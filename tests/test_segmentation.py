"""Cutting an answer up, and the invariants that keep the denominator honest.

Every count on a report is over segments, so a change here changes every number
on every report. That is why the tiling invariant is a property test and why
the fixtures are in three scripts rather than one.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from akashi.domain.language import LanguagePack, Script, script_of
from akashi.domain.segment import (
    Boundary,
    Segment,
    Segmentation,
    SegmentKind,
    segment_answer,
)
from akashi.domain.span import Span
from akashi.infrastructure.languages import CHINESE, DEFAULT, ENGLISH, JAPANESE, packs


def cut(answer: str) -> list[str]:
    return [s.text for s in segment_answer(answer, DEFAULT).segments]


# --- Sentences ---------------------------------------------------------------


def test_english_sentences_split_on_the_full_stop() -> None:
    assert cut("The tent is light. It weighs 2.4kg. We took it.") == [
        "The tent is light.",
        "It weighs 2.4kg.",
        "We took it.",
    ]


def test_japanese_sentences_split_without_a_space() -> None:
    assert cut("テントは軽い。重さは 2.4kg。前回より 300g 軽い。") == [
        "テントは軽い。",
        "重さは 2.4kg。",
        "前回より 300g 軽い。",
    ]


def test_chinese_sentences_split_without_a_space() -> None:
    assert cut("帐篷很轻。重 2.4 公斤。比上次轻 300 克。") == [
        "帐篷很轻。",
        "重 2.4 公斤。",
        "比上次轻 300 克。",
    ]


def test_a_mixed_script_paragraph_splits_at_both_kinds_of_terminator() -> None:
    """ADR-0011, and the reason it exists. Under per-document selection the
    dominant script is Japanese, the English sentence never ends, and one
    verdict covers two sentences."""
    assert cut("テントは軽い。The tent is light. 重さは 2.4kg。") == [
        "テントは軽い。",
        "The tent is light.",
        "重さは 2.4kg。",
    ]


def test_a_decimal_point_is_not_a_sentence_end() -> None:
    assert cut("It weighs 2.4 kilograms in total.") == ["It weighs 2.4 kilograms in total."]


def test_a_domain_name_is_not_a_sentence_end() -> None:
    assert cut("See example.com for details.") == ["See example.com for details."]


@pytest.mark.parametrize(
    "answer",
    [
        "See Fig. 2 for the layout.",
        "The dose is 5mg b.i.d. for one week.",
        "Refer to Art. 30 of the contract.",
        "Contact Dr. Tanaka about it.",
        "Bring a tent, e.g. the two-person one.",
        "Acme Inc. supplied the parts.",
        "The total is approx. 4.8kg overall.",
    ],
)
def test_an_abbreviation_is_not_a_sentence_end(answer: str) -> None:
    assert cut(answer) == [answer]


def test_an_initial_is_not_a_sentence_end() -> None:
    assert cut("The report is by J. Smith and others.") == ["The report is by J. Smith and others."]


def test_a_question_and_an_exclamation_end_a_sentence_once() -> None:
    assert cut("Is it light? Yes! Very.") == ["Is it light?", "Yes!", "Very."]


def test_a_run_of_marks_ends_one_sentence() -> None:
    assert cut("Is it light?! Yes.") == ["Is it light?!", "Yes."]


def test_an_ellipsis_does_not_split() -> None:
    """Deliberate under-segmentation. Merging two sentences moves a
    denominator; splitting one invents a segment, and only the second can
    invent a finding."""
    assert cut("It was light... and cheap.") == ["It was light... and cheap."]


def test_a_sentence_does_not_end_inside_a_japanese_quotation() -> None:
    assert cut("「テントは軽い。」と書いてある。重さは 2.4kg。") == [
        "「テントは軽い。」と書いてある。",
        "重さは 2.4kg。",
    ]


def test_a_bracketed_sentence_merges_with_what_follows_it() -> None:
    """Under-segmentation, on purpose.

    Telling ``（軽い。）重さは 2.4kg。`` -- two sentences -- apart from
    ``「軽い。」と書いてある。`` -- one -- needs the particle that follows the
    closing bracket, which is language-specific vocabulary rather than a rule.
    Until that is worth building, both merge: a longer span on a report is a
    cost, and a sentence split where there was none is a finding invented.
    """
    assert cut("（テントは軽い。）重さは 2.4kg。") == ["（テントは軽い。）重さは 2.4kg。"]
    assert cut("「テントは軽い。」と書いてある。") == ["「テントは軽い。」と書いてある。"]


def test_text_after_the_last_terminator_is_still_a_segment() -> None:
    """A truncated answer is exactly the kind of thing worth auditing, so the
    tail is not dropped for being unfinished."""
    segments = segment_answer("It is light. It weighs", DEFAULT).segments
    assert [s.text for s in segments] == ["It is light.", "It weighs"]
    assert segments[-1].boundary is Boundary.END


# --- Structure ---------------------------------------------------------------


def test_a_table_row_is_a_segment_of_its_own() -> None:
    """A model answering about figures replies with a table. Flattening one
    into a sentence loses every particular's position."""
    answer = "Weights:\n\n| Item | Mass |\n|---|---|\n| Tent | 2.4kg |\n| Stove | 300g |"
    segmentation = segment_answer(answer, DEFAULT)
    rows = segmentation.of_kind(SegmentKind.TABLE_ROW)
    assert [row.text for row in rows] == [
        "| Item | Mass |",
        "|---|---|",
        "| Tent | 2.4kg |",
        "| Stove | 300g |",
    ]


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("# Findings", SegmentKind.HEADING),
        ("### Findings", SegmentKind.HEADING),
        ("- the tent weighs 2.4kg", SegmentKind.LIST_ITEM),
        ("* the tent weighs 2.4kg", SegmentKind.LIST_ITEM),
        ("・テントは 2.4kg", SegmentKind.LIST_ITEM),
        ("1. the tent weighs 2.4kg", SegmentKind.LIST_ITEM),
        ("2) the tent weighs 2.4kg", SegmentKind.LIST_ITEM),
        ("| Tent | 2.4kg |", SegmentKind.TABLE_ROW),
        ("> quoted from the source", SegmentKind.QUOTE),
    ],
)
def test_structure_is_recognised_as_itself(line: str, kind: SegmentKind) -> None:
    segments = segment_answer(line, DEFAULT).segments
    assert [s.kind for s in segments] == [kind]
    assert segments[0].boundary is Boundary.STRUCTURE


