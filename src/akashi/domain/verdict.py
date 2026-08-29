"""What became of a segment when its particulars were looked for.

Six outcomes, and keeping them apart is the substance of the module. Three of
them mean akashi found nothing wrong, and they mean it for three different
reasons -- which is the distinction ADR-0005 exists to protect.

``grounded``      every particular in the segment is in the text that was sent
``floating``      at least one is not
``contradicted``  one is not, and one of the same kind, where the others point, is
``unbearing``     akashi looked and there was nothing in it to check
``unchecked``     akashi did not look
``unverifiable``  akashi could not look, and says so

**A check that treats "I looked and found nothing wrong" the same as "I did not
look" lies by omission.** That is why ``unbearing`` and ``unchecked`` are
separate, why neither is folded into ``grounded``, and why the coverage numbers
carry all three.

``contradicted`` is defined here and produced by nothing. It is v0.4, after the
evaluation corpus exists to price its false positives -- shipping the strongest
claim on the page before there is anything to measure it against is how a
detector tuned to a threshold happens (mamori's ADR-0023). A test asserts that
v0.1 never produces it, so the vocabulary is stable while the detector is not.

**And the thing this module does not do.** A grounded segment is not a true
sentence. It means every load-bearing string in it is where the answer implies
it is. A model can quote your sources perfectly and reason from them
disastrously (ADR-0004).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .evidence import Evidence, Location
from .particular import Particular
from .segment import Segment
from .span import Span

__all__ = [
    "CheckedParticular",
    "CheckedSegment",
    "Standing",
    "Verdict",
    "check_segment",
]


class Standing(Enum):
    """What became of one particular."""

    GROUNDED = "grounded"
    FLOATING = "floating"

    @property
    def is_grounded(self) -> bool:
        return self is Standing.GROUNDED


class Verdict(Enum):
    """What became of one segment."""

    GROUNDED = "grounded"
    FLOATING = "floating"
    #: v0.4. Defined so the vocabulary is stable; produced by nothing yet.
    CONTRADICTED = "contradicted"
    UNBEARING = "unbearing"
    UNCHECKED = "unchecked"
    UNVERIFIABLE = "unverifiable"

    @property
    def is_finding(self) -> bool:
        """Something a reader has to look at. Not the same as "a lie"."""
        return self in (Verdict.FLOATING, Verdict.CONTRADICTED)

    @property
    def was_examined(self) -> bool:
        """akashi looked. It may still have found nothing to check."""
        return self not in (Verdict.UNCHECKED, Verdict.UNVERIFIABLE)


@dataclass(frozen=True, slots=True)
class CheckedParticular:
    """One particular, and every place it turned out to be."""

    particular: Particular
    #: Every place it stands alone in the text that was sent. Empty means it is
    #: nowhere in it, which is a real answer and not a near miss.
    locations: tuple[Location, ...] = ()

    @property
    def standing(self) -> Standing:
        return Standing.GROUNDED if self.locations else Standing.FLOATING

    @property
    def is_ambiguous(self) -> bool:
        """Found in more than one place. Information, not an error."""
        return len(self.locations) > 1

    @property
    def in_an_interpretation(self) -> bool:
        """Grounded, and every place it was found was already a judgement.

        ``any`` would be the wrong quantifier: a particular that appears in one
        fact and one interpretation is grounded in a fact, and saying otherwise
        would understate the evidence rather than overstate it.
        """
        return bool(self.locations) and all(
            location.in_an_interpretation for location in self.locations
        )

    def describe(self) -> str:
        where = self.locations[0].anchor.describe() if self.locations else "nowhere"
        return f"{self.particular.describe()}: {self.standing.value} ({where})"


@dataclass(frozen=True, slots=True)
class CheckedSegment:
    """One segment of the answer, and what became of it."""

    segment: Segment
    particulars: tuple[CheckedParticular, ...] = ()
    verdict: Verdict = Verdict.UNBEARING
    #: Set when the verdict is ``unchecked`` or ``unverifiable``.
    because: str = ""

    def __post_init__(self) -> None:
        if self.verdict.was_examined and self.because:
            raise ValueError(
                f"{self.segment.segment_id} is {self.verdict.value} and carries a reason "
                f"for not being examined; a reason on an examined segment reads as an "
                f"excuse for a finding"
            )
        if not self.verdict.was_examined and not self.because:
            raise ValueError(
                f"{self.segment.segment_id} is {self.verdict.value} and does not say why. "
                f"An unexamined segment with no reason is a silent gap (ADR-0005)."
            )
        if not self.verdict.was_examined and self.particulars:
            raise ValueError(
                f"{self.segment.segment_id} is {self.verdict.value} but carries particulars"
            )

    @property
    def span(self) -> Span:
        return self.segment.span

    @property
    def floating(self) -> tuple[CheckedParticular, ...]:
        return tuple(p for p in self.particulars if p.standing is Standing.FLOATING)

    @property
    def grounded(self) -> tuple[CheckedParticular, ...]:
        return tuple(p for p in self.particulars if p.standing is Standing.GROUNDED)

    @property
    def bears_anything(self) -> bool:
        return bool(self.particulars)


def check_segment(
    segment: Segment,
    particulars: Sequence[Particular],
    evidence: Evidence,
) -> CheckedSegment:
    """Resolve one segment's particulars against the text that was sent.

    Pure, and the only place a verdict is decided. Code is not examined at all
    (ADR-0004's extraction note); a segment with nothing to check is
    ``unbearing`` and says so rather than passing.
    """
    if segment.is_code:
        return CheckedSegment(
            segment=segment,
            verdict=Verdict.UNCHECKED,
            because="a fenced block; a number in code is as likely to be a line number "
            "or a hash as a claim about the world",
        )

    checked = tuple(
        CheckedParticular(particular=particular, locations=evidence.locate(particular))
        for particular in particulars
    )
    if not checked:
        return CheckedSegment(segment=segment, verdict=Verdict.UNBEARING)

    verdict = (
        Verdict.GROUNDED if all(one.standing.is_grounded for one in checked) else Verdict.FLOATING
    )
    return CheckedSegment(segment=segment, particulars=checked, verdict=verdict)
