"""What a run over the corpus establishes, as arithmetic.

ADR-0010. No grader, no rubric, no model: every number here is a count divided
by another count, and both counts are visible.

**Six rates, and they are not one rate.** A single "accuracy" would average
together things that trade against each other -- catching more fabrications by
flagging more of everything -- and hide the trade in the mean. Kept apart, the
false-positive rate is free to be the tightest of the six, which it should be:
a floating finding that is wrong is worse than no finding, because it is what
decides whether a reader keeps reading the reports.

**Three of them are about akashi's silence rather than its findings.** Declared
misses passed, acknowledged false positives, and unattributed floats. None of
those is a score to improve; they are quantities to publish. "akashi passed 45
of 45 planted cross-document stitches" is the most useful line the measurement
document will carry, and it only exists because the corpus plants things akashi
is known not to catch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Rate", "Score", "Tally"]


@dataclass(frozen=True, slots=True)
class Rate:
    """A count over a count, and never one without the other.

    ``None`` for the share when the denominator is zero. Not ``0.0`` and not
    ``1.0``: a rate over nothing has not scored well and has not scored badly,
    and a number there would be read as one of the two.
    """

    name: str
    hit: int = 0
    total: int = 0
    #: What this number does *not* say. Printed beside it, always.
    note: str = ""

    @property
    def share(self) -> float | None:
        return self.hit / self.total if self.total else None

    def describe(self) -> str:
        if self.share is None:
            return f"{self.name}: nothing to measure"
        return f"{self.name}: {self.hit} of {self.total} ({self.share:.0%})"

    def __add__(self, other: Rate) -> Rate:
        return Rate(
            name=self.name,
            hit=self.hit + other.hit,
            total=self.total + other.total,
            note=self.note or other.note,
        )


@dataclass(slots=True)
class Tally:
    """The counters a run fills in, before they become rates."""

    #: Planted hallucinations akashi was expected to flag, and did.
    fabrications_found: int = 0
    fabrications_planted: int = 0
    #: Controls -- not hallucinations, not expected to be flagged -- that were.
    false_positives: int = 0
    controls_planted: int = 0
    #: Not hallucinations, expected to be flagged, and akashi says why on every
    #: report. A correct sum is in neither source, so it floats.
    acknowledged_found: int = 0
    acknowledged_planted: int = 0
    #: Hallucinations ADR-0004 says akashi cannot see. Passing them is correct
    #: behaviour and the count is published rather than improved.
    declared_passed: int = 0
    declared_planted: int = 0
    #: Flagged plants whose segment carries the verdict the plant expects.
    verdicts_right: int = 0
    verdicts_checked: int = 0
    #: Flagged plants whose reported source span is the labelled one.
    located: int = 0
    locatable: int = 0
    #: Sources akashi named that are not the one the plant replaced -- a source
    #: named for a value that replaced nothing included. This is the number
    #: that governs whether ``contradicted`` may ship at all: a wrong location
    #: is worse than none, because it sends a reader to the wrong line and
    #: tells them the answer is a corruption of it.
    misdirected: int = 0
    localisations: int = 0
    #: Cases that had to be refused, and were.
    refused: int = 0
    refusals_due: int = 0
    #: Cases whose second audit produced the same report as the first.
    reproduced: int = 0
    cases: int = 0
    #: Floating particulars that overlap no plant at all. Not attributable to a
    #: label, and the honest measure of the noise a reader actually sees.
    unattributed_floats: int = 0
    #: Plants the segmenter cut in two. A segmentation disagreement, counted
    #: where it shows up rather than inferred from a score that moved.
    plants_split: int = 0
    #: Coverage, summed. The share of segments akashi has nothing to say about
    #: is one of the three numbers that can falsify ADR-0004.
    segments: int = 0
    unbearing: int = 0
    unexamined: int = 0
    particulars: int = 0

    def add(self, other: Tally) -> None:
        for name in self.__slots__:
            setattr(self, name, getattr(self, name) + getattr(other, name))


@dataclass(frozen=True, slots=True)
class Score:
    """A tally, read as rates."""

    tally: Tally
    label: str = "all"

    @property
    def fabrication_recall(self) -> Rate:
        return Rate(
            "fabrication recall",
            self.tally.fabrications_found,
            self.tally.fabrications_planted,
            note="planted hallucinations akashi is expected to catch",
        )

    @property
    def false_positive_rate(self) -> Rate:
        return Rate(
            "false positives",
            self.tally.false_positives,
            self.tally.controls_planted,
            note="controls flagged anyway; lower is better and this is the tightest floor",
        )

    @property
    def acknowledged_rate(self) -> Rate:
        return Rate(
            "acknowledged false positives",
            self.tally.acknowledged_found,
            self.tally.acknowledged_planted,
            note="correct values akashi floats because it does no arithmetic",
        )

    @property
    def declared_miss_rate(self) -> Rate:
        return Rate(
            "declared misses passed",
            self.tally.declared_passed,
            self.tally.declared_planted,
            note="hallucinations ADR-0004 says akashi cannot see; passing them is correct",
        )

    @property
    def verdict_correctness(self) -> Rate:
        return Rate(
            "verdict correctness",
            self.tally.verdicts_right,
            self.tally.verdicts_checked,
            note="the verdict a plant should ultimately carry, not the one v0.1 emits",
        )

    @property
    def source_localisation(self) -> Rate:
        return Rate(
            "source localisation",
            self.tally.located,
            self.tally.locatable,
            note="finding the value that was replaced; ships with contradicted in v0.4",
        )

    @property
    def source_misdirection(self) -> Rate:
        return Rate(
            "source misdirection",
            self.tally.misdirected,
            self.tally.localisations,
            note="sources named that are not the value replaced; lower is better and "
            "this is why contradicted is narrow",
        )

    @property
    def refusal_rate(self) -> Rate:
        return Rate(
            "refusals",
            self.tally.refused,
            self.tally.refusals_due,
            note="protected responses refused rather than audited into nonsense",
        )

    @property
    def reproducibility(self) -> Rate:
        return Rate(
            "reproducibility",
            self.tally.reproduced,
            self.tally.cases,
            note="the same case audited twice, byte for byte",
        )

    @property
    def unbearing_share(self) -> Rate:
        return Rate(
            "unbearing segments",
            self.tally.unbearing,
            self.tally.segments,
            note="segments akashi looked at and had nothing to check in",
        )

    @property
    def rates(self) -> tuple[Rate, ...]:
        return (
            self.fabrication_recall,
            self.false_positive_rate,
            self.acknowledged_rate,
            self.declared_miss_rate,
            self.verdict_correctness,
            self.source_localisation,
            self.source_misdirection,
            self.refusal_rate,
            self.reproducibility,
            self.unbearing_share,
        )

    def by_name(self) -> dict[str, Rate]:
        return {rate.name: rate for rate in self.rates}


@dataclass(frozen=True, slots=True)
class Breakdown:
    """The same score, cut by language and by plant kind.

    An aggregate hides that extraction is strong on Japanese figures and weak
    on English legal citations, and those are different problems.
    """

    overall: Score
    by_language: dict[str, Score] = field(default_factory=dict)
    by_kind: dict[str, Score] = field(default_factory=dict)
