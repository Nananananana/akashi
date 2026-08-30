"""``akashi audit`` -- the first thing anyone runs.

The composition root. It is the only module that knows the language packs
exist, the only one that opens a file, and it decides nothing about an answer.

**Exit codes**, because a caller in a pipeline needs to tell three things
apart:

``0``  the answer was audited
``1``  it could not be audited -- a protected answer, an unreadable package
``2``  the command line was wrong
``3``  audited, and something floats. Only with ``--fail-on-findings``

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
from akashi.application import audit
from akashi.errors import AkashiError
from akashi.evaluation import load_cases, run
from akashi.evaluation.case import Split
from akashi.evaluation.marked import load_marked, score_extraction
from akashi.evaluation.rendering import as_dict as evaluation_dict
from akashi.evaluation.rendering import as_text as evaluation_text
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import as_json, as_text

__all__ = ["main"]

AUDITED = 0
REFUSED = 1
MISUSED = 2
FOUND = 3


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
    rendered = as_json(report) if arguments.json else as_text(report)
    print(rendered, end="", file=out)

    if arguments.fail_on_findings and report.has_findings:
        return FOUND
    return AUDITED


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

    if arguments.json:
        body = evaluation_dict(breakdown, notes, cases=len(cases), extraction=extraction)
        rendered = json.dumps(body, ensure_ascii=False, indent=2) + "\n"
    else:
        rendered = evaluation_text(breakdown, notes, cases=len(cases), extraction=extraction)
    print(rendered, end="", file=out)
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
