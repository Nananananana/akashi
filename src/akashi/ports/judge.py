"""A second opinion on what akashi could not check, from something that reads.

akashi decides by comparing strings. That is what makes an audit reproducible
and what bounds it: a particular the answer *paraphrased* out of the evidence is
reported `floating`, correctly and unhelpfully -- correctly, because it is in
none of the text that was sent; unhelpfully, because the reader wanted to know
whether the evidence supports it.

A judge answers the second question. It is a language model, so it answers
differently on a different day, and everything here exists to keep that fact
attached to its answer.

**A judgement is never a verdict.** akashi's verdicts are `grounded`,
`floating`, `contradicted`, `unbearing`, `unverifiable` and `unchecked`, and a
judgement uses none of those words. It says `supported`, `unsupported` or
`unclear`, about a claim, in its own vocabulary, under the name of the model
that said it. The two live in different sections of the report and nothing
merges them.

**And `report_id` does not move.** The id is a hash over the deterministic
inputs, so a report with judgements on it and the same report without them carry
the same id and `recheck` still works. What a judge adds is an annotation; what
it must never do is change the audit underneath.

That division is ADR-0017, which amends ADR-0003. ADR-0003 said no model runs at
audit time, ever, and it was right about the reason: a verdict that moves when
nobody changed anything is not an audit trail. It was wrong to conclude that
nothing a model says may appear on the artefact at all -- an annotation that
carries its own provenance is a different object from a verdict.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

__all__ = ["Claim", "Judge", "Judgement", "Standing"]


class Standing(Enum):
    """What a judge says about a claim.

    Deliberately none of akashi's own words. A reader who sees `supported` must
    not be able to read it as `grounded`: one means a model thought the evidence
    entails it, the other means the string is in the text that was sent, and the
    whole point of having both is that they are different claims.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNCLEAR = "unclear"


@dataclass(frozen=True, slots=True)
class Claim:
    """One thing akashi could not check, handed to a judge to look at."""

    segment_id: str
    text: str
    #: The particular that floated, when the claim is about one rather than
    #: about the whole sentence. Empty for a segment-level claim.
    particular: str = ""


@dataclass(frozen=True, slots=True)
class Judgement:
    """What a judge said, and who said it.

    ``model`` is required and is not decoration: two runs of the same judge
    against different model versions are two different answers, and a reader
    who cannot tell them apart cannot act on either.
    """

    segment_id: str
    standing: Standing
    because: str
    model: str
    particular: str = ""
    #: What the judge says about where its answer applies, in its own words.
    #:
    #: A model card that says "English only" is a fact about every number the
    #: model produced, and akashi reads Japanese and Chinese. Empty means akashi
    #: has no note about this judge -- which is different from the judge claiming
    #: to be universal, and neither is asserted. `AuditReport` turns the distinct
    #: scopes on a report into limit lines, so the caveat travels on the artefact
    #: rather than living in a README the report will be read without.
    scope: str = ""

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError(
                "a judgement with no model named is an opinion with no author. "
                "akashi records who said it, because a judge answers differently "
                "on a different day."
            )


@runtime_checkable
class Judge(Protocol):
    """Something that reads a claim and the evidence and says what it thinks.

    Implementations live in ``infrastructure/adapters/`` -- the one layer
    permitted to know that anything outside akashi exists -- and reach the
    network. Nothing below that layer may import one.

    ``model`` names what answered. A judge that cannot say is not one akashi
    will use, because the name is the only thing that lets a reader place the
    answer in time.
    """

    @property
    def model(self) -> str: ...

    def judge(self, claims: Sequence[Claim], evidence: Sequence[str]) -> tuple[Judgement, ...]:
        """One judgement per claim, in the order the claims were given.

        Fewer is a defect and more is a defect: a caller lines these up against
        what it asked about, and a judge that dropped one would shift every
        judgement after it onto the wrong sentence.
        """
        ...
