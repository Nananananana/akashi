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
import contextlib
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from akashi.application import audit, recheck
from akashi.domain.matching import DEFAULT_MATCHER, MATCHERS, matcher_named
from akashi.domain.package import ContextPackage
from akashi.errors import AkashiError, ContractError
from akashi.evaluation import load_cases, run
from akashi.evaluation.case import Split
from akashi.evaluation.floors import check as check_floors
from akashi.evaluation.marked import load_marked, score_extraction
from akashi.evaluation.rendering import as_dict as evaluation_dict
from akashi.evaluation.rendering import as_text as evaluation_text
from akashi.evaluation.rendering import measured_values
from akashi.infrastructure.installation import inspect as inspect_installation
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.packages.plain import package_from_contexts, read_sample
from akashi.infrastructure.rendering import (
    as_diagnosis,
    as_json,
    as_statement,
    as_text,
    certificate,
    explain_segment,
    segments_with_findings,
)
from akashi.infrastructure.reports import load_report, load_report_or_statement
from akashi.infrastructure.settings import load_settings
from akashi.interfaces.mcp import serve as mcp_serve
from akashi.ports.judge import Judge
from akashi.version import __version__

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
    source = audit_command.add_mutually_exclusive_group(required=True)
    source.add_argument("--package", metavar="PATH", help="the ContextPackage, as JSON")
    source.add_argument(
        "--contexts",
        metavar="PATH",
        help=(
            "a JSON list of strings, or a RAGAS/DeepEval sample object, for a caller "
            "with no ContextPackage. Reads user_input/input/question, "
            "response/actual_output/answer and retrieved_contexts/retrieval_context/"
            "contexts. No provenance is invented: offsets index the strings you "
            "passed and the report says so"
        ),
    )
    audit_command.add_argument(
        "--response",
        metavar="PATH",
        help=(
            "the answer to audit; - reads standard input. Not needed when --contexts "
            "is a sample object that carries the answer"
        ),
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
            "cannot verify this and reports it as your claim (ADR-0013). This is "
            "the only restoration the command line can reach: a restorer is a live "
            "object holding the mapping, and argv carries names. For a report that "
            "says 'restored by' rather than 'asserted restored by', call "
            "akashi.audit(..., restorer=...) in the process that holds the session"
        ),
    )
    audit_command.add_argument(
        "--matcher",
        default="",
        metavar="NAME",
        choices=["", *sorted(MATCHERS)],
        help=(
            f"which strings count as the same string: {', '.join(sorted(MATCHERS))}. "
            f"The default is {DEFAULT_MATCHER.name}, which is what every number in "
            f"docs/measurements.md was measured with. The name goes on the report and "
            f"into its id, because it changes every count"
        ),
    )
    audit_command.add_argument(
        "--judge",
        default=None,
        metavar="MODEL",
        nargs="?",
        const="",
        help=(
            "ask a model about the claims akashi could not settle, and record what it "
            "said. `nli` runs a local entailment model (`pip install 'akashi[nli]'`, "
            "no network after the download); anything else is a Claude model name "
            "(`pip install 'akashi[claude]'` and an API key). A judgement is NOT a "
            "verdict: it lands in its own section under the name of the model that gave "
            "it, it is not reproducible, and it does not change report_id (ADR-0017). "
            "Defaults to claude-opus-5"
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

    commands.add_parser(
        "mcp",
        help="speak MCP over stdio, for an agent rather than a person",
        description=(
            "Serves the same use cases as this CLI over JSON-RPC on stdin and stdout, "
            "so an assistant holding a package and an answer can audit before handing "
            "the answer on. Read-only, and it takes no paths: the model chooses the "
            "arguments, and a tool that opened a file the model named would be a "
            "file-read primitive with a report as the channel out. Nothing is printed "
            "on stdout that is not a protocol message."
        ),
    )

    commands.add_parser(
        "doctor",
        help="what is installed, what is missing, and what this console will do",
        description=(
            "Reports the running installation: akashi's version, the contract it "
            "ships and its hash, the language packs, what this console can print, "
            "and which siblings are importable. It decides nothing -- these are "
            "facts about a machine, and the two defects this project shipped that "
            "were invisible in development were both facts about a machine."
        ),
    )

    certificate_command = commands.add_parser(
        "certificate",
        help="the report as one HTML file, for somebody who will sign it",
        description=(
            "Renders a report as a single self-contained HTML document: the answer "
            "with every particular marked where it stands, what was not checked "
            "first, and the traced particulars a signer is signing. Reads the report "
            "and nothing else. No scripts, no network, no fonts -- opening it fetches "
            "nothing -- and the same report always renders to the same bytes, because "
            "a signature is over bytes."
        ),
    )
    certificate_command.add_argument(
        "report",
        metavar="REPORT",
        help="the audit report, as JSON; an in-toto statement is read through its predicate",
    )
    certificate_command.add_argument(
        "--out",
        metavar="PATH",
        default="",
        help="write here instead of standard output. Refuses to overwrite (--force)",
    )
    certificate_command.add_argument(
        "--force",
        action="store_true",
        help="overwrite the file at --out. A certificate somebody already signed is "
        "not a file to replace by accident",
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


def _document(text: str, out: TextIO) -> None:
    """A document leaves as UTF-8, whatever the console happens to be.

    ``_read`` above already says it for input -- *UTF-8 either way and never the
    platform encoding* -- and nothing said it for output, so akashi read
    deliberately and wrote by accident. Redirected on a Japanese Windows
    console, ``--json`` wrote ``cp932``: not valid JSON (RFC 8259 requires
    UTF-8), refused by ``recheck``, ``explain`` and ``certificate``, and
    carrying a ``response_hash`` taken over UTF-8 bytes the file does not
    contain. **akashi could not read the document akashi had just written.**

    This is the other half of the narrow-console problem. Prose on a screen
    degrades to what the console can show, because losing a character beats
    losing the audit. A *document* must not degrade at all -- it is read by a
    program somewhere else, and a `?` in it is corruption rather than a
    concession. So the bytes go to the buffer underneath the stream rather than
    through its encoder.

    A stream with no ``buffer`` is a test's ``StringIO``, which holds text and
    has no encoding to get wrong.
    """
    buffer = getattr(out, "buffer", None)
    if buffer is None:
        out.write(text)
        return
    out.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()


def _inputs(arguments: argparse.Namespace) -> tuple[ContextPackage, str]:
    """The package and the answer, from whichever pair of flags was given.

    `--contexts` is the door for somebody who has what every other library in
    this space takes -- an answer and a list of retrieved strings -- and no
    ContextPackage, which is almost everybody. A sample object may carry the
    answer too, so `--response` is optional beside it and required beside a
    package.
    """
    if arguments.package:
        return load_package(arguments.package), _read(arguments.response)

    body = json.loads(_read(arguments.contexts))
    if isinstance(body, list):
        return package_from_contexts(body), _read(arguments.response)
    if not isinstance(body, dict):
        raise ContractError(
            f"--contexts is a JSON list of strings or a sample object, not {type(body).__name__}"
        )

    sample_answer, package = read_sample(body)
    # An explicit --response wins over the one in the file: a caller who names
    # both meant the one they named, and silently preferring the file would
    # audit something other than what they asked about.
    return package, _read(arguments.response) if arguments.response else sample_answer


def _audit(arguments: argparse.Namespace, out: TextIO) -> int:
    # A flag beats a file beats a default, and the file said where it was. Both
    # of these reach `report_id`, so a run configured one way cannot be mistaken
    # for a run configured another -- which is the only reason a configuration
    # file is safe to read at all.
    settings = load_settings()
    languages = arguments.language or list(settings.languages)
    matcher_name = arguments.matcher or settings.matcher

    package, answer = _inputs(arguments)
    chosen = packs(*languages) if languages else DEFAULT

    report = audit(
        answer,
        package,
        chosen,
        restored_by=arguments.restored_by,
        akashi_version=__version__,
        matcher=matcher_named(matcher_name) if matcher_name else DEFAULT_MATCHER,
    )
    if arguments.judge is not None:
        # After the audit and never during it. akashi has already decided every
        # verdict by comparing strings; this adds an annotation about the ones
        # it could not settle, and cannot move anything it did.
        # Imported here and nowhere else. `import akashi` must not reach an
        # HTTP client on a machine that happens to have the extra installed,
        # and a module-level import would make it do exactly that.
        from akashi.application.judging import judge_report

        chosen_judge = _judge(arguments.judge)
        report = dataclasses.replace(
            report, judged=judge_report(report, chosen_judge, package.evidence)
        )

    if arguments.attestation:
        subject = arguments.subject or (
            "response" if arguments.response == "-" else Path(arguments.response).name
        )
        statement = as_statement(report, subject=subject)
        rendered = json.dumps(statement, ensure_ascii=False, indent=2) + "\n"
        _document(rendered, out)
    elif arguments.json:
        _document(as_json(report), out)
    else:
        # Prose, for a reader at a terminal. This one goes through the console's
        # encoder so that a document it cannot represent costs characters rather
        # than the whole audit.
        print(as_text(report), end="", file=out)

    if (arguments.fail_on_findings or settings.fail_on_findings) and report.has_findings:
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
        print("akashi explain - name a segment with --segment", file=out)
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


def _mcp(_arguments: argparse.Namespace, _out: TextIO) -> int:
    """Speak MCP on stdin and stdout until the client goes away.

    It does not take the `out` this function is handed. Every other command
    writes prose through the console's encoder so a character it cannot show
    costs a character rather than the audit; this is a document channel to a
    program, where a `?` is corruption, so the server binds UTF-8 on both
    directions itself.
    """
    return mcp_serve()


def _judge(named: str) -> Judge:
    """The judge the caller asked for, imported only once one was asked for.

    `nli` is the local entailment model; anything else is a Claude model name.
    Both fill the same port, which is why this is a two-line dispatch rather
    than a second code path through the audit -- and why a third judge is a
    module and an entry here, not a change to anything that decides.

    The imports stay inside the branches. `import akashi` must reach neither an
    HTTP client nor torch on a machine that happens to have an extra installed,
    and a module-level import would make it do exactly that.
    """
    if named == "nli":
        from akashi.infrastructure.adapters.nli_judge import NliJudge

        return NliJudge()
    from akashi.infrastructure.adapters.claude_judge import DEFAULT_MODEL, ClaudeJudge

    return ClaudeJudge(model=named or DEFAULT_MODEL)


def _doctor(_arguments: argparse.Namespace, out: TextIO) -> int:
    """What is here, and what is not.

    Prose for a person, so it goes through the console's encoder -- and it is
    the one command most likely to be run *because* the console is the problem,
    so every word of it is ASCII.

    Exits ``REFUSED`` when something akashi promised to ship is absent. A
    diagnostic that returns success whatever it found is a diagnostic no script
    can use, and this one is going to be run by people pasting its output into
    an issue.
    """
    installation = inspect_installation(DEFAULT)
    print(as_diagnosis(installation), end="", file=out)
    return REFUSED if installation.missing else AUDITED


def _certificate(arguments: argparse.Namespace, out: TextIO) -> int:
    """The report as one HTML file.

    Written as bytes with an explicit UTF-8 encoding rather than through the
    console's, because the file is the artefact: a certificate that came out
    `cp932` on the machine that made it is a certificate that loses the answer
    it audited on the machine that reads it, and the answer is the thing every
    offset on the page indexes.
    """
    document = load_report_or_statement(arguments.report)
    page = certificate(document)

    if not arguments.out:
        print(page, end="", file=out)
        return AUDITED

    destination = Path(arguments.out)
    if destination.exists() and not arguments.force:
        raise ContractError(
            f"{destination} exists. A certificate is an artefact somebody may have "
            f"already signed or filed, so this does not overwrite one by accident; "
            f"pass --force if replacing it is what you meant."
        )
    destination.write_bytes(page.encode("utf-8"))
    print(f"akashi: wrote {destination}", file=out)
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
        _document(json.dumps(body, ensure_ascii=False, indent=2) + "\n", out)
    else:
        print(f"akashi recheck - {result.describe()}", file=out)
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
        _document(json.dumps(body, ensure_ascii=False, indent=2) + "\n", out)
    else:
        print(
            evaluation_text(
                breakdown,
                notes,
                cases=len(cases),
                extraction=extraction,
                floors=(measured, breaches),
            ),
            end="",
            file=out,
        )
    if arguments.gate and breaches:
        # Named on stderr as well, because a build log is read from the end and
        # the reason a gate went red should not need scrolling for.
        for breach in breaches:
            print(f"akashi: {breach.describe()}", file=sys.stderr)
        return BREACHED
    return AUDITED


def _tolerate_a_narrow_console() -> None:
    """Print what the console can and a ``?`` for the rest, rather than crash.

    akashi echoes text it did not write: the answer, a segment, a particular, a
    source path. On a Japanese Windows console -- `cp932`, which is what a
    reader gets by typing `akashi` without setting anything -- a Chinese
    document or a stray typographic character raises `UnicodeEncodeError` and
    the audit is lost after doing all of its work.

    **Not `encoding="utf-8"`.** That makes the characters representable and
    then the terminal decodes them as `cp932` anyway, so the Japanese akashi is
    most often printing comes out as mojibake. `errors="replace"` keeps
    everything the console *can* show exactly right and degrades only what it
    cannot, which is the smaller loss for the text akashi actually handles.

    akashi's own prose is ASCII, so nothing here should ever be replaced. This
    is for the text somebody else wrote.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None or getattr(stream, "errors", None) == "replace":
            continue
        # A stream that cannot be reconfigured -- a pipe somebody replaced, a
        # capture object -- is not a reason to refuse to run.
        with contextlib.suppress(ValueError, OSError):
            reconfigure(errors="replace")


def _check_arguments(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> None:
    """The one rule argparse cannot state, checked where argparse would.

    `--response` is required beside `--package` and optional beside
    `--contexts`, because a sample object may carry the answer and a package
    never does. A missing one is a **wrong command line** and not an unauditable
    input, so it exits 2 like every other misuse rather than 1 like a refusal.
    """
    if getattr(arguments, "command", "") != "audit" or arguments.response:
        return
    if arguments.package:
        parser.error("--package needs --response: the answer to audit")
    if arguments.contexts:
        # A list of strings carries no answer; a sample object may.
        with contextlib.suppress(OSError, ValueError, UnicodeDecodeError):
            if isinstance(json.loads(_read(arguments.contexts)), list):
                parser.error(
                    "--contexts is a list of strings, so the answer has to come from "
                    "--response. A sample object carrying both is the other way in."
                )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Returns an exit code rather than calling ``sys.exit``.

    A function that exits the process cannot be called by a test, and the
    behaviour worth testing is the exit code.
    """
    _tolerate_a_narrow_console()
    parser = _parser()
    arguments = parser.parse_args(argv)
    _check_arguments(parser, arguments)

    try:
        if arguments.command == "eval":
            return _eval(arguments, sys.stdout)
        if arguments.command == "recheck":
            return _recheck(arguments, sys.stdout)
        if arguments.command == "explain":
            return _explain(arguments, sys.stdout)
        if arguments.command == "certificate":
            return _certificate(arguments, sys.stdout)
        if arguments.command == "doctor":
            return _doctor(arguments, sys.stdout)
        if arguments.command == "mcp":
            return _mcp(arguments, sys.stdout)
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
