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

``contradicted`` was defined here and produced by nothing until v0.4, on
purpose: shipping the strongest claim on the page before there was a corpus to
measure it against is how a detector tuned to a threshold happens (mamori's
ADR-0023). The rule is in ``contradiction.py`` and every part of it is a
restriction.

**And the thing this module does not do.** A grounded segment is not a true
sentence. It means every load-bearing string in it is where the answer implies
it is. A model can quote your sources perfectly and reason from them
disastrously (ADR-0004).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from .contradiction import Contradiction, SourceIndex, SourceParticular
from .evidence import Evidence, Location
from .matching import DEFAULT_MATCHER, Matcher
from .particular import Particular
from .protection import PlaceholderResidue
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
    CONTRADICTED = "contradicted"
    UNBEARING = "unbearing"
    UNCHECKED = "unchecked"
    UNVERIFIABLE = "unverifiable"

    @property
    def rule(self) -> str:
        """The rule that produced this verdict, in one line.

        The same words `docs/audit-report.md` gives a consumer, kept here so
        there is one definition rather than two. `akashi explain` prints this
        beside a segment: a reader looking at one finding should not have to
        hold the contract open beside it to know what the word means.

        A segment carrying ``because`` says more than this and says it about
        itself; this is what the verdict means for every segment that has it.
        """
        return _RULES[self]

    @property
    def is_finding(self) -> bool:
        """Something a reader has to look at. Not the same as "a lie"."""
        return self in (Verdict.FLOATING, Verdict.CONTRADICTED)

    @property
    def was_examined(self) -> bool:
        """akashi looked. It may still have found nothing to check."""
        return self not in (Verdict.UNCHECKED, Verdict.UNVERIFIABLE)


#: One line per verdict, worded as the contract words it. Kept beside the enum
#: rather than in the renderer: two places that explain the same vocabulary
#: drift, and the one a reader reaches first is not always the maintained one.
_RULES: dict[Verdict, str] = {
    Verdict.GROUNDED: "every particular in the segment is in the text that was sent",
    Verdict.FLOATING: "at least one is not",
    Verdict.CONTRADICTED: "one is not, and akashi can name the source value it replaced",
    Verdict.UNBEARING: "akashi looked and there was nothing to check",
    Verdict.UNCHECKED: "akashi did not look",
    Verdict.UNVERIFIABLE: "akashi could not look, and says so",
}


@dataclass(frozen=True, slots=True)
class CheckedParticular:
    """One particular, and every place it turned out to be."""

    particular: Particular
    #: Every place it stands alone in the text that was sent. Empty means it is
    #: nowhere in it, which is a real answer and not a near miss.
    locations: tuple[Location, ...] = ()
    #: What the source says instead, when akashi could tell. Set only on a
    #: floating particular, and only when the rule in ``contradiction.py``
    #: found exactly one candidate.
    contradiction: Contradiction | None = None
    #: What the evidence *does* say of this kind, nearest scope first, when the
    #: particular floated and akashi could not name a source for it.
    #:
    #: Not a finding and not a ranking. `floating` on its own is a dead end --
    #: it tells a reader the figure is in none of the text and leaves them to go
    #: and read all of it, which akashi has already done. These are the
    #: candidates it looked at, with their offsets, carrying no claim that any
    #: of them is related. See `SourceIndex.nearby`.
    nearby: tuple[SourceParticular, ...] = ()

    def __post_init__(self) -> None:
        if self.nearby and self.locations:
            raise ValueError(
                f"{self.particular.text!r} is grounded and also carries neighbours. "
                f"What the evidence says instead is only a question for a particular "
                f"that is not in it."
            )
        if self.contradiction is not None and self.locations:
            raise ValueError(
                f"{self.particular.text!r} is grounded and also carries a contradiction. "
                f"A particular that resolved cannot also be the wrong value."
            )

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

    @property
    def is_contradicted(self) -> bool:
        return self.contradiction is not None

    def describe(self) -> str:
        if self.contradiction is not None:
            return f"{self.particular.describe()}: {self.contradiction.describe()}"
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
    sources: SourceIndex | None = None,
    residue: Sequence[PlaceholderResidue] = (),
    matcher: Matcher = DEFAULT_MATCHER,
) -> CheckedSegment:
    """Resolve one segment's particulars against the text that was sent.

    Pure, and the only place a verdict is decided. Code is not examined at all
    (ADR-0004's extraction note); a segment with nothing to check is
    ``unbearing`` and says so rather than passing.

    ``sources`` is what turns a floating particular into a contradicted one. It
    is optional and an absent one changes no verdict except that: without it
    every finding is ``floating``, which is exactly what v0.1 through v0.3 did.

    ``residue`` is placeholder-shaped text a restorer could not put back, and it
    is checked **before** anything is resolved. ADR-0008: a segment whose value
    was masked is ``unverifiable`` and never ``floating``, because *unknown* and
    *false* are different and an auditor that conflates them teaches its user to
    ignore it. A floating particular says the figure is in none of the sources;
    here nobody knows what the figure was.
    """
    if segment.is_code:
        return CheckedSegment(
            segment=segment,
            verdict=Verdict.UNCHECKED,
            because="a fenced block; a number in code is as likely to be a line number "
            "or a hash as a claim about the world",
        )

    unrestored = [one for one in residue if segment.span.overlaps(one.span)]
    if unrestored:
        # No particulars, which ``CheckedSegment`` enforces: reporting findings
        # from a segment akashi has just said it could not check would be the
        # conflation this branch exists to prevent, one level down.
        listed = ", ".join(one.token for one in unrestored[:3])
        more = ", ..." if len(unrestored) > 3 else ""
        return CheckedSegment(
            segment=segment,
            verdict=Verdict.UNVERIFIABLE,
            because=f"a value here was redacted and could not be restored ({listed}{more}); "
            f"akashi does not know what it was, which is not the same as knowing it is wrong",
        )

    resolved = tuple(
        CheckedParticular(particular=particular, locations=evidence.locate(particular, matcher))
        for particular in particulars
    )
    if not resolved:
        return CheckedSegment(segment=segment, verdict=Verdict.UNBEARING)

    # Where the *rest of the segment* landed. It narrows the search for what a
    # floating particular replaced when more than one candidate would qualify.
    # It does not gate the finding: see ``contradiction`` for why that
    # restriction was specified, measured at a cost of ten findings in twelve,
    # and dropped.
    anchored = tuple(
        location for one in resolved if one.standing.is_grounded for location in one.locations
    )
    checked = tuple(
        _explained(one, anchored, evidence, sources) if not one.standing.is_grounded else one
        for one in resolved
    )

    if any(one.is_contradicted for one in checked):
        verdict = Verdict.CONTRADICTED
    elif all(one.standing.is_grounded for one in checked):
        verdict = Verdict.GROUNDED
    else:
        verdict = Verdict.FLOATING
    return CheckedSegment(segment=segment, particulars=checked, verdict=verdict)


def _explained(
    one: CheckedParticular,
    anchored: Sequence[Location],
    evidence: Evidence,
    sources: SourceIndex | None,
) -> CheckedParticular:
    if sources is None:
        return one
    found = sources.explain(one.particular, anchored, evidence)
    if found is not None:
        return CheckedParticular(particular=one.particular, contradiction=found)
    # No source can be named, which is the common case and used to be the end of
    # it. What the evidence does carry of this kind is still worth handing over.
    return CheckedParticular(
        particular=one.particular,
        nearby=sources.nearby(one.particular, anchored, evidence),
    )
