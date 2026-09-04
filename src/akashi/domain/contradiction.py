"""What the source says instead.

A `floating` particular says *this figure is in none of your sources*. A
`contradicted` one says *this figure is wrong, and here is the one your source
gives, at this offset*. The second is what a reader can act on, and the
difference between the two is the difference between a complaint and evidence.

Held back from v0.1 on purpose. This is the strongest claim akashi makes and
therefore the one most able to be wrong, and shipping it before there was a
corpus to price its false positives against is how a detector tuned to a
threshold happens (`mamori`'s ADR-0023).

**The rule is narrower than the feature was specified as, because the
measurement said the rest of it does not work.** akashi names the source only
when the answer's digits and the source's digits are *identical* and the text
around them differs — ``5 grams`` where the source says ``5mg``, ``1,200億円``
where it says ``1,200万円``. A value whose digits changed is left `floating`.

The measurement is in ``docs/measurements.md`` and it is not close. Over the
corpus, naming a source for a value whose digits drifted was right 47% of the
time; naming one for a value whose digits were intact was right 12 times out of
12. Three plant kinds explain the gap and none of them can be told apart from a
drift by anything in the text:

- an **invented** figure. ``250mg`` beside a source's ``5mg`` is a number in the
  answer that is not in the source, sitting near a source number of the same
  shape. So is a drift. There is no third thing to look at.
- a **derived** value. ``28回`` sits next to the ``2回`` and the ``14日`` it was
  computed from, and reporting "the source says 2回" is not merely unhelpful,
  it is false — the source and the answer agree.
- a **different** figure. A contract full of ``60 days``, ``90 days`` and
  ``30 days`` offers a drifted ``45 days`` several equally good parents.

Identical digits are a different kind of thing. They are a *shared substring*,
which is textual evidence rather than similarity, and ADR-0004 is built on the
observation that a faithful paraphrase does not have one. When ``5`` survives
verbatim and the unit beside it does not, the number was copied and the unit was
got wrong. That is the only case where akashi can point at a source and say the
answer replaced it.

**The rest of the rule, and every part of it is a restriction.**

1. Same **kind**. A quantity is never explained by a date.
2. Same **digits**, and at least one of them. Different text around them.
3. **Exactly one** candidate, taken from the tightest neighbourhood that has
   one: the item sentences the rest of the segment resolved into, then those
   whole items, then the package. Two candidates leave it `floating`, because
   ambiguity is not a finding and naming one would invent the precision this
   project refuses.

Step 3 has no floor under it — the package is the whole of what was sent — and
that is deliberate. It was originally specified the other way, with a segment
that had grounded nothing barred from ever being contradicted, on the reasoning
that without an anchor there is no way to know which document the sentence is
about. That anchor cost 10 of the 12 findings and bought no precision at all,
because identical digits do the anchoring better than proximity does: the
corpus's answers put one figure in a sentence, so the anchor was usually absent
exactly when the finding was wanted. The uniqueness requirement in step 3 is
what keeps it honest, and the neighbourhood is now used only to *break ties*.

The index costs one segmentation and one extraction pass over the evidence, per
audit. That is the same work the answer already gets, over text that is usually
shorter, and it buys the only finding a reader can act on without opening the
file themselves.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .anchor import Anchor
from .evidence import Evidence, Location
from .extraction import extract_from_segment
from .language import LanguagePack
from .particular import Particular, ParticularKind
from .segment import segment_answer
from .span import Span
from .text import search_form

#: Runs of digits. What is left of a value when these go is its shape.
_DIGITS = re.compile(r"\d+")

__all__ = ["Contradiction", "SourceIndex", "SourceParticular", "replaces"]


def _shape(text: str) -> str:
    """What is left of a value when its digits are taken out. ``2.4kg`` -> ``#kg``."""
    return _shape_of(search_form(text).text)


def _digits(text: str) -> str:
    """What is left of a value when everything but its digits is."""
    return _digits_of(search_form(text).text)


# The two above take raw text and reduce it; these take text already reduced.
# `replaces` is the hot path -- it ran four reductions per candidate pair and
# two of them were of strings it had just reduced -- and reducing once and
# asking two questions of the result is the same answer for half the work.
def _shape_of(reduced: str) -> str:
    return _DIGITS.sub("#", reduced)


