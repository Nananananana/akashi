"""The measurement, and the things it must not quietly become.

Every number `akashi eval` prints is a count over a count. What these tests
check is that the counting is right, that the three groups stay apart, and that
the caveats travel with the figures -- because a rate detached from its
denominator and its note is a rate a reader supplies a generous reading for.

The scores themselves are pinned in `test_floors.py` when there are floors to
pin. What is here is the instrument.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from akashi.evaluation import Rate, Score, load_cases, run
from akashi.evaluation.case import Split
from akashi.evaluation.metrics import Tally
from akashi.evaluation.rendering import as_dict, as_text
from akashi.infrastructure.languages import DEFAULT
from akashi.interfaces.cli.main import AUDITED, REFUSED, main

CASES = Path(__file__).parent / "cases"


@pytest.fixture(scope="module")
def measured() -> tuple[object, list[str]]:
    cases = load_cases(CASES, splits=(Split.TRAIN,))
    return run(cases, DEFAULT)


# --- A rate is a count over a count ------------------------------------------


def test_a_rate_over_nothing_has_no_share() -> None:
    """Not 0.0 and not 1.0. A rate over nothing has not scored well and has not
    scored badly, and a number there would be read as one of the two."""
    assert Rate("nothing", 0, 0).share is None
    assert "nothing to measure" in Rate("nothing", 0, 0).describe()


def test_a_rate_prints_its_counts_and_not_only_its_share() -> None:
    assert Rate("recall", 3, 4).describe() == "recall: 3 of 4 (75%)"


def test_rates_add_up() -> None:
    assert (Rate("r", 1, 2) + Rate("r", 3, 4)) == Rate("r", 4, 6)


def test_every_rate_carries_a_note_about_what_it_does_not_say() -> None:
    score = Score(Tally())
    for rate in score.rates:
        assert rate.note, f"{rate.name} carries no note"


# --- The run -----------------------------------------------------------------


def test_the_corpus_runs(measured: tuple[object, list[str]]) -> None:
    breakdown, _ = measured
    assert breakdown.overall.tally.cases == 30  # type: ignore[attr-defined]
    assert breakdown.overall.tally.segments > 0  # type: ignore[attr-defined]


def test_the_notes_name_the_case_that_disagreed(
    measured: tuple[object, list[str]],
) -> None:
    """A rate says how often something went wrong; the notes say which. A
    measurement that cannot be followed back to a case cannot be acted on."""
    _, notes = measured
    for note in notes:
        assert ":" in note, f"{note!r} names no case"


def test_the_breakdown_cuts_by_language_and_by_kind(
    measured: tuple[object, list[str]],
) -> None:
    """An aggregate hides that extraction is strong on Japanese figures and
    weak on English legal citations, and those are different problems."""
    breakdown, _ = measured
    assert set(breakdown.by_language) == {"en", "ja", "zh"}  # type: ignore[attr-defined]
    assert "digit_drift" in breakdown.by_kind  # type: ignore[attr-defined]


def test_a_kind_is_scored_over_its_own_plants(
    measured: tuple[object, list[str]],
) -> None:
    """Not over whole cases. A kind that appears in every case would otherwise
    show the same denominator as one that appears in three."""
    breakdown, _ = measured
    drift = breakdown.by_kind["digit_drift"]  # type: ignore[attr-defined]
    stitch = breakdown.by_kind["cross_document_stitch"]  # type: ignore[attr-defined]
    assert drift.fabrication_recall.total != stitch.declared_miss_rate.total


def test_declared_misses_are_counted_as_passed_rather_than_failed(
    measured: tuple[object, list[str]],
) -> None:
    """ADR-0004 says akashi cannot see a cross-document stitch. Passing one is
    correct behaviour, and the count is published rather than improved."""
    breakdown, _ = measured
    rate = breakdown.by_kind["cross_document_stitch"].declared_miss_rate  # type: ignore[attr-defined]
    assert rate.total > 0
    assert rate.share == 1.0


def test_an_acknowledged_false_positive_is_not_counted_as_a_false_positive(
    measured: tuple[object, list[str]],
) -> None:
    """A correct sum is in neither source, so it floats. That is on
    STANDING_LIMITS, and it gets its own number rather than being hidden in the
    false-positive rate."""
    breakdown, _ = measured
    derived = breakdown.by_kind["derived_value"]  # type: ignore[attr-defined]
    assert derived.acknowledged_rate.total > 0
    assert derived.false_positive_rate.total == 0


def test_a_protected_case_is_scored_on_its_refusal(
    measured: tuple[object, list[str]],
) -> None:
    breakdown, _ = measured
    rate = breakdown.by_kind["placeholder_residue"].refusal_rate  # type: ignore[attr-defined]
    assert rate.total > 0
    assert rate.share == 1.0


def test_source_localisation_is_measured_even_though_it_cannot_yet_be_hit(
    measured: tuple[object, list[str]],
) -> None:
    """A metric introduced at the same time as the feature it scores measures
    nothing. This is the baseline v0.4 has to move."""
    breakdown, _ = measured
    rate = breakdown.overall.source_localisation  # type: ignore[attr-defined]
    assert rate.total > 0
    assert rate.hit == 0
    assert "v0.4" in rate.note


def test_verdict_correctness_is_over_what_a_plant_should_ultimately_carry(
    measured: tuple[object, list[str]],
) -> None:
    """A digit drift should read ``contradicted``, and v0.1 says ``floating``.
    The gap is a number that should rise when v0.4 ships, not a failure now."""
    breakdown, _ = measured
    rate = breakdown.overall.verdict_correctness  # type: ignore[attr-defined]
    assert 0 < rate.hit < rate.total


def test_the_held_out_split_is_not_in_the_default_run() -> None:
    default = load_cases(CASES, splits=(Split.TRAIN,))
    both = load_cases(CASES, splits=(Split.TRAIN, Split.HELD_OUT))
    assert len(both) > len(default)


def test_running_twice_gives_the_same_numbers() -> None:
    """ADR-0003 reaches the measurement. A score that moved between runs would
    be a score nobody could compare to the one before it."""
    cases = load_cases(CASES, splits=(Split.TRAIN,), tier="ci")
    first, _ = run(cases, DEFAULT)
    second, _ = run(cases, DEFAULT)
    assert as_dict(first, [], cases=len(cases)) == as_dict(second, [], cases=len(cases))


# --- Rendering ---------------------------------------------------------------


def test_the_text_keeps_the_three_groups_apart(
    measured: tuple[object, list[str]],
) -> None:
    breakdown, notes = measured
    printed = as_text(breakdown, notes, cases=30)  # type: ignore[arg-type]
    for group in ("Detection", "Attribution", "Integrity", "Coverage"):
        assert group in printed
    assert printed.index("Detection") < printed.index("Attribution")


def test_the_text_ends_with_what_the_numbers_do_not_say(
    measured: tuple[object, list[str]],
) -> None:
    breakdown, notes = measured
    printed = as_text(breakdown, notes, cases=30)  # type: ignore[arg-type]
    assert "What these numbers do not say" in printed
    assert "The corpus is generated" in printed
    assert printed.rindex("What these numbers do not say") > printed.index("Detection")


def test_every_printed_rate_shows_its_denominator(
    measured: tuple[object, list[str]],
) -> None:
    """A share on its own is a share a reader supplies a generous denominator
    for."""
    breakdown, notes = measured
    for line in as_text(breakdown, notes, cases=30).splitlines():  # type: ignore[arg-type]
        if line.startswith("  ") and "%" in line and "of" not in line:
            assert "/" in line, f"{line!r} prints a share with no counts"


def test_the_json_carries_the_counts_and_not_only_the_shares(
    measured: tuple[object, list[str]],
) -> None:
    breakdown, notes = measured
    body = as_dict(breakdown, notes, cases=30)  # type: ignore[arg-type]
    recall = body["overall"]["fabrication recall"]
    assert set(recall) == {"hit", "total", "share"}


def test_the_json_carries_the_notes(measured: tuple[object, list[str]]) -> None:
    breakdown, notes = measured
    assert as_dict(breakdown, notes, cases=30)["notes"] == notes  # type: ignore[arg-type]


# --- The command line --------------------------------------------------------


def test_eval_runs_from_the_command_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["eval", "--cases", str(CASES)]) == AUDITED
    printed = capsys.readouterr().out
    assert printed.startswith("akashi eval — ")
    assert "fabrication recall" in printed


def test_eval_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    main(["eval", "--cases", str(CASES), "--json"])
    body = json.loads(capsys.readouterr().out)
    assert body["cases"] > 0
    assert "fabrication recall" in body["overall"]


def test_eval_can_read_the_held_out_split_when_asked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["eval", "--cases", str(CASES), "--json"])
    default = json.loads(capsys.readouterr().out)["cases"]
    main(["eval", "--cases", str(CASES), "--held-out", "--json"])
    both = json.loads(capsys.readouterr().out)["cases"]
    assert both > default


def test_eval_can_run_one_tier(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["eval", "--cases", str(CASES), "--tier", "ci", "--json"]) == AUDITED
    assert json.loads(capsys.readouterr().out)["cases"] > 0


def test_a_tier_nothing_is_in_is_a_refusal(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["eval", "--cases", str(CASES), "--tier", "nightly"]) == REFUSED
    assert "no cases matched" in capsys.readouterr().err


def test_a_missing_corpus_is_a_refusal_and_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["eval", "--cases", str(tmp_path / "nowhere")]) == REFUSED
    error = capsys.readouterr().err
    assert error.startswith("akashi: ")
    assert "Traceback" not in error
