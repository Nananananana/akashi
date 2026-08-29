"""A half-open range of character offsets.

Half-open, like a Python slice, so that ``text[span.start:span.end]`` is the
span and adjacent spans share an endpoint without overlapping. An off-by-one
here points a reader at the wrong sentence while still looking like a finding,
which is the class of failure ADR-0004 rejects fuzzy matching to avoid -- so
the invariants are checked on construction rather than assumed.

Offsets are into a Python string, which means they count code points and not
bytes or grapheme clusters. Every offset akashi reports and every offset it
reads from a ContextPackage anchor is in the same unit, and a consumer slicing
a file by them has to read it as text.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Span"]


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """``[start, end)`` in some text named elsewhere.

    A span does not know what it is a span of. What it points into is always
    carried alongside it -- by an anchor, a segment or a particular -- because
    a span that travels without its text is the thing that gets resolved
    against the wrong document.
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"a span starts at or after 0, not {self.start}")
        if self.end < self.start:
            raise ValueError(f"a span ends at or after it starts: [{self.start}, {self.end})")

    def __len__(self) -> int:
        return self.end - self.start

    @property
    def is_empty(self) -> bool:
        return self.start == self.end

    def slice(self, text: str) -> str:
        """The part of ``text`` this span covers."""
        return text[self.start : self.end]

    def shifted(self, by: int) -> Span:
        """The same span, moved. Used to lift an offset in one item's text up
        into an offset in the document that item came from."""
        return Span(self.start + by, self.end + by)

    def overlaps(self, other: Span) -> bool:
        """Share at least one position.

        An empty span occupies no positions, so it overlaps nothing -- not even
        a span it sits inside. Without that guard an empty span reads as
        overlapping half the document, and redundancy and tiling checks are
        both built on this.
        """
        if self.is_empty or other.is_empty:
            return False
        return self.start < other.end and other.start < self.end

    def contains(self, other: Span) -> bool:
        return self.start <= other.start and other.end <= self.end

    def touches(self, other: Span) -> bool:
        """Overlap, or meet at an endpoint. What tiling is checked with."""
        return self.start <= other.end and other.start <= self.end

    def describe(self) -> str:
        return f"[{self.start}:{self.end}]"
