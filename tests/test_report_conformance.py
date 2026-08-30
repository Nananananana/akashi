"""The report is a document, and this is what makes that true.

ADR-0002. Two representations of the same thing exist — the dataclasses and the
schema — and there is no pydantic here (ADR-0001) to derive one from the other.
**These tests are the only thing keeping them in step**, which is why they check
the enums as well as the shape: a value akashi can emit and the schema does not
allow is a report no conforming consumer can read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

jsonschema = pytest.importorskip("jsonschema", reason="a dev dependency; see [dev] in pyproject")

from akashi.application import audit  # noqa: E402
from akashi.domain.coverage import SkipRule  # noqa: E402
from akashi.domain.language import Script  # noqa: E402
from akashi.domain.particular import ParticularKind  # noqa: E402
from akashi.domain.report import CONTRACT  # noqa: E402
from akashi.domain.segment import Boundary, SegmentKind  # noqa: E402
from akashi.domain.verdict import Standing, Verdict  # noqa: E402
from akashi.evaluation import load_cases  # noqa: E402
from akashi.evaluation.case import Split  # noqa: E402
from akashi.infrastructure.languages import DEFAULT  # noqa: E402
from akashi.infrastructure.packages import load_package  # noqa: E402
from akashi.infrastructure.rendering import as_dict  # noqa: E402

ROOT = Path(__file__).parent.parent
SCHEMA = ROOT / "schemas" / "audit-report-1.json"
PACKAGES = Path(__file__).parent / "packages"
ANSWERS = Path(__file__).parent / "answers"
CASES = Path(__file__).parent / "cases"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    body: dict[str, Any] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return body


def reports() -> list[tuple[str, dict[str, Any]]]:
    """Every report the corpus and the fixtures can produce.

    The corpus is the interesting half: it exercises refusals, unbearing
    segments, interpretations and every verdict akashi emits, which a
    hand-written example would not.
    """
    found: list[tuple[str, dict[str, Any]]] = []
    for case in load_cases(CASES, splits=(Split.TRAIN, Split.HELD_OUT)):
        if case.expect_refusal:
            continue
        found.append((case.case_id, as_dict(audit(case.response, case.package, DEFAULT))))

    for name in ("gear-ja", "contract-en"):
        package = load_package(PACKAGES / f"{name}.json")
        answer = (
            (ANSWERS / "gear-ja.txt").read_text(encoding="utf-8")
            if name == "gear-ja"
            else "Section 4(b) allows 30 days notice. The cap rose in 2025."
        )
        found.append((name, as_dict(audit(answer, package, DEFAULT))))
    assert found, "no reports to check; this test is measuring nothing"
    return found


ALL_REPORTS = reports()


# --- The shape ---------------------------------------------------------------


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_every_report_conforms_to_the_published_schema(
    name: str, report: dict[str, Any], schema: dict[str, Any]
) -> None:
    jsonschema.validate(report, schema)


def test_the_schema_itself_is_a_valid_schema(schema: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)


def test_the_schema_ships_inside_the_wheel() -> None:
    """A consumer validating a report should not have to fetch a schema from
    the internet, and an auditor whose schema lives on someone else's server is
    not an auditor."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    live = [line for line in pyproject.splitlines() if not line.lstrip().startswith("#")]
    assert "[tool.hatch.build.targets.wheel.force-include]" in live


# --- The enums, in both places -----------------------------------------------


def enum_of(schema: dict[str, Any], name: str) -> set[Any]:
    return set(schema["$defs"][name]["enum"])


def test_the_verdicts_in_the_code_are_the_verdicts_in_the_schema(
    schema: dict[str, Any],
) -> None:
    assert enum_of(schema, "verdict") == {one.value for one in Verdict}


def test_the_standings_in_the_code_are_the_standings_in_the_schema(
    schema: dict[str, Any],
) -> None:
    assert enum_of(schema, "standing") == {one.value for one in Standing}


