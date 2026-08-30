"""Floors, and the rule that stops them becoming targets.

A gate set at today's number makes every honest experiment a build failure: any
change that trades a point of one metric for five of another goes red, so the
change does not get made, and the pinned number becomes the only thing anyone
optimises. `mamori`'s ADR-0023 records what that costs.

So the interesting tests here are not "does the gate fire" but "can a floor be
written that has quietly become a target".
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from akashi.evaluation.floors import FLOORS, Breach, Floor, check
from akashi.interfaces.cli.main import AUDITED, BREACHED, main

CASES = Path(__file__).parent / "cases"
MARKED = Path(__file__).parent / "marked"


# --- A floor is not a target -------------------------------------------------


def test_a_floor_at_the_measured_score_is_refused() -> None:
    """The rule the whole file exists for, enforced at construction rather than
    left to whoever writes the next one."""
    with pytest.raises(ValueError, match="every honest experiment a build failure"):
        Floor(
            metric="x",
            measured=1.0,
            measured_on="2026-08-30",
            at_least=1.0,
            why="because",
        )


def test_a_ceiling_at_the_measured_score_is_refused() -> None:
    with pytest.raises(ValueError, match="at or below the measured"):
        Floor(metric="x", measured=0.35, measured_on="2026-08-30", at_most=0.35, why="because")


def test_a_floor_at_the_measured_score_is_allowed_when_it_is_an_invariant() -> None:
    """Refusing a protected response is not a quality metric. There is no
    honest experiment that trades it away, so the bound is the measurement and
    it says so."""
    floor = Floor(
        metric="refusals",
        measured=1.0,
        measured_on="2026-08-30",
        at_least=1.0,
        is_invariant=True,
        why="ADR-0008",
    )
    assert floor.is_invariant
    assert "invariant" in floor.describe()


def test_a_floor_must_bound_exactly_one_side() -> None:
    with pytest.raises(ValueError, match="one side"):
        Floor(metric="x", measured=0.5, measured_on="d", why="w")
    with pytest.raises(ValueError, match="one side"):
        Floor(metric="x", measured=0.5, measured_on="d", at_least=0.1, at_most=0.9, why="w")


def test_a_bound_with_no_reason_is_refused() -> None:
    """A number nobody can move. The reason is what a future contributor argues
    against when they want to change it."""
    with pytest.raises(ValueError, match="no reason"):
        Floor(metric="x", measured=1.0, measured_on="d", at_least=0.5)


# --- The shipped floors ------------------------------------------------------


def test_every_shipped_floor_has_room_or_declares_itself_an_invariant() -> None:
    for floor in FLOORS:
        if floor.is_invariant:
            continue
        if floor.at_least is not None:
            assert floor.at_least < floor.measured, floor.metric
        else:
            assert floor.at_most > floor.measured, floor.metric


def test_every_shipped_floor_names_the_date_it_was_measured() -> None:
    """A floor with no date is a floor nobody can tell has gone stale."""
    for floor in FLOORS:
        assert floor.measured_on, floor.metric


def test_the_two_invariants_are_the_two_that_should_be() -> None:
    """ADR-0003 and ADR-0008. Everything else is a quality metric and has room."""
    assert {floor.metric for floor in FLOORS if floor.is_invariant} == {
        "refusals",
        "reproducibility",
    }


def test_the_false_positive_bound_is_the_tightest() -> None:
    """A floating finding that is wrong is worse than no finding: it decides
    whether a reader keeps reading the reports."""
    ceilings = {floor.metric: floor.at_most for floor in FLOORS if floor.at_most is not None}
    assert ceilings["false positives"] == min(ceilings.values())


@pytest.mark.parametrize(
    "metric",
    ["declared misses passed", "acknowledged false positives", "source localisation"],
)
def test_the_numbers_akashi_wants_to_move_are_not_gated(metric: str) -> None:
    """Gating ``declared misses passed`` would forbid akashi from ever catching
    a cross-document stitch, which is a goal. Gating a number you want to move
    is how a measurement becomes a cage."""
    assert metric not in {floor.metric for floor in FLOORS}


# --- Checking -----------------------------------------------------------------


def test_a_metric_through_its_floor_is_a_breach() -> None:
    breaches = check({"fabrication recall": 0.5})
    assert len(breaches) == 1
    assert "fabrication recall" in breaches[0].describe()
    assert "50%" in breaches[0].describe()


def test_a_metric_over_its_ceiling_is_a_breach() -> None:
    breaches = check({"false positives": 0.20})
    assert len(breaches) == 1
    assert "above" in breaches[0].describe()


def test_a_metric_with_no_value_is_neither_a_breach_nor_a_pass() -> None:
    """A rate over nothing has not scored, and treating it as a failure would
    make an empty corpus look like a regression."""
    assert check({"fabrication recall": None}) == []
    assert check({}) == []


def test_a_breach_says_why_the_bound_is_there() -> None:
    """So that a contributor reading a red build knows what the number is for
    rather than only that it moved."""
    breach = check({"reproducibility": 0.9})[0]
    assert "ADR-0003" in breach.describe()


def test_the_measured_run_breaches_nothing() -> None:
    """The floors were set against this run. If this fails, either something
    regressed or the floors were set too close to the measurement."""
    from akashi.evaluation import load_cases, run
    from akashi.evaluation.marked import load_marked, score_extraction
    from akashi.evaluation.rendering import measured_values
    from akashi.infrastructure.languages import DEFAULT

    breakdown, _ = run(load_cases(CASES), DEFAULT)
    overall, by_language, _ = score_extraction(load_marked(MARKED), DEFAULT)
    breaches = check(measured_values(breakdown, (overall, by_language)))
    assert breaches == [], [breach.describe() for breach in breaches]


# --- The gate ----------------------------------------------------------------


def test_the_gate_passes_on_the_current_corpus(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["eval", "--cases", str(CASES), "--marked", str(MARKED), "--gate"])
    assert code == AUDITED
    assert capsys.readouterr().err == ""


def test_the_floors_print_beside_the_scores_they_were_set_against(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The gap is the point. A floor that has crept up to meet its measurement
    has become a target, and printing the two side by side is what makes that
    visible before it happens."""
    main(["eval", "--cases", str(CASES), "--marked", str(MARKED)])
    printed = capsys.readouterr().out
    assert "Floors" in printed
    assert "floor set against" in printed
    assert "invariant" in printed


