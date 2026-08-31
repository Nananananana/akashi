"""One finding, in full, from the report and nothing else.

The constraint is the point. `explain` takes a report and no package, no
response and no re-audit — so if a report were not complete on its own, this is
the command that could not be written. `docs/audit-report.md` claims *a report
is a document*; these tests are where the claim is exercised rather than
repeated.

Everything here works on an archived report read back off disk. Nothing
constructs a domain object, because a reader holding an archived report has
bytes and not objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from akashi.application import audit
from akashi.errors import ContractError
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import (
    as_statement,
    explain_segment,
    segments_with_findings,
)
from akashi.infrastructure.reports import load_report_or_statement
from akashi.interfaces.cli.main import AUDITED, REFUSED, main

PACKAGES = Path(__file__).parent / "packages"

#: Quotes one figure correctly, gets a unit wrong, and mentions a third that is
#: nowhere — so one report carries a grounded particular, a contradicted one and
#: a plain floating one.
ANSWER = "テントは 2.4kg、ガスは 250mg カートリッジ。タープは 1.9kg です。"


@pytest.fixture(scope="module")
def archived() -> dict[str, Any]:
    """A report, serialised and read back — the way a reader meets one."""
    report = audit(ANSWER, load_package(PACKAGES / "gear-ja.json"), DEFAULT)
    body: dict[str, Any] = json.loads(json.dumps(report.to_dict(), ensure_ascii=False))
    return body


# --- What it says ------------------------------------------------------------


def test_it_prints_the_segment_and_its_verdict(archived: dict[str, Any]) -> None:
    printed = explain_segment(archived, "seg_001")
    assert "seg_001" in printed
    assert "contradicted" in printed
    assert "テントは 2.4kg" in printed


def test_it_names_the_rule_behind_the_verdict(archived: dict[str, Any]) -> None:
    """In the contract's words rather than new ones. A reader looking at one
    finding should not have to hold `docs/audit-report.md` open beside it."""
    from akashi.domain.verdict import Verdict

    printed = explain_segment(archived, "seg_001")
    assert Verdict.CONTRADICTED.rule in printed


def test_a_grounded_particular_says_where_it_was_found(archived: dict[str, Any]) -> None:
    printed = explain_segment(archived, "seg_001")
    assert "2.4kg" in printed
    assert "notes/2025-06-03-装備メモ.md" in printed
    assert "item itm_01" in printed


def test_a_contradicted_particular_says_what_the_source_says_and_why(
    archived: dict[str, Any],
) -> None:
    """The `why` is carried in the report. A finding that cannot say why it is a
    finding is one nobody can appeal, and that holds for the archived copy as
    much as for the live one."""
    printed = explain_segment(archived, "seg_001")
    assert "the source says '250g'" in printed
    assert "same digits" in printed


def test_a_floating_particular_says_it_resolved_nowhere(archived: dict[str, Any]) -> None:
    findings = segments_with_findings(archived)
    printed = "".join(explain_segment(archived, one) for one in findings)
    assert "1.9kg" in printed
    assert "in none of the text that was sent" in printed


# --- Narrowing ---------------------------------------------------------------


def test_a_particular_can_be_named(archived: dict[str, Any]) -> None:
    printed = explain_segment(archived, "seg_001", particular="250mg")
    assert "250mg" in printed
    assert "2.4kg" not in printed.split("Particulars", 1)[1]


def test_a_particular_that_is_not_there_is_refused_with_the_ones_that_are(
    archived: dict[str, Any],
) -> None:
    with pytest.raises(ContractError, match="carries no particular"):
        explain_segment(archived, "seg_001", particular="9kg")
    try:
        explain_segment(archived, "seg_001", particular="9kg")
    except ContractError as refusal:
        assert "'2.4kg'" in str(refusal)


def test_a_segment_that_is_not_there_is_refused_with_the_ones_that_are(
    archived: dict[str, Any],
) -> None:
    """Refused by name and with the alternatives. A tool that says only "no"
    makes the reader guess, and guessing at an id is how somebody reads the
    wrong finding and believes it."""
    with pytest.raises(ContractError, match="has no segment 'seg_099'"):
        explain_segment(archived, "seg_099")
    try:
        explain_segment(archived, "seg_099")
    except ContractError as refusal:
        assert "seg_001" in str(refusal)


# --- The constraint that makes it worth having -------------------------------


def test_it_needs_nothing_but_the_report(tmp_path: Path, archived: dict[str, Any]) -> None:
    """The whole point. Written to a file, with no package and no response
    anywhere near it, and read back by path.

    If this ever needed the package, `a report is a document` would be false and
    the fix would be to the report rather than to this test.
    """
    somewhere = tmp_path / "kept" / "report.json"
    somewhere.parent.mkdir()
    somewhere.write_text(json.dumps(archived, ensure_ascii=False), encoding="utf-8")

    printed = explain_segment(load_report_or_statement(somewhere), "seg_001")
    assert "contradicted" in printed


def test_an_attestation_and_a_bare_report_are_one_shape(tmp_path: Path) -> None:
    """A reader who archived the signed artefact holds the same document one
    envelope down. Asking them to unwrap it by hand would be asking them to know
    something the envelope already says."""
    report = audit(ANSWER, load_package(PACKAGES / "gear-ja.json"), DEFAULT)
    statement = tmp_path / "statement.json"
    statement.write_text(json.dumps(as_statement(report), ensure_ascii=False), encoding="utf-8")

    bare = tmp_path / "report.json"
    bare.write_text(json.dumps(report.to_dict(), ensure_ascii=False), encoding="utf-8")

    through_envelope = explain_segment(load_report_or_statement(statement), "seg_001")
    assert through_envelope == explain_segment(load_report_or_statement(bare), "seg_001")


def test_an_envelope_is_recognised_by_its_type_and_not_by_a_field(tmp_path: Path) -> None:
    """Keying on the presence of `predicate` would unwrap any report that
    happened to gain a field of that name. `_type` is what the envelope uses to
    say it is one."""
    report = audit(ANSWER, load_package(PACKAGES / "gear-ja.json"), DEFAULT)
    body = report.to_dict()
    body["predicate"] = {"not": "an envelope"}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    from akashi.domain.report import CONTRACT

    assert load_report_or_statement(path)["contract"] == CONTRACT


def test_a_statement_with_no_predicate_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text('{"_type": "https://in-toto.io/Statement/v1"}', encoding="utf-8")
    with pytest.raises(ContractError, match="no 'predicate'"):
        load_report_or_statement(path)


# --- What it tells a reader they cannot check --------------------------------


def test_it_says_which_offsets_the_reader_can_check_and_which_they_cannot(
    archived: dict[str, Any],
) -> None:
    """The question #53 asks, answered where it arises.

    An offset into the answer is checkable from the report: the answer is in it.
    An offset into a source document is an assertion — the reader does not have
    that document, and nothing on the screen lets them confirm the span holds
    what akashi says it holds. Saying so is the difference between a report and
    a report that reads as proof.
    """
    printed = explain_segment(archived, "seg_001")
    assert "What this screen does not let you check" in printed
    assert "Offsets into the answer you can check" in printed


def test_a_segment_with_nothing_to_check_says_so_rather_than_looking_empty() -> None:
    from akashi.domain.evidence import Evidence, item
    from akashi.domain.package import ContextPackage

    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "何もない。")]),
    )
    report = json.loads(json.dumps(audit("それは良い。", package, DEFAULT).to_dict()))
    printed = explain_segment(report, "seg_001")
    assert "nothing in this segment to check" in printed
    # No footer: there is no outward claim for a reader to be unable to check.
    assert "does not let you check" not in printed


# --- Through the command line ------------------------------------------------


def test_the_cli_explains_a_segment(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], archived: dict[str, Any]
) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(archived, ensure_ascii=False), encoding="utf-8")
    assert main(["explain", str(path), "--segment", "seg_001"]) == AUDITED
    assert "contradicted" in capsys.readouterr().out


def test_the_cli_lists_the_findings_when_no_segment_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], archived: dict[str, Any]
) -> None:
    """Discovery without a second command. A reader who has the report but not
    an id gets the ids that are worth asking about."""
    path = tmp_path / "report.json"
    path.write_text(json.dumps(archived, ensure_ascii=False), encoding="utf-8")
    assert main(["explain", str(path)]) == AUDITED
    printed = capsys.readouterr().out
    assert "Findings in this report" in printed
    assert "seg_001" in printed


def test_the_cli_refuses_an_unknown_segment_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], archived: dict[str, Any]
) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(archived, ensure_ascii=False), encoding="utf-8")
    assert main(["explain", str(path), "--segment", "seg_099"]) == REFUSED
    assert "has no segment 'seg_099'" in capsys.readouterr().err


def test_the_cli_refuses_something_that_is_not_a_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "notes.json"
    path.write_text('{"hello": "world"}', encoding="utf-8")
    assert main(["explain", str(path), "--segment", "seg_001"]) == REFUSED
    assert "contract" in capsys.readouterr().err