def test_the_particular_kinds_in_the_code_are_the_kinds_in_the_schema(
    schema: dict[str, Any],
) -> None:
    assert enum_of(schema, "particular_kind") == {one.value for one in ParticularKind}


def test_the_skip_rules_in_the_code_are_the_rules_in_the_schema(
    schema: dict[str, Any],
) -> None:
    assert enum_of(schema, "skip_rule") == {one.value for one in SkipRule}


def test_the_segment_kinds_in_the_code_are_the_kinds_in_the_schema(
    schema: dict[str, Any],
) -> None:
    kinds = set(schema["$defs"]["segment"]["properties"]["kind"]["enum"])
    assert kinds == {one.value for one in SegmentKind}


def test_the_boundaries_in_the_code_are_the_boundaries_in_the_schema(
    schema: dict[str, Any],
) -> None:
    boundaries = set(schema["$defs"]["segment"]["properties"]["boundary"]["enum"])
    assert boundaries == {one.value for one in Boundary}


def test_the_scripts_in_the_code_are_the_scripts_in_the_schema(
    schema: dict[str, Any],
) -> None:
    scripts = set(schema["$defs"]["segment"]["properties"]["script"]["enum"])
    assert scripts == {one.value for one in Script}


# --- The rules the schema cannot express -------------------------------------


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_every_span_indexes_the_answer_the_report_carries(
    name: str, report: dict[str, Any]
) -> None:
    """A report is complete on its own. A reader following a finding needs
    nothing but the document in their hand."""
    answer = report["answer"]
    for segment in report["segments"]:
        start, end = segment["span"]
        assert answer[start:end] == segment["text"], f"{name}: {segment['segment_id']}"
        for particular in segment.get("particulars", []):
            at, to = particular["span"]
            assert answer[at:to] == particular["text"]


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_the_coverage_adds_up(name: str, report: dict[str, Any]) -> None:
    coverage = report["coverage"]
    assert (
        coverage["bearing"] + coverage["unbearing"] + coverage["unexamined"] == coverage["segments"]
    )
    assert coverage["segments"] == len(report["segments"])


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_every_verdict_is_counted_including_the_zeroes(name: str, report: dict[str, Any]) -> None:
    counted = report["counts"]["segments"]
    assert set(counted) == {one.value for one in Verdict}
    assert sum(counted.values()) == len(report["segments"])


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_every_unchecked_span_belongs_to_a_segment(name: str, report: dict[str, Any]) -> None:
    """ADR-0005: every discarding path carries its reason to the end. A skip
    naming no segment is a gap nobody can follow up."""
    known = {segment["segment_id"] for segment in report["segments"]}
    for skip in report["unchecked"]:
        assert skip["segment_id"] in known
        assert skip["reason"]


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_the_limits_travel_with_every_report(name: str, report: dict[str, Any]) -> None:
    """On the artefact rather than in the documentation. The artefact travels."""
    assert len(report["limits"]) == 4
    assert any("not about truth" in limit for limit in report["limits"])


@pytest.mark.parametrize(("name", "report"), ALL_REPORTS, ids=[n for n, _ in ALL_REPORTS])
def test_a_grounded_particular_carries_a_location_and_a_floating_one_does_not(
    name: str, report: dict[str, Any]
) -> None:
    for segment in report["segments"]:
        for particular in segment.get("particulars", []):
            if particular["standing"] == "grounded":
                assert particular["locations"]
            else:
                assert "locations" not in particular


def test_the_contract_is_still_a_draft() -> None:
    """The freeze is a condition, not a date: a second program has to have
    produced *and consumed* a report. When that happens, this test changes in
    the same commit that records why."""
    assert CONTRACT.endswith("-draft")


def test_a_report_that_is_not_conforming_is_caught(schema: dict[str, Any]) -> None:
    """The suite is only worth anything if it can fail."""
    broken = dict(ALL_REPORTS[0][1])
    broken["contract"] = "somebody.else/1"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, schema)