def test_the_gate_is_off_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    """Reading the numbers and failing on them are different things, and a
    developer looking at a score should not have to think about an exit code."""
    assert main(["eval", "--cases", str(CASES), "--marked", str(MARKED)]) == AUDITED


def test_the_json_carries_the_breaches_and_the_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["eval", "--cases", str(CASES), "--marked", str(MARKED), "--json"])
    body = json.loads(capsys.readouterr().out)["floors"]
    assert body["breaches"] == []
    assert body["measured"]["fabrication recall"] == 1.0


def test_a_breach_is_named_on_stderr_as_well(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build log is read from the end, and the reason a gate went red should
    not need scrolling for."""
    # ``import akashi.interfaces.cli.main`` binds the *function*: the package
    # __init__ re-exports it and shadows the submodule of the same name.
    cli = importlib.import_module("akashi.interfaces.cli.main")
    monkeypatch.setattr(cli, "check_floors", lambda measured: [Breach(floor=FLOORS[0], value=0.1)])
    code = main(["eval", "--cases", str(CASES), "--marked", str(MARKED), "--gate"])
    assert code == BREACHED
    assert "akashi: fabrication recall" in capsys.readouterr().err


def test_a_breach_without_the_gate_prints_but_does_not_fail(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = importlib.import_module("akashi.interfaces.cli.main")
    monkeypatch.setattr(cli, "check_floors", lambda measured: [Breach(floor=FLOORS[0], value=0.1)])
    assert main(["eval", "--cases", str(CASES), "--marked", str(MARKED)]) == AUDITED
    assert "bound breached" in capsys.readouterr().out
