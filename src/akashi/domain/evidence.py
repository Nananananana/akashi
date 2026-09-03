"""The closed world an answer is checked against.

ADR-0006: the evidence set is exactly ``items[]`` of the package that produced
the answer. Nothing else is evidence -- not the corpus, not the instructions,
not the candidates that were considered and dropped. A figure the model guessed
that happens to exist somewhere in the archive was still guessed, and marking it
grounded rewards a lucky fabrication.

**There is one index and it has one source.** ``omissions[]`` is counted and
reported and never searched, because it does not carry the omitted text and
never will (ADR-0012). Keeping the withheld candidates in a different type from
the evidence, rather than in the same list behind a flag, is what makes
"grounded in something that was deliberately withheld" unrepresentable instead
of merely unwritten.

The instructions are not evidence either. A rule that happens to contain an
example number would otherwise ground every answer that echoed it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .anchor import Anchor, Layer
from .matching import DEFAULT_MATCHER, Matcher
from .particular import Particular
from .span import Span
from .text import SearchForm, search_form

__all__ = ["Evidence", "EvidenceItem", "Location", "Withheld", "item"]


@dataclass(frozen=True, slots=True)
class Location:
    """One place a particular was found, anchored back to a real document."""

    item_id: str
    anchor: Anchor
    layer: Layer | None = None
    producer: str = ""

    @property
    def in_an_interpretation(self) -> bool:
        """Grounded, and grounded in something that was already a judgement.

        Not a lesser kind of grounding, and not the same kind either. A report
        that flattened the two would launder an interpretation into a fact.
        """
        return self.layer is not None and self.layer.is_interpretation

    def describe(self) -> str:
        return f"{self.item_id} {self.anchor.describe()}"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One piece of context that was sent, ready to be searched.

    The reduced form is built once, on construction. An audit looks for every
    particular of the answer in every item, so reducing per lookup would be the
    whole cost of an audit spent over and over on the same text.
    """

    item_id: str
    text: str
    anchor: Anchor
    layer: Layer | None = None
    producer: str = ""
    form: SearchForm = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("an evidence item with no id cannot be cited")
        if len(self.text) != len(self.anchor.span):
            raise ValueError(
                f"{self.item_id} holds {len(self.text)} characters but its anchor covers "
                f"{len(self.anchor.span)} of {self.anchor.where}; one of the two is wrong, "
                f"and an offset reported from here would point at the wrong text"
            )
        object.__setattr__(self, "form", search_form(self.text))

    def locate(self, form: str, matcher: Matcher = DEFAULT_MATCHER) -> tuple[Anchor, ...]:
        """Every place ``form`` stands alone in this item, in document coordinates.

        ``matcher`` is which strings count as the same string, and it is the
        question the whole audit turns on. Its name reaches the report and the
        report's id, so two runs that answered it differently cannot be
        mistaken for one another.
        """
        return tuple(self.anchor.narrowed(span) for span in matcher.find(form, self.form))


@dataclass(frozen=True, slots=True)
class Withheld:
    """A candidate the package considered and did not send.

    Carries an anchor and a reason and **not the text** -- that is the
    contract, and ADR-0012 is what follows from it. This is a receipt, and the
    report uses it to say how much was held back and why. It grounds nothing
    and it explains no particular finding.
    """

    rule: str
    reason: str
    anchor: Anchor | None = None

    def __post_init__(self) -> None:
        if not self.rule:
            raise ValueError("a withheld candidate with no rule says nothing")
        if not self.reason:
            raise ValueError(f"the {self.rule!r} omission carries no reason")


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything that was sent, and the receipts for what was not."""

    items: tuple[EvidenceItem, ...] = ()
    withheld: tuple[Withheld, ...] = ()

    def __post_init__(self) -> None:
        seen = [entry.item_id for entry in self.items]
        if len(seen) != len(set(seen)):
            duplicated = sorted({name for name in seen if seen.count(name) > 1})
            raise ValueError(f"two evidence items share the id {duplicated}")

    def __len__(self) -> int:
        return len(self.items)

    @property
    def is_empty(self) -> bool:
        """A package that sent nothing. Every particular then floats, correctly
        and uselessly, and the caller should say so rather than print a score."""
        return not self.items

    @property
    def characters(self) -> int:
        return sum(len(entry.text) for entry in self.items)

    def locate(
        self, particular: Particular, matcher: Matcher = DEFAULT_MATCHER
    ) -> tuple[Location, ...]:
        """Every place this particular stands alone in the text that was sent.

        Ordered by item and then by position, so that a report over the same
        package is the same report every time (ADR-0003).
        """
        found: list[Location] = []
        for entry in self.items:
            found.extend(
                Location(
                    item_id=entry.item_id,
                    anchor=anchor,
                    layer=entry.layer,
                    producer=entry.producer,
                )
                for anchor in entry.locate(particular.form, matcher)
            )
        return tuple(found)

    def withheld_by_rule(self) -> dict[str, int]:
        """How many candidates were held back, under each rule, sorted.

        Context for the reader and nothing more. Four floating particulars
        beside nine candidates dropped for budget is a retrieval problem;
        four beside none is a model problem. A reader with both numbers can
        tell which they have -- and neither number explains any particular
        finding (ADR-0012).
        """
        counts: dict[str, int] = {}
        for candidate in self.withheld:
            counts[candidate.rule] = counts.get(candidate.rule, 0) + 1
        return dict(sorted(counts.items()))

    @classmethod
    def of(cls, items: Sequence[EvidenceItem], withheld: Sequence[Withheld] = ()) -> Evidence:
        return cls(items=tuple(items), withheld=tuple(withheld))


def item(
    item_id: str,
    text: str,
    *,
    document_id: str = "doc",
    start: int = 0,
    source_path: str = "",
    section: str = "",
    layer: Layer | None = None,
    producer: str = "",
) -> EvidenceItem:
    """An evidence item from its parts, for tests and for callers with no package.

    The anchor's span is derived from the text rather than passed in, because
    the two must agree and deriving is the only way that cannot drift. A caller
    reading a real package supplies the anchor it read (ADR-0007).
    """
    return EvidenceItem(
        item_id=item_id,
        text=text,
        anchor=Anchor(
            document_id=document_id,
            span=Span(start, start + len(text)),
            source_path=source_path,
            section=section,
        ),
        layer=layer,
        producer=producer,
    )
