"""The floors, and the distance between each floor and what was measured.

**Floors, not targets.** A gate set at today's number makes every honest
experiment a build failure: any change that trades a point of one metric for
five of another goes red, so the change does not get made, and the number that
was pinned becomes the only thing anyone optimises. `mamori`'s ADR-0023 records
what that costs.

So every floor here carries the score it was set against and the date it was
measured, and the renderer prints both. **The gap is the point.** A floor that
has crept up to meet its measurement is a floor that has become a target, and
seeing the two side by side is what makes that visible before it happens.

**Two of them are not floors at all**, and they say so. Refusing a protected
response and producing the same report twice are invariants (ADR-0003,
ADR-0008): a drop is a defect, not an experiment, and there is no honest
experiment that trades either of them away.

**Three metrics are deliberately ungated.** *Declared misses passed* would
forbid akashi from ever catching a cross-document stitch, which is a goal.
*Acknowledged false positives* would forbid the arithmetic checking that would
remove them. *Source localisation* is structurally zero until v0.4. Gating a
number you want to move is how a measurement becomes a cage.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FLOORS", "Breach", "Floor", "check"]


@dataclass(frozen=True, slots=True)
class Floor:
    """One bound, with the measurement it was set against."""

    metric: str
    #: What the score was on ``measured_on``. Printed beside the bound so the
    #: gap is visible.
    measured: float
    measured_on: str
    at_least: float | None = None
    at_most: float | None = None
    why: str = ""
    #: True where the bound *is* the measurement on purpose: an invariant
    #: rather than a quality metric.
    is_invariant: bool = False

    def __post_init__(self) -> None:
        if (self.at_least is None) == (self.at_most is None):
            raise ValueError(f"{self.metric}: a floor bounds one side, not both or neither")
        if not self.why:
            raise ValueError(f"{self.metric}: a bound with no reason is a number nobody can move")
        if not self.is_invariant and self.at_least is not None and self.at_least >= self.measured:
            raise ValueError(
                f"{self.metric}: the floor {self.at_least} is at or above the measured "
                f"{self.measured}. A gate set at today's number makes every honest "
                f"experiment a build failure. Set it below, or mark it an invariant."
            )
        if not self.is_invariant and self.at_most is not None and self.at_most <= self.measured:
            raise ValueError(
                f"{self.metric}: the ceiling {self.at_most} is at or below the measured "
                f"{self.measured}"
            )

    @property
    def bound(self) -> float:
        return self.at_least if self.at_least is not None else self.at_most  # type: ignore[return-value]

    def holds(self, value: float) -> bool:
        if self.at_least is not None:
            return value >= self.at_least
        return value <= self.at_most  # type: ignore[operator]

    def describe(self) -> str:
        direction = "at least" if self.at_least is not None else "at most"
        room = "invariant" if self.is_invariant else f"measured {self.measured:.0%}"
        return f"{self.metric}: {direction} {self.bound:.0%} ({room}, {self.measured_on})"


@dataclass(frozen=True, slots=True)
class Breach:
    """A metric that fell through its floor."""

    floor: Floor
    value: float

    def describe(self) -> str:
        direction = "below" if self.floor.at_least is not None else "above"
        return (
            f"{self.floor.metric}: {self.value:.0%} is {direction} the "
            f"{self.floor.bound:.0%} bound - {self.floor.why}"
        )


#: Set on 2026-08-30 and re-measured the same day, twice: once when the
#: structural name rules shipped (extraction recall over everything marked went
#: 91% -> 95%, unbearing 35% -> 30%) and once when ``contradicted`` did
#: (verdict correctness 35% -> 59%, source localisation 0% -> 36%).
#:
#: Every bound below is where it was. ``verdict correctness`` is the clearest
#: case: its score rose 24 points and its floor did not move, because nothing
#: about what akashi can afford to lose changed when it got better.
#:
#: **Moving a bound because a score improved is how a floor becomes a target.**
#: The ``measured`` figures below are updated because they are a record of what
#: was seen; the bounds are not, because nothing about what akashi can afford to
#: lose has changed.
FLOORS: tuple[Floor, ...] = (
    Floor(
        metric="fabrication recall",
        measured=1.0,
        measured_on="2026-08-30",
        at_least=0.90,
        why="a planted hallucination akashi is expected to catch and did not",
    ),
    Floor(
        metric="false positives",
        measured=0.0,
        measured_on="2026-08-30",
        at_most=0.05,
        why=(
            "a floating finding that is wrong is worse than no finding: it is what "
            "decides whether a reader keeps reading the reports. The tightest bound here"
        ),
    ),
    Floor(
        metric="verdict correctness",
        measured=0.59,
        measured_on="2026-08-30",
        at_least=0.25,
        why=(
            "the verdict a plant should ultimately carry. It was 35% and is 59% now "
            "that contradicted ships, and the bound stays at 25% on purpose: a floor "
            "raised every time a score rises is a target wearing a floor's name"
        ),
    ),
    Floor(
        metric="source misdirection",
        measured=0.0,
        measured_on="2026-08-30",
        at_most=0.05,
        why=(
            "a source named that is not the value replaced. Worse than naming none: it "
            "sends a reader to a line that is correct and tells them it is not. With "
            "twelve localisations, one of these is 8% and breaches -- which is the "
            "intended strictness, not an accident of the sample size. Note which of "
            "the pair is gated: source *localisation* is not, because 27 of its 33 "
            "were given up in one afternoon to hold this number at zero, and a floor "
            "under it would have forbidden the trade"
        ),
    ),
    Floor(
        metric="refusals",
        measured=1.0,
        measured_on="2026-08-30",
        at_least=1.0,
        is_invariant=True,
        why=(
            "ADR-0008. Auditing a protected response reports every honest particular as "
            "fabricated. There is no experiment that trades this away"
        ),
    ),
    Floor(
        metric="reproducibility",
        measured=1.0,
        measured_on="2026-08-30",
        at_least=1.0,
        is_invariant=True,
        why="ADR-0003. Same inputs, same report. A drop here is a defect, not a trade",
    ),
    Floor(
        metric="extraction recall on claimed kinds",
        measured=0.95,
        measured_on="2026-08-30",
        at_least=0.85,
        why=(
            "whether akashi finds what it says it finds. A particular not extracted is "
            "never checked, and the segment holding it still comes back grounded"
        ),
    ),
    Floor(
        metric="extraction precision",
        measured=1.0,
        measured_on="2026-08-30",
        at_least=0.90,
        why="a particular nobody would call one is noise on every report that carries it",
    ),
    Floor(
        metric="unbearing segments",
        measured=0.30,
        measured_on="2026-08-30",
        at_most=0.55,
        why=(
            "how much of a realistic answer akashi has nothing to say about. Above half "
            "and the falsification condition in proposals/0001 section 10 has fired"
        ),
    ),
)


def check(measured: dict[str, float | None]) -> list[Breach]:
    """Every floor a measurement fell through, in the order the floors are declared.

    A metric with no value is not a breach and not a pass: a rate over nothing
    has not scored, and treating it as a failure would make an empty corpus
    look like a regression.
    """
    breaches: list[Breach] = []
    for floor in FLOORS:
        value = measured.get(floor.metric)
        if value is None:
            continue
        if not floor.holds(value):
            breaches.append(Breach(floor=floor, value=value))
    return breaches
