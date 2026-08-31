"""The one tolerance, and the map back to where the text came from.

ADR-0004 states the tolerance: NFKC, case-folded, whitespace runs collapsed.
These tests are what stop it widening by accident. A test here that starts
failing because "the strings are basically the same" is the tolerance drifting,
and the fix is an ADR, not a looser assertion.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Collection
from typing import Any, cast

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from akashi.domain.span import Span
from akashi.domain.text import SearchForm, search_form


def reduced(text: str) -> str:
    return search_form(text).text


# --- The tolerance, stated as examples ---------------------------------------


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("２.４kg", "2.4kg"),  # full-width digits are the same digits
        ("2.4  kg", "2.4 kg"),  # a run of whitespace is one space
        ("2.4\nkg", "2.4 kg"),  # a wrapped line is one space
        ("2.4㎏", "2.4kg"),  # a squared unit character is the letters it stands for
        ("Tanaka", "TANAKA"),  # case is not evidence
        ("ﬁle", "file"),  # a ligature is the letters it stands for
        ("が", "が"),  # composed and decomposed dakuten are one character
        ("１２３", "123"),
        ("ＡＢＣ", "abc"),
        ("第30条", "第30条"),
        ("a b", "a b"),  # a non-breaking space is a space
        ("a　b", "a b"),  # so is an ideographic one
        ("  padded  ", "padded"),
    ],
)
def test_these_are_the_same_string(left: str, right: str) -> None:
    assert reduced(left) == reduced(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("2.4", "2.40"),  # trailing zeros are a different number
        ("2.4kg", "2400g"),  # ADR-0004 owns this gap: no unit arithmetic
        # Collapsing is not deleting. Whether a *particular* should compare
        # equal across an internal space is a narrower question and belongs to
        # the extractor; widening it here would make "a b" and "ab" one string.
        ("2.4kg", "2.4 kg"),
        ("2.4", "2,4"),  # a decimal comma is not a decimal point
        ("第30条", "第13条"),
        ("300g", "300kg"),
        ("tanaka", "tanka"),  # nothing here is fuzzy
        ("2026-08-30", "2026-08-31"),
    ],
)
def test_these_are_not_the_same_string(left: str, right: str) -> None:
    assert reduced(left) != reduced(right)


def test_case_folding_survives_renormalization() -> None:
    """Case folding can leave a string that is no longer NFKC, which is why
    ``_fold`` normalizes twice. Without the second pass this compares unequal
    to itself."""
    assert reduced("ẞ") == reduced("ss")  # LATIN CAPITAL LETTER SHARP S


# --- The reduced form's own shape --------------------------------------------


def test_the_reduced_form_has_no_runs_of_whitespace() -> None:
    assert reduced("a \t\n  b\r\n\r\nc") == "a b c"


def test_the_reduced_form_is_stripped() -> None:
    assert reduced("\n\n  answer.  \n") == "answer."


def test_an_empty_text_reduces_to_nothing() -> None:
    form = search_form("")
    assert form.is_empty
    assert form.text == ""
    assert form.origin == ()


def test_text_that_is_only_whitespace_reduces_to_nothing() -> None:
    assert search_form("  \n\t 　 ").is_empty


def test_japanese_prose_survives_intact() -> None:
    """Nothing in the tolerance touches CJK, and a change that started
    stripping or splitting it would be caught here rather than in a score."""
    assert (
        reduced("テントは 2.4kg で、前回より 300g 軽い。")
        == "テントは 2.4kg で、前回より 300g 軽い。"
    )


def test_chinese_prose_survives_but_full_width_punctuation_folds() -> None:
    """NFKC leaves ``。`` and ``、`` alone and turns ``，`` into ``,``.

    Worth an explicit test rather than a surprise, because the two behave
    differently and the segmenter (ADR-0009) reads the *original* text for
    exactly that reason. A sentence boundary that only exists before
    normalization is a boundary the reduced form cannot be asked about.
    """
    assert reduced("帐篷重 2.4 公斤，比上次轻 300 克。") == "帐篷重 2.4 公斤,比上次轻 300 克。"
    assert reduced("テントは軽い。") == "テントは軽い。"
    assert reduced("テント、シュラフ") == "テント、シュラフ"


# --- The map back ------------------------------------------------------------


def test_an_offset_in_the_reduced_form_recovers_the_original_characters() -> None:
    form = search_form("The tent  weighs ２.４kg.")
    at = form.text.index("2.4kg")
    original = form.to_original(Span(at, at + len("2.4kg")))
    assert original.slice(form.original) == "２.４kg"


def test_the_map_reaches_across_a_collapsed_run() -> None:
    """The single space stands for the whole run, so a span that ends on it
    recovers everything the match actually covered."""
    form = search_form("a \t\n b")
    recovered = form.to_original(Span(0, len(form.text)))
    assert recovered == Span(0, 6)
    assert recovered.slice(form.original) == "a \t\n b"


def test_the_map_covers_a_whole_source_character_when_a_span_cuts_an_expansion() -> None:
    """``ﬁ`` is one character that reduces to two. Half of it is not a position
    in the original, so the answer is the whole character -- the smallest span
    that contains everything the match referred to. An under-report here would
    hand a reader an offset that slices to the wrong text."""
    form = search_form("ﬁle")
    assert form.text == "file"
    assert form.to_original(Span(0, 1)).slice(form.original) == "ﬁ"
    assert form.to_original(Span(1, 2)).slice(form.original) == "ﬁ"


def test_the_map_covers_both_characters_of_a_decomposed_dakuten() -> None:
    form = search_form("がっこいい")
    assert form.text.startswith("が")
    assert form.to_original(Span(0, 1)).slice(form.original) == "が"


def test_an_empty_span_recovers_no_position() -> None:
    """Not position zero. A span that found nothing must not point at the start
    of the document and imply it was found there."""
    form = search_form("anything at all")
    assert form.to_original(Span(4, 4)) == Span(0, 0)


def test_the_neighbours_of_a_span_are_reachable() -> None:
    """``2.4`` occurs inside ``2.40``. Resolution has to see what sits either
    side of a match, or a longer number grounds a shorter one."""
    form = search_form("weighs 2.40 kilograms")
    at = form.text.index("2.4")
    span = Span(at, at + 3)
    assert form.character_before(span) == " "
    assert form.character_after(span) == "0"


def test_the_neighbours_at_the_edges_are_empty_rather_than_an_error() -> None:
    form = search_form("2.4")
    whole = Span(0, len(form.text))
    assert form.character_before(whole) == ""
    assert form.character_after(whole) == ""


def test_a_search_form_whose_map_disagrees_with_its_text_is_refused() -> None:
    with pytest.raises(ValueError, match="disagree"):
        SearchForm(original="ab", text="ab", origin=(0,), extent=(1,))


# --- Properties --------------------------------------------------------------

TEXT = st.text(
    alphabet=st.characters(
        codec="utf-8",
        # Surrogates cannot be encoded and never arrive from a JSON document or
        # a file read as text. Excluding them keeps the generator honest rather
        # than testing a case that cannot occur.
        # Annotated because `strict` reads a bare tuple as `tuple[str]`, and
        # hypothesis wants the literal. The value was always right; the type
        # was not carrying which strings are allowed.
        exclude_categories=cast("Collection[Any]", ("Cs",)),
    ),
    max_size=120,
)


@given(text=TEXT)
def test_reducing_a_reduced_form_changes_nothing(text: str) -> None:
    once = search_form(text).text
    assert search_form(once).text == once


@given(text=TEXT)
def test_the_reduced_form_never_carries_edge_or_doubled_whitespace(text: str) -> None:
    form = search_form(text)
    assert form.text == form.text.strip()
    assert "  " not in form.text
    assert not any(character.isspace() and character != " " for character in form.text)


@given(text=TEXT)
def test_the_map_is_the_same_length_as_the_reduced_text(text: str) -> None:
    form = search_form(text)
    assert len(form.origin) == len(form.text) == len(form.extent)


@given(text=TEXT)
def test_the_map_never_points_outside_the_original(text: str) -> None:
    form = search_form(text)
    for start, end in zip(form.origin, form.extent, strict=True):
        assert 0 <= start < end <= len(form.original)


@given(text=TEXT)
def test_the_map_only_moves_forwards(text: str) -> None:
    """Reduction never reorders. A map that went backwards would let a later
    match report an earlier offset, which is an offset that is simply wrong."""
    form = search_form(text)
    assert list(form.origin) == sorted(form.origin)
    assert list(form.extent) == sorted(form.extent)


@given(data=st.data(), text=TEXT)
def test_a_recovered_span_contains_everything_the_reduced_span_referred_to(
    data: st.DataObject, text: str
) -> None:
    """The round trip, as an invariant rather than an example.

    Containment rather than equality, because a span may cut through an
    expansion: half of ``ﬁ`` recovers the whole character, so re-reducing gives
    ``fi`` where the span said ``f``. Recovering *more* than was asked for is
    safe; recovering less would hand a reader the wrong text.
    """
    form = search_form(text)
    assume(form.text)

    start = data.draw(st.integers(0, len(form.text) - 1))
    end = data.draw(st.integers(start + 1, len(form.text)))
    wanted = form.text[start:end].strip()

    recovered = form.to_original(Span(start, end))
    assert recovered.end <= len(form.original)
    assert wanted in search_form(recovered.slice(form.original)).text


@given(text=TEXT)
def test_the_whole_reduced_form_recovers_the_whole_of_the_original_that_matters(
    text: str,
) -> None:
    form = search_form(text)
    assume(form.text)
    recovered = form.to_original(Span(0, len(form.text)))
    assert search_form(recovered.slice(form.original)).text == form.text


@given(text=TEXT)
def test_reduction_agrees_with_unicode_on_a_string_with_no_whitespace(text: str) -> None:
    """The whitespace rule is akashi's; the rest is Unicode's. Where there is
    no whitespace to collapse, the two must give the same answer -- otherwise
    the chunking that keeps the offsets has changed what the tolerance means.
    """
    assume(not any(character.isspace() for character in text))
    expected = unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", text).casefold())
    assume(not any(character.isspace() for character in expected))
    assert search_form(text).text == expected
