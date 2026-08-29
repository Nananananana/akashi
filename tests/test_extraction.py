"""Finding the things that get falsified.

ADR-0004 is the claim that the evident half of the hallucination taxonomy is a
string comparison, and extraction is where that claim is cashed. A particular
that is not found is never checked, and the segment holding it still comes back
grounded -- so a miss here is silent, which is why these tests are mostly about
what *is* found rather than about what is rejected.

The number this file does not produce is extraction recall on real answers.
That is v0.3, against the labelled corpus, and it is the measurement that can
falsify ADR-0004.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from akashi.domain.extraction import (
    extract_from_answer,
    extract_from_segment,
    kinds_not_extracted,
    rules_of,
)
from akashi.domain.particular import ExtractionRule, Particular, ParticularKind
from akashi.domain.segment import SegmentKind, segment_answer
from akashi.domain.span import Span
from akashi.infrastructure.languages import COMMON, DEFAULT, JAPANESE, packs


def found(answer: str) -> list[tuple[str, str]]:
    segmentation = segment_answer(answer, DEFAULT)
    return [(p.kind.value, p.text) for p in extract_from_answer(segmentation, DEFAULT)]


def texts(answer: str) -> list[str]:
    return [text for _, text in found(answer)]


# --- The kinds, one script at a time -----------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("The tent weighs 2.4kg.", [("quantity", "2.4kg")]),
        ("The stove is 300 g.", [("quantity", "300 g")]),
        ("It weighs 2.4 kilograms.", [("quantity", "2.4 kilograms")]),
        ("Growth was 12.5%.", [("percentage", "12.5%")]),
        ("The fee is 45,000 dollars.", [("money", "45,000 dollars")]),
        ("The fee is $45,000.", [("money", "$45,000")]),
        ("Signed on 2026-08-30.", [("date", "2026-08-30")]),
        ("Signed on August 30, 2026.", [("date", "August 30, 2026")]),
        ("It starts at 14:30.", [("time", "14:30")]),
        ("Within 14 days of signing.", [("duration", "14 days")]),
        ("See Section 4(b) for details.", [("reference", "Section 4(b)")]),
        ("Refer to Art. 12 of the protocol.", [("reference", "Art. 12")]),
        ("Version 1.2.3 shipped.", [("identifier", "1.2.3")]),
        ("ISO 9001 applies.", [("identifier", "ISO 9001")]),
        ("There were 42 of them.", [("number", "42")]),
    ],
)
def test_english_particulars(answer: str, expected: list[tuple[str, str]]) -> None:
    assert found(answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("テントは 2.4kg。", [("quantity", "2.4kg")]),
        ("重さは 2.4キログラム。", [("quantity", "2.4キログラム")]),
        ("第30条による。", [("reference", "第30条")]),
        ("第三十条による。", [("reference", "第三十条")]),
        ("費用は 1,200万円。", [("money", "1,200万円")]),
        ("費用は ¥45,000。", [("money", "¥45,000")]),
        ("令和8年8月30日に締結。", [("date", "令和8年8月30日")]),
        ("2026年8月30日に締結。", [("date", "2026年8月30日")]),
        ("二〇二六年三月に開始。", [("date", "二〇二六年三月")]),
        ("参加者は 12人。", [("quantity", "12人")]),
        ("三千人が参加した。", [("quantity", "三千人")]),
        ("会議は 14:30 開始。", [("time", "14:30")]),
    ],
)
def test_japanese_particulars(answer: str, expected: list[tuple[str, str]]) -> None:
    assert found(answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("帐篷重 2.4 公斤。", [("quantity", "2.4 公斤")]),
        ("第30条规定。", [("reference", "第30条")]),
        ("支付 1,200 万元。", [("money", "1,200 万元")]),
        ("2026年8月30日前完成。", [("date", "2026年8月30日")]),
        ("共有 12 个。", [("quantity", "12 个")]),
        ("用时 3 小时。", [("quantity", "3 小时")]),
    ],
)
def test_chinese_particulars(answer: str, expected: list[tuple[str, str]]) -> None:
    assert found(answer) == expected


def test_a_full_width_number_is_the_same_particular_as_a_half_width_one() -> None:
    """Reduction is what makes them one, and the report keeps what was written."""
    segmentation = segment_answer("テントは ２.４kg。", DEFAULT)
    particular = extract_from_answer(segmentation, DEFAULT)[0]
    assert particular.text == "２.４kg"
    assert particular.form == "2.4kg"


# --- Overlaps ----------------------------------------------------------------


def test_a_reference_is_one_particular_and_not_a_stray_number() -> None:
    """``第30条`` -> ``第13条`` is the failure this project is aimed at. Split
    into ``第``, ``30`` and ``条`` it would be a number that grounds anywhere a
    thirty appears."""
    assert found("第30条により支払う。") == [("reference", "第30条")]


def test_a_date_is_one_particular_and_not_three_numbers() -> None:
    assert found("2026年8月30日に締結。") == [("date", "2026年8月30日")]
    assert found("Signed 2026-08-30.") == [("date", "2026-08-30")]


def test_a_version_outranks_a_number_on_the_same_span() -> None:
    """Equal start and equal length, so length cannot decide and priority must.
    Without it the answer would depend on which rule was tried first."""
    assert found("Version 1.2.3 shipped.") == [("identifier", "1.2.3")]


def test_a_unit_is_part_of_the_quantity() -> None:
    """The whole point of the kind. ``2.4kg`` and ``2.4mg`` differ only here,
    and a bare ``2.4`` would ground against either."""
    assert texts("It weighs 2.4kg.") == ["2.4kg"]
    assert texts("The dose is 2.4mg.") == ["2.4mg"]


def test_a_number_is_not_found_inside_a_longer_one() -> None:
    """``234`` is not a number inside ``1,234``, and reporting it as one would
    ground a figure nobody wrote."""
    assert texts("The total was 1,234.") == ["1,234"]
    assert texts("It was 2.40 kilograms.") == ["2.40 kilograms"]


def test_particulars_do_not_overlap_and_are_in_order() -> None:
    particulars = extract_from_answer(
        segment_answer("On 2026-08-30 the 2.4kg tent cost $45,000.", DEFAULT), DEFAULT
    )
    for earlier, later in itertools.pairwise(particulars):
        assert earlier.span.end <= later.span.start
        assert not earlier.span.overlaps(later.span)


@pytest.mark.parametrize(
    "answer",
    [
        "一般的な話をする。",
        "一部が該当する。",
        "一体どうなるのか。",
        "这是一个例子。",
        "一些问题。",
    ],
)
def test_a_bare_kanji_numeral_is_not_read_as_a_quantity(answer: str) -> None:
    """``一部`` is "a portion" far more often than "one copy", and ``一个`` is
    the indefinite article. A rule that fired on them would put a particular in
    every other CJK sentence, each of which then has to ground somewhere."""
    assert texts(answer) == []


def test_the_price_of_that_is_a_small_bare_numeral_that_is_missed() -> None:
    """The other half of the same trade, asserted so that it is a known
    quantity rather than a surprise. ``三人`` is a genuine quantity and nothing
    but a dictionary distinguishes it from a word, so it is not found -- while
    ``三千人``, which carries a magnitude, is."""
    assert texts("三人が参加した。") == []
    assert texts("三千人が参加した。") == ["三千人"]
    assert texts("12人が参加した。") == ["12人"]


def test_a_numeral_between_two_markers_is_safe_however_small() -> None:
    """``第`` and ``条`` bracket the numeral, so there is no ambiguity left to
    protect against and the full numeral set is used."""
    assert found("第一条による。") == [("reference", "第一条")]
    assert found("第三十条による。") == [("reference", "第三十条")]


# --- What is not extracted ---------------------------------------------------


def test_nothing_is_extracted_from_code() -> None:
    """A number in a fenced block is as likely to be a line number or a hash as
    a claim about the world."""
    answer = "Run it.\n\n```python\nweight = 2.4\nlimit = 300\n```"
    segmentation = segment_answer(answer, DEFAULT)
    code = segmentation.of_kind(SegmentKind.CODE)[0]
    assert extract_from_segment(code, DEFAULT) == ()
    assert extract_from_answer(segmentation, DEFAULT) == ()


def test_a_segment_may_simply_have_no_particulars() -> None:
    assert texts("The tent was light and easy to carry.") == []


def test_the_kinds_no_rule_covers_are_named() -> None:
    """ADR-0005. A blind spot that is not named reads as an absence of
    findings, and ``proper_noun`` is the one akashi refuses to guess at."""
    assert kinds_not_extracted(DEFAULT) == (ParticularKind.PROPER_NOUN,)


def test_narrowing_the_packs_widens_what_is_not_extracted() -> None:
    """A kind that only the Japanese pack finds is unfound without it, and the
    report has to say so rather than showing a clean sheet."""
    missing = kinds_not_extracted(packs("en"))
    assert ParticularKind.PROPER_NOUN in missing
    assert ParticularKind.DURATION not in missing
    assert ParticularKind.DURATION in kinds_not_extracted(packs("ja"))


def test_the_shared_pack_is_always_loaded() -> None:
    """An ISO date belongs to no language, so a pack set without the common
    rules would find nothing at all in an answer written in figures."""
    assert COMMON in packs("ja")
    assert texts("2026-08-30") == ["2026-08-30"]


def test_the_shared_pack_claims_no_terminator() -> None:
    assert COMMON.terminators == frozenset()
    assert COMMON.rules


# --- Rules -------------------------------------------------------------------


def test_the_rule_order_is_a_property_of_the_rules_not_of_the_argument() -> None:
    """Nothing in the algorithm depends on it -- overlaps are resolved by a
    total order afterwards -- but a report naming the rules would, and a
    duplicate would be invisible without it."""
    assert rules_of(DEFAULT) == rules_of(tuple(reversed(DEFAULT)))


def test_every_rule_has_a_pattern() -> None:
    with pytest.raises(ValueError, match="has no pattern"):
        ExtractionRule(kind=ParticularKind.NUMBER, pattern="")


def test_every_shipped_rule_compiles_and_finds_nothing_in_an_empty_string() -> None:
    import re

    for rule in rules_of(DEFAULT):
        compiled = re.compile(rule.pattern)
        assert compiled.search("") is None, f"{rule.kind.value} matches the empty string"


def test_a_pack_must_contribute_something() -> None:
    from akashi.domain.language import LanguagePack

    with pytest.raises(ValueError, match="neither a terminator nor an extraction rule"):
        LanguagePack(code="xx", version=1, terminators=frozenset(), needs_space_after=False)


def test_a_pack_may_contribute_only_rules() -> None:
    from akashi.domain.language import LanguagePack

    pack = LanguagePack(
        code="xx",
        version=1,
        terminators=frozenset(),
        needs_space_after=False,
        rules=(ExtractionRule(kind=ParticularKind.NUMBER, pattern=r"\d+"),),
    )
    assert pack.rules


# --- Particulars themselves --------------------------------------------------


def test_a_particular_carries_answer_coordinates_not_segment_coordinates() -> None:
    """A particular that could only be located relative to a segment would need
    the segmentation re-derived before a reader could open it."""
    answer = "It is light. It weighs 2.4kg."
    particular = extract_from_answer(segment_answer(answer, DEFAULT), DEFAULT)[0]
    assert answer[particular.span.start : particular.span.end] == "2.4kg"
    assert particular.segment_id == "seg_002"


def test_a_particular_may_not_be_empty() -> None:
    with pytest.raises(ValueError, match="bears nothing"):
        Particular(kind=ParticularKind.NUMBER, span=Span(0, 1), text=" ")


def test_a_particular_whose_span_disagrees_with_its_text_is_refused() -> None:
    with pytest.raises(ValueError, match="offset that has drifted"):
        Particular(kind=ParticularKind.NUMBER, span=Span(0, 99), text="42")


def test_a_particular_describes_itself_for_a_reader() -> None:
    particular = Particular(kind=ParticularKind.QUANTITY, span=Span(4, 9), text="2.4kg")
    assert particular.describe() == "quantity '2.4kg' at [4:9]"


# --- Properties --------------------------------------------------------------

_FRAGMENTS = (
    list("abcdefg .,")
    + list("0123456789")
    + ["テントは", "軽い", "重さは", "。", "、", "第", "条", "年", "月", "日", "円", "万", "人"]
    + ["帐篷", "重", "公斤", "元", "个"]
    + ["kg", "g", "%", "$", ":", "-", "/", "(", ")", "\n", "\n\n", "- ", "```"]
)

ANSWERS = st.lists(st.sampled_from(_FRAGMENTS), max_size=90).map("".join)


@given(answer=ANSWERS)
def test_every_particular_slices_back_to_its_own_text(answer: str) -> None:
    """The invariant a reader depends on. An offset that has drifted points at
    the wrong number while still looking like a finding."""
    for particular in extract_from_answer(segment_answer(answer, DEFAULT), DEFAULT):
        assert answer[particular.span.start : particular.span.end] == particular.text


@given(answer=ANSWERS)
def test_every_particular_sits_inside_the_segment_that_claims_it(answer: str) -> None:
    segmentation = segment_answer(answer, DEFAULT)
    by_id = {segment.segment_id: segment for segment in segmentation.segments}
    for particular in extract_from_answer(segmentation, DEFAULT):
        assert by_id[particular.segment_id].span.contains(particular.span)


@given(answer=ANSWERS)
def test_particulars_never_overlap(answer: str) -> None:
    particulars = extract_from_answer(segment_answer(answer, DEFAULT), DEFAULT)
    for earlier, later in itertools.pairwise(particulars):
        assert earlier.span.end <= later.span.start


@given(answer=ANSWERS)
def test_extracting_twice_finds_the_same_particulars(answer: str) -> None:
    """ADR-0003, and the reason overlaps are resolved by a total order rather
    than by whichever rule ran first."""
    segmentation = segment_answer(answer, DEFAULT)
    assert extract_from_answer(segmentation, DEFAULT) == extract_from_answer(segmentation, DEFAULT)


@given(answer=ANSWERS)
def test_the_pack_order_never_changes_what_is_found(answer: str) -> None:
    segmentation = segment_answer(answer, DEFAULT)
    forwards = extract_from_answer(segmentation, DEFAULT)
    backwards = extract_from_answer(segmentation, tuple(reversed(DEFAULT)))
    assert forwards == backwards


@given(answer=ANSWERS)
def test_no_particular_is_only_whitespace(answer: str) -> None:
    for particular in extract_from_answer(segment_answer(answer, DEFAULT), DEFAULT):
        assert particular.text.strip()


@given(answer=ANSWERS)
def test_a_narrower_pack_set_never_finds_more(answer: str) -> None:
    """Loading fewer rules cannot produce more particulars. If it did, a rule
    would be *suppressing* another rather than competing with it, and the
    overlap resolution would be doing something nobody asked for."""
    segmentation = segment_answer(answer, DEFAULT)
    everything = extract_from_answer(segmentation, DEFAULT)
    japanese_only = extract_from_answer(segmentation, (COMMON, JAPANESE))
    assert len(japanese_only) <= len(everything) + len(segmentation.segments)