def _digits_of(reduced: str) -> str:
    return "".join(_DIGITS.findall(reduced))


def replaces(source_text: str, answer_text: str) -> bool:
    """Whether the answer's value is the source's with the unit changed.

    The digits must be identical and there must be some: a value with no digits
    has none to survive, and without this guard every name would explain every
    other name. The text around them must differ, because two ways of writing
    the same value are the same value and would have grounded.
    """
    left, right = search_form(source_text).text, search_form(answer_text).text
    source, answer = _digits_of(left), _digits_of(right)
    return bool(source) and source == answer and _shape_of(left) != _shape_of(right)


@dataclass(frozen=True, slots=True)
class SourceParticular:
    """A particular akashi found in the text that was sent."""

    item_id: str
    kind: ParticularKind
    text: str
    #: Where it is, in document coordinates. What a reader opens.
    anchor: Anchor
    #: The item sentence it sits in, in *item* coordinates. The neighbourhood.
    sentence: Span


@dataclass(frozen=True, slots=True)
class Contradiction:
    """What the source says where the answer says something else."""

    found: str
    item_id: str
    anchor: Anchor
    #: The rule that produced this. A finding that cannot say why it is a
    #: finding is a finding nobody can appeal.
    why: str

    def describe(self) -> str:
        return f"the source says {self.found!r} at {self.anchor.describe()}"