def test_a_hash_without_a_space_is_not_a_heading() -> None:
    assert segment_answer("#1 is the tent.", DEFAULT).segments[0].kind is SegmentKind.PROSE


def test_a_fenced_code_block_is_one_segment_and_is_never_split() -> None:
    answer = "Run this.\n\n```python\nx = 1.5\ny = 2.5\n```\n\nThat is all."
    segmentation = segment_answer(answer, DEFAULT)
    code = segmentation.of_kind(SegmentKind.CODE)
    assert len(code) == 1
    assert code[0].text == "```python\nx = 1.5\ny = 2.5\n```"
    assert code[0].is_code


def test_an_unclosed_fence_runs_to_the_end_rather_than_being_refused() -> None:
    answer = "Here:\n\n```\nx = 1\ny = 2"
    code = segment_answer(answer, DEFAULT).of_kind(SegmentKind.CODE)
    assert code[0].text == "```\nx = 1\ny = 2"


def test_a_paragraph_spans_its_own_line_breaks() -> None:
    """A newline inside a paragraph is not a sentence boundary. A model wraps
    where its renderer wrapped, which is nowhere in particular."""
    assert cut("The tent is\nlight. It weighs\n2.4kg.") == [
        "The tent is\nlight.",
        "It weighs\n2.4kg.",
    ]


# --- The fallback ------------------------------------------------------------


def test_a_prose_block_with_no_terminator_falls_back_to_lines() -> None:
    segmentation = segment_answer("テントは 2.4kg\nシュラフは 800g", DEFAULT)
    assert [s.text for s in segmentation.segments] == ["テントは 2.4kg", "シュラフは 800g"]
    assert all(s.boundary is Boundary.LINE for s in segmentation.segments)


def test_the_fallback_share_is_reported() -> None:
    """ADR-0009 owes an account of how much of an answer was cut by the weaker
    rule, and a report can only say it if the segmentation counts it."""
    segmentation = segment_answer("It is light. It weighs 2.4kg.", DEFAULT)
    assert segmentation.fallback_share == 0.0
    assert segment_answer("テントは 2.4kg", DEFAULT).fallback_share == 1.0


