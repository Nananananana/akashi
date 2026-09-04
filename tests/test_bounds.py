"""Where a limit changed the answer, and whether the report says so.

akashi has four bounds and all four are correct. Three of them were silent, and
the third one below is why this file exists: a sentence plainly containing a
number came back "akashi looked and there was nothing to check". Nothing
raised. Nothing was slow. The report was wrong and looked fine.

Each test names the bound it exercises and asserts the bound was actually
reached before asserting what was said about it -- a test for a truncation
message that stops truncating is a test that has stopped checking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from akashi import evaluate
from akashi.application.judging import MAX_CLAIMS, claims_and_total, claims_for
from akashi.domain.bounds import Bound, from_unsent_claims, oversized_runs
from akashi.domain.extraction import MAX_RUN
from akashi.domain.matching import LOCATION_LIMIT
from akashi.domain.report import AuditReport

TENT = "The tent weighs 2.4kg."


def _schema() -> dict[str, Any]:
    """The published contract, loaded. `conftest.published_schema` gives its
    path; every caller here wants the document."""
    from conftest import published_schema

    body: dict[str, Any] = json.loads(published_schema().read_text(encoding="utf-8"))
    return body


def bound_lines(report: dict[str, object], name: str) -> list[str]:
    limits = report["limits"]
    assert isinstance(limits, list)
    return [line for line in limits if isinstance(line, str) and line.startswith(f"{name}=")]


# --- MAX_RUN: the number that vanished ---------------------------------------


def test_a_number_too_long_to_extract_is_not_silence() -> None:
    """The worst of the three. `share=None` reads as 'this answer contained
    nothing checkable', and the answer contained a 301-digit number."""
    digits = "1" * 301
    result = evaluate(answer=f"The value is {digits}.", contexts=[f"The value is {digits}."])
    assert result.grounded_share is None, "the setup no longer reproduces the miss"

    body = result.to_dict()
    [line] = bound_lines(body, "MAX_RUN")
    assert "301" in line
    assert str(MAX_RUN) in line
    assert "akashi did not look" in line


def test_an_ordinary_answer_carries_no_bound_at_all() -> None:
    """A report listing every bound akashi has is a report where the one that
    mattered is buried among three that did not."""
    body = evaluate(answer=TENT, contexts=[TENT]).to_dict()
    assert body["bounds"] == []
    assert not [line for line in body["limits"] if line.startswith(("MAX_", "LOCATION_"))]


def test_a_number_at_the_bound_is_still_seen() -> None:
    """The receipt is for what was missed, so it must not fire on what was not."""
    digits = "1" * MAX_RUN
    result = evaluate(answer=f"The value is {digits}.", contexts=[f"The value is {digits}."])
    assert result.grounded_share == 1.0
    assert result.to_dict()["bounds"] == []


@pytest.mark.parametrize("run", ["1" * 300, "１" * 300, "1," * 200])
def test_the_scan_reaches_the_shapes_a_number_actually_takes(run: str) -> None:
    """Full-width digits and thousands separators are numbers akashi reads
    everywhere else; a detector that only knew ASCII would be silent again on
    exactly the half of the corpus that is CJK."""
    assert oversized_runs(f"value {run} here", MAX_RUN)


def test_the_scan_says_nothing_about_ordinary_text() -> None:
    assert oversized_runs("The tent weighs 2.4kg on 2024-03-01.", MAX_RUN) == ()


# --- LOCATION_LIMIT: the count that was a floor ------------------------------


def test_a_particular_found_more_times_than_the_cap_says_the_count_is_a_floor() -> None:
    crowded = " ".join([TENT] * 40)
    result = evaluate(answer=TENT, contexts=[crowded])
    places = [
        place
        for segment in result.report.assessment.segments
        for one in segment.particulars
        for place in one.locations
    ]
    assert len(places) == LOCATION_LIMIT, "the cap was not reached, so this checks nothing"

    [line] = bound_lines(result.to_dict(), "LOCATION_LIMIT")
    assert "at least" in line
    assert "floors" in line


def test_a_particular_under_the_cap_reports_no_floor() -> None:
    result = evaluate(answer=TENT, contexts=[" ".join([TENT] * 3)])
    assert bound_lines(result.to_dict(), "LOCATION_LIMIT") == []


# --- MAX_CLAIMS: the judge that was shown a third of it ----------------------


def many_floating() -> AuditReport:
    answer = "".join(f"Item {n} weighs {n}.{n % 10}kg. " for n in range(1, 101))
    return evaluate(answer=answer, contexts=["Nothing here matches anything."]).report


