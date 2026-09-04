"""The account of what akashi did not check, and the denominator it did.

ADR-0005. akashi's coverage is partial by construction, and partial coverage
reported as a single number reads as total coverage. A report that says
``94% grounded`` and stops has told the reader that 6% of the answer is
questionable. What it has actually established is that 94% of the *extracted
particulars* resolved -- which says nothing about the segments that had no
particulars in them, nothing about the kinds no rule covers, and nothing about
whether a true sentence was assembled from two unrelated documents.

The failure mode is specific and it is the one that gets people hurt: a
compliance officer sees a high score, signs off, and the sentence that mattered
was one akashi never looked at.

So three things travel with every set of findings, and all three are required:

- ``unchecked`` -- the spans akashi did not examine, each with the rule that
  caused it. Empty only when nothing was skipped.
- ``coverage`` -- the denominators, in plain numbers.
- ``STANDING_LIMITS`` -- what the method cannot do, on the artefact rather than
  in the documentation. The artefact travels; the documentation does not.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .particular import ParticularKind
from .span import Span
from .verdict import CheckedSegment, Standing, Verdict

__all__ = [
    "STANDING_LIMITS",
    "Assessment",
    "Coverage",
    "SkipRule",
    "Skipped",
    "assess",
]


#: The limits of the method, restated on every artefact. Fixed wording rather
#: than left to the caller: this is the part a reader is most likely to skip and
#: most needs, and a caller who could reword it could soften it.
STANDING_LIMITS: tuple[str, ...] = (
    "A grounded particular is a statement about strings, not about truth. A model "
    "can quote a source perfectly and reason from it badly.",
    "A sentence assembled from two documents, each quoted correctly, is reported "
    "grounded. akashi does not check that the parts belong together.",
    "A meaning reversed without changing any particular is not detected.",
    "A number correctly derived from grounded numbers is reported floating, "
    "because it is not in the sources. akashi does not do arithmetic.",
    "A name with no title, honorific or legal form beside it is not extracted "
    "and so is never checked. akashi reads structure, not names.",
    "A floating particular is named as contradicting a source only where the "
    "answer kept that source's digits exactly. A figure whose digits differ "
    "from every source figure is reported without one, because an invention, a "
    "calculation and a corruption look the same from here.",
)


class SkipRule(Enum):
    """Why a span was not examined.

    Every rule here is produced by something. A rule defined for a detector
    that does not exist yet would be a promise on an artefact, and an artefact
    is the wrong place for a promise.
    """

    NOT_PROSE = "not_prose"
    NO_PARTICULARS = "no_particulars"
    PROTECTED = "protected"


@dataclass(frozen=True, slots=True)
class Skipped:
    """One span akashi did not check, and why."""

    span: Span
    rule: SkipRule
    reason: str
    segment_id: str = ""

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError(
                f"a {self.rule.value} skip with no reason is a silent gap; the rule says "
                f"which check was not run and the reason says why this span met it"
            )


@dataclass(frozen=True, slots=True)
class Coverage:
    """The denominators, published so a reader cannot assume the wrong one.

    A ratio whose denominator is not visible is a ratio a reader will assume
    the wrong denominator for, and they will assume the generous one.
    """

    segments: int = 0
    #: Examined, and holding at least one particular.
    bearing: int = 0
    #: Examined, and holding nothing to check. Not a pass.
    unbearing: int = 0
    #: Not examined at all.
    unexamined: int = 0
    particulars: int = 0
    checked: int = 0
    #: Kinds in the vocabulary that no loaded rule finds. A blind spot that is
    #: not named reads as an absence of findings.
    kinds_not_extracted: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        counted = self.bearing + self.unbearing + self.unexamined
        if counted != self.segments:
            raise ValueError(
                f"{self.segments} segments, but {counted} accounted for "
                f"({self.bearing} bearing, {self.unbearing} unbearing, "
                f"{self.unexamined} unexamined). Every segment is in exactly one."
            )
        if self.checked > self.particulars:
            raise ValueError(
                f"{self.checked} particulars checked out of {self.particulars} extracted"
            )

    @property
    def examined(self) -> int:
        return self.bearing + self.unbearing

    def describe(self) -> str:
        return (
            f"{self.segments} segments: {self.bearing} bearing, "
            f"{self.unbearing} unbearing, {self.unexamined} unexamined; "
            f"{self.checked} of {self.particulars} particulars checked"
        )


@dataclass(frozen=True, slots=True)
class Assessment:
    """Every segment of an answer, what became of it, and what was skipped.

    The domain's whole output. What sits above this adds where the answer came
    from and turns it into a document; nothing above decides a verdict.
    """

    segments: tuple[CheckedSegment, ...] = ()
    skipped: tuple[Skipped, ...] = ()
    coverage: Coverage = Coverage()
    limits: tuple[str, ...] = STANDING_LIMITS

    @property
    def findings(self) -> tuple[CheckedSegment, ...]:
        """The segments a reader has to look at, in the order they were written."""
        return tuple(segment for segment in self.segments if segment.verdict.is_finding)

    def counts(self) -> dict[str, int]:
        """Every verdict, including the ones that are zero.

        A verdict missing from a summary reads as a verdict that cannot happen,
        and ``contradicted`` at zero is a different statement from
        ``contradicted`` being absent.
        """
        tally = {verdict.value: 0 for verdict in Verdict}
        for segment in self.segments:
            tally[segment.verdict.value] += 1
        return tally

    def particular_counts(self) -> dict[str, int]:
        tally = {standing.value: 0 for standing in Standing}
        for segment in self.segments:
            for particular in segment.particulars:
                tally[particular.standing.value] += 1
        return tally

    @property
    def grounded_share(self) -> float | None:
        """Grounded particulars over checked ones, or ``None`` when none were.

        ``None`` rather than ``1.0`` or ``0.0``: an answer with nothing to check
        has not scored perfectly and has not scored badly, and a number here
        would be read as one of the two. The caller has to say "nothing was
        checkable" in words.
        """
        counts = self.particular_counts()
        checked = counts[Standing.GROUNDED.value] + counts[Standing.FLOATING.value]
        if not checked:
            return None
        return counts[Standing.GROUNDED.value] / checked


#: Added when the evidence was handed over as plain strings rather than read
#: from a ContextPackage.
#:
#: A reader who sees `notes/gear.md[1209:1214]` on a report goes and opens that
#: file. A reader who sees `context 2[41:46]` does not, and must not be led to.
#: The artefact travels and the documentation does not (ADR-0005), so this is on
#: the artefact rather than in a README about the compatibility layer.
PLAIN_CONTEXT_LIMITS: tuple[str, ...] = (
    "The evidence was supplied as plain strings, so every offset here indexes "
    "the string that was passed in, at the position given -- not a document. "
    "akashi was not told where any of it came from and does not say.",
)


def assess(
    segments: Sequence[CheckedSegment],
    kinds_not_extracted: Sequence[ParticularKind] = (),
    limits: Sequence[str] = STANDING_LIMITS,
) -> Assessment:
    """Gather checked segments into an assessment, with its own account.

    The skips are derived from the segments rather than passed in alongside
    them, so that a segment akashi did not examine cannot fail to appear in the
    account. Every discarding path carries its reason to the end, and the only
    way to guarantee that is for the account to be computed from the same thing
    the verdicts are.
    """
    skipped = tuple(
        Skipped(
            span=segment.span,
            rule=_rule_for(segment),
            reason=segment.because,
            segment_id=segment.segment.segment_id,
        )
        for segment in segments
        if not segment.verdict.was_examined
    ) + tuple(
        Skipped(
            span=segment.span,
            rule=SkipRule.NO_PARTICULARS,
            reason="the segment asserts something with no load-bearing token in it",
            segment_id=segment.segment.segment_id,
        )
        for segment in segments
        if segment.verdict is Verdict.UNBEARING
    )

    bearing = sum(1 for segment in segments if segment.bears_anything)
    unbearing = sum(1 for segment in segments if segment.verdict is Verdict.UNBEARING)
    unexamined = sum(1 for segment in segments if not segment.verdict.was_examined)
    particulars = sum(len(segment.particulars) for segment in segments)

    return Assessment(
        limits=tuple(limits),
        segments=tuple(segments),
        skipped=tuple(sorted(skipped, key=lambda entry: (entry.span, entry.rule.value))),
        coverage=Coverage(
            segments=len(segments),
            bearing=bearing,
            unbearing=unbearing,
            unexamined=unexamined,
            particulars=particulars,
            checked=particulars,
            kinds_not_extracted=tuple(kind.value for kind in kinds_not_extracted),
        ),
    )


def _rule_for(segment: CheckedSegment) -> SkipRule:
    if segment.verdict is Verdict.UNVERIFIABLE:
        return SkipRule.PROTECTED
    return SkipRule.NOT_PROSE
