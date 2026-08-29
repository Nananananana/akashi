"""Spans, and the invariants that stop an offset drifting quietly."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from akashi.domain.span import Span

OFFSETS = st.integers(min_value=0, max_value=500)


def test_a_span_slices_the_text_it_points_into() -> None:
    assert Span(4, 9).slice("the quick brown fox") == "quick"


def test_a_span_may_be_empty() -> None:
    empty = Span(7, 7)
    assert empty.is_empty
    assert len(empty) == 0
    assert empty.slice("anything") == ""


def test_a_span_may_not_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="ends at or after it starts"):
        Span(9, 4)


def test_a_span_may_not_start_before_the_text() -> None:
    with pytest.raises(ValueError, match="starts at or after 0"):
        Span(-1, 4)


def test_shifting_lifts_an_offset_into_a_wider_text() -> None:
    """An item's text sits inside a document; a match inside the item has to be
    reported as a position in the document, or a reader cannot open it."""
    assert Span(3, 8).shifted(1200) == Span(1203, 1208)


def test_shifting_off_the_front_is_refused_rather_than_clamped() -> None:
    with pytest.raises(ValueError):
        Span(0, 4).shifted(-1)


def test_adjacent_spans_do_not_overlap() -> None:
    """Half-open is the whole reason to prefer it: segments that tile a text
    share an endpoint, and sharing an endpoint is not an overlap."""
    assert not Span(0, 5).overlaps(Span(5, 9))
    assert Span(0, 6).overlaps(Span(5, 9))


def test_an_empty_span_overlaps_nothing() -> None:
    assert not Span(3, 3).overlaps(Span(0, 10))
    assert not Span(0, 10).overlaps(Span(3, 3))


def test_touching_is_what_tiling_is_checked_with() -> None:
    assert Span(0, 5).touches(Span(5, 9))
    assert not Span(0, 5).touches(Span(6, 9))


def test_containment_includes_the_endpoints() -> None:
    assert Span(0, 10).contains(Span(0, 10))
    assert Span(0, 10).contains(Span(3, 4))
    assert not Span(0, 10).contains(Span(3, 11))


def test_spans_sort_by_position() -> None:
    """Ordering discipline: nothing unordered reaches an output, so the type
    that positions everything has to have a total order of its own."""
    spans = [Span(5, 9), Span(0, 3), Span(0, 10), Span(5, 6)]
    assert sorted(spans) == [Span(0, 3), Span(0, 10), Span(5, 6), Span(5, 9)]


@given(start=OFFSETS, length=st.integers(min_value=0, max_value=100))
def test_length_is_the_distance_between_the_endpoints(start: int, length: int) -> None:
    assert len(Span(start, start + length)) == length


@given(text=st.text(max_size=200), start=OFFSETS, length=st.integers(0, 100))
def test_slicing_a_span_never_raises_however_far_past_the_end_it_points(
    text: str, start: int, length: int
) -> None:
    """A span can outlive the text it was made for. Python slicing clamps, and
    that is the behaviour relied on -- the check that a span still fits its
    text belongs to whoever owns both, not to the span."""
    assert isinstance(Span(start, start + length).slice(text), str)