def expected_total(report: AuditReport) -> int:
    """How many claims there are, counted independently of the thing under test.

    `total > MAX_CLAIMS` was the first version of this and it does not work: a
    loop that returns early on the claim *after* the cap reports 65, which is
    greater than 64 and self-consistent with every other number it produces.
    The poison walked straight through it. So the expectation is derived from
    the report instead, by the same rule stated in prose in `claims_for`.
    """
    from akashi.domain.verdict import Standing, Verdict

    segments = report.assessment.segments
    return sum(
        1
        if one.verdict is Verdict.UNBEARING
        else sum(
            1
            for particular in one.particulars
            if particular.standing is Standing.FLOATING and particular.contradiction is None
        )
        for one in segments
    )


def test_more_claims_than_the_cap_are_counted_even_though_they_are_not_sent() -> None:
    """The loop cannot return early: the total is the whole point, and a loop
    that stops cannot report what it stopped short of."""
    report = many_floating()
    sent, total = claims_and_total(report)
    assert len(sent) == MAX_CLAIMS
    assert total == expected_total(report)
    assert total > MAX_CLAIMS * 2, "this answer no longer overflows the cap by enough to matter"
    assert len(claims_for(report)) == len(sent)


def test_the_shortfall_becomes_a_receipt() -> None:
    report = many_floating()
    sent, total = claims_and_total(report)
    assert total == expected_total(report), "the receipt would be self-consistent and wrong"
    [bound] = from_unsent_claims(len(sent), total, MAX_CLAIMS)
    assert str(total) in bound.because
    assert str(total - len(sent)) in bound.because
    assert "not judged by anything" in bound.because


def test_no_shortfall_produces_no_receipt() -> None:
    assert from_unsent_claims(3, 3, MAX_CLAIMS) == ()


def test_the_command_line_puts_it_on_the_report(tmp_path: Path) -> None:
    """Where the shortfall is actually produced. Judging happens at the
    composition root, so the receipt has to be added there too."""
    import contextlib

    from akashi.interfaces.cli.main import main
    from akashi.ports.judge import Judgement, Standing

    class Stub:
        model = "stub@1"

        def judge(self, claims: object, evidence: object) -> tuple[Judgement, ...]:
            assert isinstance(claims, tuple | list)
            return tuple(
                Judgement(
                    segment_id=one.segment_id,
                    particular=one.particular,
                    standing=Standing.UNCLEAR,
                    because="the stub says so",
                    model="stub@1",
                )
                for one in claims
            )

    answer = tmp_path / "answer.txt"
    answer.write_text(
        "".join(f"Item {n} weighs {n}.{n % 10}kg. " for n in range(1, 101)), encoding="utf-8"
    )
    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps({"answer": answer.read_text(encoding="utf-8"), "contexts": ["Nothing."]}),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"

    import sys

    cli: Any = sys.modules["akashi.interfaces.cli.main"]
    original = cli._judge
    cli._judge = lambda named: Stub()
    try:
        with out.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
            main(["audit", "--contexts", str(sample), "--judge", "stub", "--json"])
    finally:
        cli._judge = original

    body = json.loads(out.read_text(encoding="utf-8"))
    names = [one["name"] for one in body["bounds"]]
    assert "MAX_CLAIMS" in names, f"no shortfall recorded; bounds were {names}"
    assert len(body["judged"]) == MAX_CLAIMS


# --- the shape the receipt takes ---------------------------------------------


def test_a_bound_appears_both_as_prose_and_as_structure() -> None:
    """A person reads the sentence. A consumer deciding whether to trust a share
    needs to test for truncation without matching on prose, and prose is the
    thing most likely to be reworded."""
    digits = "1" * 300
    body = evaluate(answer=f"value {digits}", contexts=["x"]).to_dict()
    [structured] = body["bounds"]
    assert structured["name"] == "MAX_RUN"
    assert structured["limit"] == MAX_RUN
    assert structured["because"] in bound_lines(body, "MAX_RUN")[0]


def test_the_structured_form_is_in_the_published_contract() -> None:
    """Otherwise a consumer validating against the schema would reject the
    reports that most need reading."""

    schema = _schema()
    assert "bounds" in schema["properties"]
    assert "bounds" in schema["required"]


def test_a_report_with_a_bound_still_validates() -> None:
    import jsonschema

    digits = "1" * 300
    body = evaluate(answer=f"value {digits}", contexts=["x"]).to_dict()
    assert body["bounds"]
    jsonschema.validate(body, _schema())


def test_a_bound_that_does_not_say_what_it_left_out_is_refused() -> None:
    """The silence this module exists to remove, arriving as an empty string."""
    with pytest.raises(ValueError, match="does not say what it left out"):
        Bound(name="MAX_RUN", limit=256, because="")


def test_bounds_do_not_move_the_report_id() -> None:
    """A bound is a consequence of the input, not a second input, so `recheck`
    re-derives the same id from the same answer and package."""
    digits = "1" * 300
    first = evaluate(answer=f"value {digits}", contexts=["x"]).report
    second = evaluate(answer=f"value {digits}", contexts=["x"]).report
    assert first.bounds
    assert first.report_id == second.report_id
