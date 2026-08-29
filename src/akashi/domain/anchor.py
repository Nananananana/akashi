"""Where a piece of text came from, in coordinates a reader can open.

An anchor is the difference between "this number is not in your sources" and
"this number is not in your sources, and the one that is sits at
notes/design/gear.md offset 1204". The first is a complaint; the second is
evidence.

Offsets are into the *document*, not into the item. An item's text is a copy of
a span of a document, and a match inside the item has to be lifted into
document coordinates before it is reported -- otherwise a reader has to
reconstruct the selection before they can open the file, and a report is meant
to stand on its own (ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .span import Span

__all__ = ["Anchor", "Layer"]


class Layer(Enum):
    """What kind of statement a piece of context is.

    ``kiseki``'s distinction, and it survives the crossing: an interpretation
    stays an interpretation inside a package, and a particular grounded in one
    is grounded *in an interpretation*. Reporting that as though it were a fact
    would launder the very thing ``kiseki`` is most careful about.
    """

    FACT = "fact"
    MEASURE = "measure"
    INTERPRETATION = "interpretation"

    @property
    def is_interpretation(self) -> bool:
        return self is Layer.INTERPRETATION


@dataclass(frozen=True, slots=True)
class Anchor:
    """A span of a named document, and what is known about it."""

    document_id: str
    span: Span
    source_path: str = ""
    section: str = ""
    #: From the package. Carried so a report can say what the item hashed to
    #: when it was built; akashi does not recompute it, because it never reads
    #: the document.
    text_hash: str = ""
    document_hash: str = ""

    def __post_init__(self) -> None:
        if not self.document_id:
            raise ValueError("an anchor with no document names nothing")

    @property
    def where(self) -> str:
        """The most useful name for this document that is available."""
        return self.source_path or self.document_id

    def narrowed(self, inner: Span) -> Anchor:
        """This anchor, restricted to a span *of the item's text*.

        The item covers ``self.span`` of the document, so an offset inside the
        item is that offset plus ``self.span.start``. Hashes are dropped: they
        covered the whole item and saying nothing is better than carrying a
        hash that no longer describes what it is attached to.
        """
        moved = inner.shifted(self.span.start)
        if not self.span.contains(moved):
            raise ValueError(
                f"{inner.describe()} of the item lands at {moved.describe()}, outside the "
                f"item's own {self.span.describe()} in {self.where}"
            )
        return Anchor(
            document_id=self.document_id,
            span=moved,
            source_path=self.source_path,
            section=self.section,
        )

    def describe(self) -> str:
        where = self.where
        if self.section:
            where += f" ({self.section})"
        return f"{where}[{self.span.start}:{self.span.end}]"