def test_the_fallback_share_is_by_characters_not_by_segments() -> None:
    """One unsegmented paragraph and one short sentence are not the same amount
    of answer."""
    answer = "It is light.\n\n" + "テントは 2.4kg で軽く前回より 300g 軽い"
    share = segment_answer(answer, DEFAULT).fallback_share
    assert 0.5 < share < 1.0


# --- What a segmentation guarantees ------------------------------------------


def test_a_segmentation_names_the_packs_that_produced_it() -> None:
    segmentation = segment_answer("It is light.", DEFAULT)
    assert segmentation.segmenters == (
        "akashi.segmenter/en@1",
        "akashi.segmenter/ja@1",
        "akashi.segmenter/zh@1",
    )


def test_segment_ids_are_in_order_and_zero_padded() -> None:
    segmentation = segment_answer("One. Two. Three.", DEFAULT)
    assert [s.segment_id for s in segmentation.segments] == ["seg_001", "seg_002", "seg_003"]


def test_an_empty_answer_produces_no_segments() -> None:
    assert segment_answer("", DEFAULT).segments == ()
    assert segment_answer("   \n\n  ", DEFAULT).segments == ()


def test_segmentation_needs_a_pack() -> None:
    with pytest.raises(ValueError, match="at least one language pack"):
        segment_answer("It is light.", [])


def test_a_segment_may_not_be_empty() -> None:
    with pytest.raises(ValueError, match="asserts something"):
        Segment(
            segment_id="seg_001",
            span=Span(0, 3),
            text="   ",
            kind=SegmentKind.PROSE,
            script=Script.UNKNOWN,
            boundary=Boundary.END,
        )


def test_a_segment_whose_span_disagrees_with_its_text_is_refused() -> None:
    with pytest.raises(ValueError, match="offset that has drifted"):
        Segment(
            segment_id="seg_001",
            span=Span(0, 99),
            text="short",
            kind=SegmentKind.PROSE,
            script=Script.LATIN,
            boundary=Boundary.END,
        )


def test_a_segmentation_refuses_a_segment_that_does_not_slice_back() -> None:
    with pytest.raises(ValueError, match="does not slice back"):
        Segmentation(
            answer="The tent is light.",
            segments=(
                Segment(
                    segment_id="seg_001",
                    span=Span(0, 4),
                    text="tent",
                    kind=SegmentKind.PROSE,
                    script=Script.LATIN,
                    boundary=Boundary.END,
                ),
            ),
        )


def test_a_segmentation_refuses_to_lose_text_between_segments() -> None:
    answer = "One. Two."
    with pytest.raises(ValueError, match="is in no segment"):
        Segmentation(
            answer=answer,
            segments=(
                Segment(
                    segment_id="seg_001",
                    span=Span(5, 9),
                    text="Two.",
                    kind=SegmentKind.PROSE,
                    script=Script.LATIN,
                    boundary=Boundary.END,
                ),
            ),
        )


# --- Packs -------------------------------------------------------------------


def test_the_packs_agree_about_the_characters_they_share() -> None:
    """ADR-0011: a disagreement would mean the answer depended on which pack
    imported first, and that is not reproducible."""
    shared = JAPANESE.terminators & CHINESE.terminators
    assert shared
    assert JAPANESE.needs_space_after == CHINESE.needs_space_after


def test_packs_that_disagree_about_a_shared_terminator_are_refused() -> None:
    contradictory = LanguagePack(
        code="xx", version=1, terminators=frozenset("。"), needs_space_after=True
    )
    with pytest.raises(ValueError, match="disagree about"):
        segment_answer("テントは軽い。", [JAPANESE, contradictory])


def test_a_pack_must_claim_a_terminator() -> None:
    with pytest.raises(ValueError, match="claims no terminators"):
        LanguagePack(code="xx", version=1, terminators=frozenset(), needs_space_after=False)


def test_a_terminator_is_one_character() -> None:
    with pytest.raises(ValueError, match="not one character"):
        LanguagePack(code="xx", version=1, terminators=frozenset({"。。"}), needs_space_after=False)


def test_abbreviations_without_a_space_rule_would_never_be_read() -> None:
    with pytest.raises(ValueError, match="would never be consulted"):
        LanguagePack(
            code="xx",
            version=1,
            terminators=frozenset("。"),
            needs_space_after=False,
            abbreviations=frozenset({"fig."}),
        )


