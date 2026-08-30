"""``akashi audit`` -- the first thing anyone runs.

The composition root. It is the only module that knows the language packs
exist, the only one that opens a file, and it decides nothing about an answer.

**Exit codes**, because a caller in a pipeline needs to tell three things
apart:

``0``  the answer was audited
``1``  it could not be audited -- a protected answer, an unreadable package
``2``  the command line was wrong
``3``  audited, and something floats. Only with ``--fail-on-findings``
``4``  a floor was breached. Only with ``eval --gate``
``5``  a report re-derived differently. Only from ``recheck``

The default is ``0`` for an audit that found problems, because *finding* things
is what an auditor does and a non-zero exit for that would make the ordinary
case look like a failure. A caller who wants the build to go red asks for it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from akashi import __version__
from akashi.application import audit, recheck
from akashi.errors import AkashiError
from akashi.evaluation import load_cases, run
from akashi.evaluation.case import Split
from akashi.evaluation.floors import check as check_floors
from akashi.evaluation.marked import load_marked, score_extraction
from akashi.evaluation.rendering import as_dict as evaluation_dict
from akashi.evaluation.rendering import as_text as evaluation_text
from akashi.evaluation.rendering import measured_values
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import (
    as_json,
    as_statement,
    as_text,
    explain_segment,
    segments_with_findings,
)
from akashi.infrastructure.reports import load_report, load_report_or_statement

__all__ = ["main"]

AUDITED = 0
REFUSED = 1
MISUSED = 2
FOUND = 3
BREACHED = 4
DIFFERED = 5


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="akashi",
        description=(
            "Separate what an answer took from its evidence from what it made up. "
            "Deterministic, offline, no model."
        ),
    )
    parser.add_argument("--version", action="version", version=f"akashi {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    audit_command = commands.add_parser(
        "audit",
        help="audit an answer against the package that produced it",
        description=(
            "Reads a ContextPackage and an answer, and reports which particulars of "
            "the answer are in the text that was sent. A grounded particular is a "
            "statement about strings, not about truth."
        ),
    )
    audit_command.add_argument(
        "--package", required=True, metavar="PATH", help="the ContextPackage, as JSON"
    )
    audit_command.add_argument(
        "--response",
        required=True,
        metavar="PATH",
        help="the answer to audit; - reads standard input",
    )
    audit_command.add_argument(
        "--json", action="store_true", help="emit the report as JSON instead of text"
    )
    audit_command.add_argument(
        "--attestation",
        action="store_true",
        help=(
            "emit the report as an unsigned in-toto Statement, for a pipeline that "
            "signs its artefacts. akashi signs nothing: the keys are yours (ADR-0014)"
        ),
    )
    audit_command.add_argument(
        "--subject",
        default="",
        metavar="NAME",
        help="the subject name in the attestation. Defaults to the response path",
    )
    audit_command.add_argument(
        "--language",
        action="append",
        metavar="CODE",
        help=(
            "restrict the language packs, for measurement. Repeatable. The default is "
            "every pack, and narrowing under-segments -- see ADR-0011"
        ),
    )
    audit_command.add_argument(
        "--restored-by",
        default="",
        metavar="WHO",
        help=(
            "assert that you restored the answer yourself, naming who did. akashi "
            "cannot verify this and reports it as your claim (ADR-0013)"
        ),
    )
    audit_command.add_argument(
        "--fail-on-findings",
        action="store_true",
        help=f"exit {FOUND} when anything floats, for a pipeline that gates on it",
    )

    recheck_command = commands.add_parser(
        "recheck",
        help="re-derive a report from the inputs it names, and compare",
        description=(
            "Takes a report somebody else produced, re-derives it from the package "
            "and the response the report names, and reports whether the report_id "
            "matches. This is the difference between an audit and an opinion."
        ),
    )
    recheck_command.add_argument("report", metavar="REPORT", help="the audit report, as JSON")
    recheck_command.add_argument("--package", required=True, metavar="PATH")
    recheck_command.add_argument(
        "--response", required=True, metavar="PATH", help="- reads standard input"
    )
    recheck_command.add_argument(
        "--restored-by",
        default="",
        metavar="WHO",
        help="as for audit; needed when the report was made over a restored answer",
    )
    recheck_command.add_argument("--json", action="store_true")

    explain_command = commands.add_parser(
        "explain",
        help="one finding, in full, from the report alone",
        description=(
            "Prints one segment of a report with everything about it: the sentence, "
            "every particular, where each resolved, what the source says instead, and "
            "what the verdict means. It reads the report and nothing else -- no "
            "package, no response, no re-audit -- which is how the claim that a report "
            "is a document gets exercised rather than asserted."
        ),
    )
    explain_command.add_argument(
        "report",
        metavar="REPORT",
        help="the audit report, as JSON; an in-toto statement is read through its predicate",
    )
    explain_command.add_argument(
        "--segment",
        metavar="ID",
        default="",
        help="which segment. Omitted, the findings are listed for you to choose from",
    )
    explain_command.add_argument(
        "--particular",
        metavar="TEXT",
        default="",
        help="narrow to one particular by its text, for a segment carrying a dozen",
    )

    eval_command = commands.add_parser(
        "eval",
        help="run the labelled corpus and print what it establishes",
        description=(
            "Audits every case in the corpus and counts what happened. All "
            "arithmetic: no grader, no rubric, no model. Every rate prints its "
            "counts, because a share on its own is a share a reader supplies a "
            "generous denominator for."
        ),
    )
    eval_command.add_argument(
        "--cases", default="tests/cases", metavar="DIR", help="the corpus directory"
    )
    eval_command.add_argument(
        "--tier", default="", metavar="NAME", help="run only the cases in this tier"
    )
    eval_command.add_argument(
        "--held-out",
        action="store_true",
        help="read the held-out split as well. It is not read by default, and a "
        "held-out split that anything touches by default is a training split "
        "with a different name",
    )
    eval_command.add_argument(
        "--marked",
        default="tests/marked",
        metavar="DIR",
        help="hand-marked realistic answers, for extraction recall. Skipped when absent",
    )
    eval_command.add_argument(
        "--gate",
        action="store_true",
        help=f"exit {BREACHED} when a metric falls through its floor. The floors are in "
        f"src/akashi/evaluation/floors.py, each beside the score it was set against",
    )
    eval_command.add_argument("--json", action="store_true", help="emit the numbers as JSON")
    eval_command.add_argument(
        "--language", action="append", metavar="CODE", help="restrict the language packs"
    )
    return parser


def _read(location: str) -> str:
    """The answer, from a file or from standard input.

    UTF-8 either way and never the platform encoding. Half of what akashi
    audits is CJK, and an answer read with the wrong encoding audits as
    fabricated in full.
    """
    if location == "-":
        return sys.stdin.buffer.read().decode("utf-8")
    return Path(location).read_text(encoding="utf-8")


def _audit(arguments: argparse.Namespace, out: TextIO) -> int:
    package = load_package(arguments.package)
    answer = _read(arguments.response)
    chosen = packs(*arguments.language) if arguments.language else DEFAULT

    report = audit(
        answer,
        package,
        chosen,
        restored_by=arguments.restored_by,
        akashi_version=__version__,
    )
    if arguments.attestation:
        subject = arguments.subject or (
            "response" if arguments.response == "-" else Path(arguments.response).name
        )
        statement = as_statement(report, subject=subject)
        rendered = json.dumps(statement, ensure_ascii=False, indent=2) + "\n"
    elif arguments.json:
        rendered = as_json(report)
    else:
        rendered = as_text(report)
    print(rendered, end="", file=out)

    if arguments.fail_on_findings and report.has_findings:
        return FOUND
    return AUDITED


def _explain(arguments: argparse.Namespace, out: TextIO) -> int:
    """One segment of a report, from the report alone.

    A statement is unwrapped to its predicate first: an attestation and a bare
    report are one shape, and a reader who archived the signed thing should not
    have to unwrap it by hand to read it.
    """
    document = load_report_or_statement(arguments.report)
    if not arguments.segment:
        findings = segments_with_findings(document)
        print("akashi explain — name a segment with --segment", file=out)
        print(file=out)
        if findings:
            print("Findings in this report", file=out)
            for segment_id in findings:
                print(f"  {segment_id}", file=out)
        else:
            print("  this report has no findings; every segment can still be named", file=out)
        return AUDITED

    print(
        explain_segment(document, arguments.segment, particular=arguments.particular or None),
        end="",
        file=out,
    )
    return AUDITED


def _recheck(arguments: argparse.Namespace, out: TextIO) -> int:
    archived = load_report(arguments.report)
    package = load_package(arguments.package)
    answer = _read(arguments.response)

    # The packs the *report* names, not this machine's default. Re-deriving with
    # a different pack set would change the segmentation and therefore every
    # count, and the difference would be the recheck's rather than the report's.
    named = [code for code in archived["audited"]["packs"] if code != "und"]
    try:
        chosen = packs(*named) if named else DEFAULT
    except ValueError as error:
        raise AkashiError(
            f"the report names a language pack this akashi does not have: {error}. "
            f"A recheck under a different set of packs is not a recheck."
        ) from error

    result = recheck(
        archived,
        answer,
        package,
        chosen,
        restored_by=arguments.restored_by,
        akashi_version=__version__,
    )

    if arguments.json:
        body = {
            "archived_id": result.archived_id,
            "rederived_id": result.rederived_id,
            "matches": result.matches,
            "version_differs": result.version_differs,
            "archived_version": result.archived_version,
            "rederived_version": result.rederived_version,
            "differences": list(result.differences),
        }
        print(json.dumps(body, ensure_ascii=False, indent=2), file=out)
    else:
        print(f"akashi recheck — {result.describe()}", file=out)
        if not result.matches:
            print(f"  archived   {result.archived_id}", file=out)
            print(f"  re-derived {result.rederived_id}", file=out)
            print("", file=out)
            for line in result.differences[:40]:
                print(f"  {line}", file=out)
            if len(result.differences) > 40:
                print(f"  ... and {len(result.differences) - 40} more", file=out)

    return AUDITED if result.matches else DIFFERED


def _eval(arguments: argparse.Namespace, out: TextIO) -> int:
    splits = (Split.TRAIN, Split.HELD_OUT) if arguments.held_out else (Split.TRAIN,)
    cases = load_cases(arguments.cases, splits=splits, tier=arguments.tier)
    if not cases:
        print("akashi: no cases matched", file=sys.stderr)
        return REFUSED

    chosen = packs(*arguments.language) if arguments.language else DEFAULT
    breakdown, notes = run(cases, chosen)

    # Skipped rather than refused when absent: the corpus and the marked
    # answers measure different things, and a caller who has one should get
    # the numbers it supports rather than an error about the other.
    extraction = None
    if Path(arguments.marked).is_dir():
        answers = load_marked(arguments.marked)
        overall, by_language, _ = score_extraction(answers, chosen)
        extraction = (overall, by_language)

    measured = measured_values(breakdown, extraction)
    breaches = check_floors(measured)

    if arguments.json:
        body = evaluation_dict(breakdown, notes, cases=len(cases), extraction=extraction)
        body["floors"] = {
            "breaches": [breach.describe() for breach in breaches],
            "measured": measured,
        }
        rendered = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = evaluation_text(
            breakdown,
            notes,
            cases=len(cases),
            extraction=extraction,
            floors=(measured, breaches),
        )
    print(rendered, end="", file=out)
    if arguments.gate and breaches:
        # Named on stderr as well, because a build log is read from the end and
        # the reason a gate went red should not need scrolling for.
        for breach in breaches:
            print(f"akashi: {breach.describe()}", file=sys.stderr)
        return BREACHED
    return AUDITED


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Returns an exit code rather than calling ``sys.exit``.

    A function that exits the process cannot be called by a test, and the
    behaviour worth testing is the exit code.
    """
    parser = _parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "eval":
            return _eval(arguments, sys.stdout)
        if arguments.command == "recheck":
            return _recheck(arguments, sys.stdout)
        if arguments.command == "explain":
            return _explain(arguments, sys.stdout)
        if arguments.command != "audit":  # pragma: no cover - argparse refuses it first
            parser.error(f"unknown command {arguments.command!r}")
        return _audit(arguments, sys.stdout)
    except AkashiError as refusal:
        # akashi refuses loudly and by name (ADR-0008). Not a traceback: a
        # refusal is an answer, and a traceback reads as a bug in the tool.
        print(f"akashi: {refusal}", file=sys.stderr)
        return REFUSED
    except OSError as error:
        print(f"akashi: {error}", file=sys.stderr)
        return REFUSED
    except UnicodeDecodeError as error:
        print(
            f"akashi: the answer is not UTF-8: {error}. Text read with the wrong "
            f"encoding audits as fabricated in full.",
            file=sys.stderr,
        )
        return REFUSED


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
