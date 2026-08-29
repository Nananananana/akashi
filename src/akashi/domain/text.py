"""Reducing text for comparison, without losing where it came from.

Every comparison akashi makes runs through here, and the tolerance is stated
once, in one place, so that widening it later is a visible act rather than a
drifting default. ADR-0004:

    NFKC, case-folded, and runs of whitespace collapsed to one space.

Nothing else. No fuzzy matching, no edit distance, no "close enough". The
tolerance covers the ways the *same* string can be written differently -- a
full-width digit, a wrapped line, ``㎏`` written as a single character -- and
stops there, because every step past it trades a false negative for a false
positive and only one of those two is safe in an audit.

So ``２.４`` and ``2.4`` are the same string, and ``2.4 kg`` written with a
newline or two spaces is the same as ``2.4 kg`` written with one. ``2.4`` and
``2.40`` are not the same, ``2.4kg`` and ``2400g`` are not, and -- read this
one carefully -- **``2.4kg`` and ``2.4 kg`` are not the same either.** Runs of
whitespace collapse to one space; a space is never deleted. Whether a
*particular* should compare equal across that difference is a separate and
narrower question, and it belongs to the extractor rather than here: this
module is the tolerance for text, and widening it for prose would make
``a b`` and ``ab`` the same sentence.

**The map back is the point.** A reduced form on its own would let akashi say
that a string is missing, and nothing more. ``origin`` and ``extent`` are what
turn a match into an offset in a document a reader can open, and the round trip
is a property test rather than an example.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from .span import Span

__all__ = ["SearchForm", "search_form"]


def _fold(chunk: str) -> str:
    """One character and its combining marks, reduced.

    The second ``NFKC`` is not redundant: case folding can leave a string that
    is no longer normalized, and Unicode's own ``toNFKC_Casefold`` is defined
    as the composition of the three steps. Skipping it makes a handful of
    Greek and Cherokee strings compare unequal to themselves.
    """
    return unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", chunk).casefold())


@dataclass(frozen=True, slots=True)
class SearchForm:
    """Text reduced to its comparable form, with a map back to the original.

    ``origin[i]`` and ``extent[i]`` bracket the piece of ``original`` that
    produced ``text[i]``. They are separate arrays rather than one, because the
    relationship is not one-to-one in either direction: ``ﬁ`` produces two
    characters from one, and ``か`` followed by a combining dakuten produces one
    from two. Assuming either direction is safe is how an offset drifts by a
    character in exactly the scripts this project exists for.
    """

    original: str
    text: str
    #: ``origin[i]`` is the index in ``original`` where ``text[i]`` came from.
    origin: tuple[int, ...] = field(repr=False)
    #: ``extent[i]`` is the exclusive end in ``original`` of that same piece.
    extent: tuple[int, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not (len(self.text) == len(self.origin) == len(self.extent)):
            raise ValueError(
                f"the reduced text and its map disagree: {len(self.text)} characters, "
                f"{len(self.origin)} origins, {len(self.extent)} extents"
            )

    @property
    def is_empty(self) -> bool:
        return not self.text

    def to_original(self, span: Span) -> Span:
        """The span of ``original`` that produced ``span`` of ``text``.

        An empty span carries no position, so it comes back empty rather than
        pointing at the start of the document and implying it was found there.

        Where a span cuts through an expansion -- half of an ``ﬁ`` -- the
        result covers the whole source character. It is the smallest span of
        the original that contains everything the reduced span refers to, which
        is the only answer that cannot be an under-report.
        """
        if span.is_empty or not self.origin:
            return Span(0, 0)
        last = min(span.end, len(self.origin)) - 1
        return Span(self.origin[span.start], self.extent[last])

    def character_before(self, span: Span) -> str:
        """The reduced character preceding ``span``, or ``""`` at the start.

        Resolution needs this: ``2.4`` occurs inside ``2.40``, and a substring
        search that does not look at what sits either side of a match will
        report a number as grounded because a longer number contains it.
        """
        return self.text[span.start - 1] if span.start > 0 else ""

    def character_after(self, span: Span) -> str:
        """The reduced character following ``span``, or ``""`` at the end."""
        return self.text[span.end] if span.end < len(self.text) else ""


def search_form(text: str) -> SearchForm:
    """Reduce ``text`` for comparison, keeping the offsets.

    Applied identically to both sides of every comparison, so that a quotation
    and the text it is checked against are reduced on equal terms.

    Leading and trailing whitespace is dropped: a model that quotes with a
    trailing newline has not made a mistake worth reporting.
    """
    # Expand first, collapse second. Doing both in one pass looks tempting and
    # gets the case where a character normalizes *into* whitespace wrong --
    # U+2000 EN QUAD is not caught by ``isspace`` before NFKC turns it into a
    # space, and a run containing one would then collapse to two spaces.
    expanded: list[tuple[str, int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        after = index + 1
        while after < length and unicodedata.combining(text[after]):
            after += 1
        for character in _fold(text[index:after]):
            expanded.append((character, index, after))
        index = after

    pieces: list[str] = []
    origin: list[int] = []
    extent: list[int] = []
    in_space = True  # True at the start, so leading whitespace is dropped.

    for character, start, end in expanded:
        if character.isspace():
            if not in_space:
                pieces.append(" ")
                origin.append(start)
                extent.append(end)
                in_space = True
            elif extent:
                # The one space stands for the whole run, so it has to reach to
                # the end of it. Without this a span ending on a collapsed run
                # recovers an original that stops inside the whitespace, which
                # is an under-report of what the match actually covered.
                extent[-1] = end
            continue
        in_space = False
        pieces.append(character)
        origin.append(start)
        extent.append(end)

    while pieces and pieces[-1] == " ":
        pieces.pop()
        origin.pop()
        extent.pop()

    return SearchForm(
        original=text,
        text="".join(pieces),
        origin=tuple(origin),
        extent=tuple(extent),
    )