def test_narrowing_the_pack_set_is_possible_for_measurement() -> None:
    assert packs("ja") == (JAPANESE,)
    assert packs() == DEFAULT
    assert packs("zh", "en") == (ENGLISH, CHINESE)


def test_an_unknown_language_is_refused_rather_than_ignored() -> None:
    with pytest.raises(ValueError, match="no language pack for"):
        packs("ko")


def test_narrowing_the_packs_under_segments_which_is_why_it_is_not_a_default() -> None:
    """The failure mode ADR-0011 removes. With only the Japanese pack loaded,
    the two English sentences merge into one verdict, so one floating
    particular would condemn a grounded one."""
    answer = "テントは軽い。The tent is light. It weighs 2.4kg。"
    assert len(segment_answer(answer, DEFAULT).segments) == 3
    assert len(segment_answer(answer, packs("ja")).segments) == 2


# --- Script detection --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "script"),
    [
        ("The tent is light.", Script.LATIN),
        ("テントは軽い。", Script.JAPANESE),
        ("帐篷很轻。", Script.CHINESE),
        ("2.4kg のテント", Script.JAPANESE),
        ("2.4kg", Script.LATIN),
        ("2.4", Script.UNKNOWN),
        ("", Script.UNKNOWN),
    ],
)
def test_the_dominant_script_is_labelled_for_reporting(text: str, script: Script) -> None:
    assert script_of(text) == script


def test_kana_decides_however_much_han_surrounds_it() -> None:
    assert script_of("東京都港区の事務所は") is Script.JAPANESE


def test_kanji_only_japanese_is_labelled_chinese_and_that_is_stated() -> None:
    """A reporting error, not a segmentation error. ADR-0011 owns it: fixing it
    would need a dictionary or a model, and both are refused."""
    assert script_of("東京都港区") is Script.CHINESE


# --- Properties --------------------------------------------------------------

#: Fragments rather than characters, so that the generator produces answers
#: with the shapes a model actually emits -- a table row, a fence, a wrapped
#: line -- instead of only well-formed prose. A property that only ever sees
#: prose is a property that does not cover the structure pass.
_FRAGMENTS = (
    list("abcdefgh ")
    + list("0123456789.,!?")
    + list("テントは軽い重さ")
    + list("帐篷很轻重")
    + ["。", "、", "！", "？", "「", "」", "（", "）", "\n", "\n\n", "- ", "# ", "| ", "> ", "```"]
)

ANSWERS = st.lists(st.sampled_from(_FRAGMENTS), max_size=120).map("".join)


@given(answer=ANSWERS)
def test_every_segment_slices_back_to_its_own_text(answer: str) -> None:
    for segment in segment_answer(answer, DEFAULT).segments:
        assert answer[segment.span.start : segment.span.end] == segment.text


@given(answer=ANSWERS)
def test_segments_are_ordered_and_never_overlap(answer: str) -> None:
    segments = segment_answer(answer, DEFAULT).segments
    for earlier, later in itertools.pairwise(segments):
        assert earlier.span.end <= later.span.start
        assert not earlier.span.overlaps(later.span)


@given(answer=ANSWERS)
def test_nothing_but_whitespace_falls_between_segments(answer: str) -> None:
    """The tiling invariant, in the strongest form that is true. Manufacturing
    empty segments to cover the blank lines would tile it literally, at the
    price of a denominator full of segments that assert nothing."""
    segments = segment_answer(answer, DEFAULT).segments
    at = 0
    for segment in segments:
        assert not answer[at : segment.span.start].strip()
        at = segment.span.end
    assert not answer[at:].strip()


@given(answer=ANSWERS)
def test_no_segment_is_empty(answer: str) -> None:
    assert all(segment.text.strip() for segment in segment_answer(answer, DEFAULT).segments)


@given(answer=ANSWERS)
def test_segmenting_twice_gives_the_same_segments(answer: str) -> None:
    """ADR-0003. Same inputs, same report, and the report is built on these."""
    assert segment_answer(answer, DEFAULT) == segment_answer(answer, DEFAULT)


@given(answer=ANSWERS)
def test_the_segments_reconstruct_the_answer_apart_from_whitespace(answer: str) -> None:
    segments = segment_answer(answer, DEFAULT).segments
    rejoined = "".join(segment.text for segment in segments)
    assert "".join(rejoined.split()) == "".join(answer.split())