@dataclass(frozen=True, slots=True)
class SourceIndex:
    """Every particular in the text that was sent, by where it sits.

    Built once per audit. Empty when the caller did not ask for it, and an
    empty index contradicts nothing -- which is what makes this feature
    switchable off without a flag reaching the domain.
    """

    entries: tuple[SourceParticular, ...] = ()

    #: ``entries`` grouped by the two things `replaces` requires to be equal.
    #:
    #: `explain` used to walk every entry three times, once per scope, calling
    #: `replaces` on each -- and `replaces` begins by refusing every pair whose
    #: digits differ. On a realistic audit that was 7,360 comparisons, almost
    #: all of them answered by the first line of the function.
    #:
    #: The grouping is exact rather than an approximation: `replaces` is false
    #: unless the digits are identical and non-empty, so a bucket miss is a
    #: definite no. Derived in `__post_init__` rather than in `of`, so a caller
    #: building an index directly -- every test that does -- gets one too.
    by_digits: dict[tuple[ParticularKind, str], tuple[SourceParticular, ...]] = field(
        default_factory=dict, compare=False, repr=False
    )

    def __post_init__(self) -> None:
        grouped: dict[tuple[ParticularKind, str], list[SourceParticular]] = {}
        for entry in self.entries:
            digits = _digits(entry.text)
            if digits:
                grouped.setdefault((entry.kind, digits), []).append(entry)
        object.__setattr__(self, "by_digits", {key: tuple(value) for key, value in grouped.items()})

    @classmethod
    def of(cls, evidence: Evidence, packs: Sequence[LanguagePack]) -> SourceIndex:
        found: list[SourceParticular] = []
        for item in evidence.items:
            for segment in segment_answer(item.text, packs).segments:
                if segment.is_code:
                    continue
                for particular in extract_from_segment(segment, packs):
                    # ``extract_from_segment`` returns spans in the coordinates
                    # of the text it segmented, which here is the item's own.
                    found.append(
                        SourceParticular(
                            item_id=item.item_id,
                            kind=particular.kind,
                            text=particular.text,
                            anchor=item.anchor.narrowed(particular.span),
                            sentence=segment.span,
                        )
                    )
        return cls(entries=tuple(found))

    def __len__(self) -> int:
        return len(self.entries)

    def explain(
        self,
        floating: Particular,
        grounded: Sequence[Location],
        evidence: Evidence,
    ) -> Contradiction | None:
        """What the source says where ``floating`` says something else.

        ``grounded`` is where the *rest of the segment* resolved. It narrows the
        search when more than one candidate would otherwise qualify, and a
        segment without any is still eligible -- see the module docstring for
        why that restriction was specified, measured, and dropped.
        """
        if not self.entries:
            return None

        sentences = self._sentences_of(grounded, evidence)
        items = {item_id for item_id, _ in sentences}
        # Tightest first. The neighbourhood breaks ties; it does not make the
        # finding, and the package is the floor because that is all that was
        # sent.
        scopes: tuple[tuple[str, Callable[[SourceParticular], bool]], ...] = (
            ("sentence", lambda entry: (entry.item_id, entry.sentence) in sentences),
            ("item", lambda entry: entry.item_id in items),
            ("package", lambda entry: True),
        )
        # Everything `replaces` could say yes to, found by lookup rather than by
        # scanning. What is left for it to decide is the shape, which is the
        # half of the rule that is actually about this pair.
        reduced = search_form(floating.text).text
        possible = self.by_digits.get((floating.kind, _digits_of(reduced)), ())
        if not possible:
            return None
        shape = _shape_of(reduced)

        for where, within in scopes:
            candidates = [
                entry
                for entry in possible
                if within(entry) and _shape_of(search_form(entry.text).text) != shape
            ]
            if len(candidates) == 1:
                found = candidates[0]
                return Contradiction(
                    found=found.text,
                    item_id=found.item_id,
                    anchor=found.anchor,
                    why=(
                        f"the only {floating.kind.value} in the {where} carrying the same "
                        f"digits as this one, written with a different unit"
                    ),
                )
        return None

    def nearby(
        self,
        floating: Particular,
        grounded: Sequence[Location],
        evidence: Evidence,
        most: int = 5,
    ) -> tuple[SourceParticular, ...]:
        """Everything of the same kind the evidence does say, nearest scope first.

        **This is not a finding and makes no claim about the floating value.**
        `explain` names a source only when the digits are identical, which the
        corpus priced at 12/12; anything looser was 47% and is not shipped as a
        verdict. What is shipped instead is the list itself, unranked by any
        similarity and unlabelled by any confidence: *you said 2.4kg, and the
        quantities the evidence actually carries here are these, at these
        offsets.*

        The reason this exists is that `floating` alone is a dead end. A reader
        told only that a figure is in none of the text still has to go and read
        all of it, and akashi has already read all of it. Handing over the
        candidates it looked at is the difference between a refusal and an
        answer -- and it costs no confidence, because there is no threshold
        here to be wrong about.

        Scope is the ordering and the only one: the sentences the rest of this
        segment resolved into, then those whole items, then everything sent. A
        similarity score would put akashi's guess at the top of a list a reader
        is about to trust, which is exactly what `explain` refuses to do.
        """
        if not self.entries or most <= 0:
            return ()
        sentences = self._sentences_of(grounded, evidence)
        items = {item_id for item_id, _ in sentences}
        found: list[SourceParticular] = []
        scopes: tuple[Callable[[SourceParticular], bool], ...] = (
            lambda entry: (entry.item_id, entry.sentence) in sentences,
            lambda entry: entry.item_id in items,
            lambda entry: True,
        )
        for within in scopes:
            for entry in self.entries:
                if entry.kind is not floating.kind or entry in found:
                    continue
                # The particular itself is not a neighbour of itself. It floated,
                # so no *location* matched -- but the same string can sit in the
                # evidence inside a longer token, and offering it back as "what
                # the evidence says instead" would be a lie by omission.
                if entry.text == floating.text or not within(entry):
                    continue
                found.append(entry)
                if len(found) >= most:
                    return tuple(found)
        return tuple(found)

    def _sentences_of(
        self, grounded: Sequence[Location], evidence: Evidence
    ) -> set[tuple[str, Span]]:
        """Which item sentences the segment's grounded particulars landed in."""
        starts = {item.item_id: item.anchor.span.start for item in evidence.items}
        found: set[tuple[str, Span]] = set()
        for location in grounded:
            offset = starts.get(location.item_id)
            if offset is None:
                continue
            inside = location.anchor.span.shifted(-offset)
            for entry in self.entries:
                if entry.item_id == location.item_id and entry.sentence.contains(inside):
                    found.add((entry.item_id, entry.sentence))
        return found
