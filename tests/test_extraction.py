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
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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
    """`pairwise` over nothing yields nothing, so this passed with extraction
    returning `()` -- and the answer below is written to hold three particulars
    precisely so that the invariant has something to be true of. The population
    is asserted before it is iterated."""
    particulars = extract_from_answer(
        segment_answer("On 2026-08-30 the 2.4kg tent cost $45,000.", DEFAULT), DEFAULT
    )
    assert len(particulars) >= 3, (
        f"this answer holds a date, a quantity and an amount; extraction found "
        f"{len(particulars)}, so there is no pair for the invariant to hold between"
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


def test_every_kind_is_covered_by_some_rule_now() -> None:
    """``proper_noun`` was the last one, until the structural rules shipped in
    v0.4. An empty tuple here does *not* mean akashi sees every name: it reads
    structure, not names, and that limit moved to ``STANDING_LIMITS`` where a
    permanent one belongs."""
    assert kinds_not_extracted(DEFAULT) == ()


def test_narrowing_the_packs_widens_what_is_not_extracted() -> None:
    """A kind that only the Japanese pack finds is unfound without it, and the
    report has to say so rather than showing a clean sheet."""
    assert ParticularKind.DURATION not in kinds_not_extracted(packs("en"))
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


# --- the cost of an audit is bounded, and the input is untrusted -------------
#
# akashi audits text a model produced, and `akashi mcp` lets the model choose
# the arguments. So the length of an answer is an attacker-controlled number,
# and the shape 32 of the 40 shipped rules have -- a long numeric run followed
# by a unit that is not there -- made extraction quadratic in it.
#
#     16,000 characters of ordinary prose    0.09 s
#     16,000 characters of digits           38.09 s     x4.0 per doubling
#
# `_bounded` caps every repetition at `MAX_RUN`. These are the checks that make
# that safe to do and keep it done.


def test_no_shipped_rule_compiles_to_an_unbounded_repeat() -> None:
    """The structural guard, and the one that cannot be flaky.

    A timing test says the cost is acceptable on this machine today. This says
    the shape that produced the cost is not there at all -- including in a rule
    added later, and including shapes `_bounded` was not written for, because
    it reads the compiled pattern with `re`'s own parser rather than the
    pattern text.
    """
    import re._constants as constants  # type: ignore[import-not-found]
    import re._parser as parser  # type: ignore[import-not-found]

    from akashi.domain.extraction import _compiled, rules_of
    from akashi.infrastructure.languages import DEFAULT

    def repeats(tree: Any) -> Iterator[Any]:
        for operation, argument in tree:
            if operation in (
                constants.MAX_REPEAT,
                constants.MIN_REPEAT,
                constants.POSSESSIVE_REPEAT,
            ):
                yield argument[1]
                yield from repeats(argument[2])
            elif operation is constants.SUBPATTERN:
                yield from repeats(argument[3])
            elif operation is constants.BRANCH:
                for branch in argument[1]:
                    yield from repeats(branch)
            elif operation in (constants.ASSERT, constants.ASSERT_NOT):
                yield from repeats(argument[1])

    unbounded: list[str] = []
    for rule in rules_of(DEFAULT):
        # `_compiled` and not `_bounded`: the question is what extraction runs,
        # not what a helper would return if something called it. Written the
        # other way round first, and removing the bound from `_compiled` left
        # this test green -- it was checking the ingredient, not the dish.
        used = _compiled(rule.pattern).pattern
        if any(most is constants.MAXREPEAT for most in repeats(parser.parse(used))):
            unbounded.append(f"{rule.kind.value}: {rule.pattern[:60]}")

    assert not unbounded, (
        "an unbounded repetition makes extraction quadratic in the length of a "
        "segment, and the segment is text somebody else wrote:\n  " + "\n  ".join(unbounded)
    )


def test_the_bound_changes_nothing_the_corpus_extracts() -> None:
    """A rewritten rule is not the rule as written, so this is the check that
    makes rewriting them safe: every particular, in the same order, at the same
    offsets, from every case and every evidence item in the corpus.

    The longest particular in that corpus is 21 characters and `MAX_RUN` is
    256, so there is an order of magnitude between the bound and anything real
    -- which is what this asserts, rather than that 256 happens to work.
    """
    from akashi.domain import extraction
    from akashi.domain.segment import segment_answer
    from akashi.evaluation import load_cases
    from akashi.infrastructure.languages import DEFAULT

    cases = load_cases(Path(__file__).parent / "cases")
    assert cases, "no corpus, so this test would compare nothing to nothing"

    def fingerprint(*, bound: bool) -> list[tuple[object, ...]]:
        extraction._compiled.cache_clear()
        original = extraction._bounded
        if not bound:
            extraction._bounded = lambda pattern, limit=0: pattern
        try:
            found: list[tuple[object, ...]] = []
            for case in cases:
                for text in (case.response, *(item.text for item in case.package.evidence.items)):
                    for one in extraction.extract_from_answer(
                        segment_answer(text, DEFAULT), DEFAULT
                    ):
                        found.append((one.kind.value, one.span.start, one.span.end, one.text))
            return found
        finally:
            extraction._bounded = original
            extraction._compiled.cache_clear()

    unbounded = fingerprint(bound=False)
    bounded = fingerprint(bound=True)
    assert len(bounded) > 300, "the corpus stopped producing particulars; this proves nothing"
    assert bounded == unbounded


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        (r"\d[\d,.]*\d", r"\d[\d,.]{0,256}\d"),
        (r"[a-z]+", r"[a-z]{1,256}"),
        (r"a*?b", r"a{0,256}?b"),
        (r"a*+b", r"a{0,256}+b"),
        (r"\d{2,}", r"\d{2,256}"),
        (r"\d{2,4}", r"\d{2,4}"),
        (r"[*+]x", r"[*+]x"),
        (r"\*literal", r"\*literal"),
        (r"[]]*", r"[]]{0,256}"),
        (r"[^]]+", r"[^]]{1,256}"),
        (r"[\]]*", r"[\]]{0,256}"),
        (r"a?b", r"a?b"),
    ],
)
def test_the_rewriter_reads_a_pattern_the_way_re_does(pattern: str, expected: str) -> None:
    r"""The two places this has to be exactly right are inside a character class
    and after a backslash, which are the two places reading is hardest. `[*+]`
    holds quantifier characters as literals; `\*` is an escaped star; `[]]`
    and `[^]]` hold a literal `]` before the class closes."""
    from akashi.domain.extraction import _bounded

    assert _bounded(pattern) == expected
    re.compile(_bounded(pattern))


def test_a_long_run_costs_time_that_grows_with_its_length_and_not_its_square() -> None:
    """The demonstration rather than the guard -- the structural test above is
    what actually holds the line, because a timing assertion measures a machine.

    **How reliably it goes red under poison, measured rather than assumed.**
    A sibling project found a check of its own that was probabilistic: poisoned,
    it went red 2 times in 12, and "twelve runs, all green" then reads as
    "guarded". So this one was measured the same way, unwiring the bound:

    ..  code-block:: text

        bounded (the real thing)   ratios 2.03 - 2.11   red at >3:  0 of 6
        poisoned (bound removed)   ratios 3.52 - 4.01   red at >3: 12 of 12

    Two populations with a wide gap between them, and the threshold sits in the
    gap. That makes this deterministic in effect rather than merely usually
    right -- but the numbers belong here, because a reader should not have to
    re-derive them to know which of the two kinds of check they are looking at.
    """
    import time

    from akashi.domain.extraction import extract_from_answer
    from akashi.domain.segment import segment_answer
    from akashi.infrastructure.languages import DEFAULT

    def cost(size: int) -> float:
        text = "1" * size
        segmentation = segment_answer(text, DEFAULT)
        start = time.perf_counter()
        extract_from_answer(segmentation, DEFAULT)
        return time.perf_counter() - start

    cost(2000)  # warm the pattern cache, so the first call does not pay for it
    small = cost(4000)
    large = cost(8000)
    assert large < small * 3, (
        f"doubling the input multiplied the cost by {large / small:.1f}; "
        f"quadratic is 4 and linear is 2. Has an unbounded repetition come back?"
    )


# --- a party designation is a name -------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("甲社は乙社に対し支払う。", ["甲社", "乙社"]),
        ("甲方应向乙方支付。", ["甲方", "乙方"]),
        ("丙社も同様とする。", ["丙社"]),
        # The stem alone is a word, not a party. `甲乙` is "the two of them" and
        # `一般` holds no party at all -- precision is the half that would fail
        # quietly, because a false name grounds against nothing and reads as a
        # fabrication in the answer.
        ("甲乙双方の合意による。", []),
        ("一般的な条件は次のとおり。", []),
        ("这是个方法。", []),
    ],
)
def test_a_contract_party_is_extracted_as_a_name(text: str, expected: list[str]) -> None:
    """`甲社` / `乙方` is what a clause is about, and akashi read past it.

    Four of the five particulars the hand-marked corpus said akashi missed were
    these, and the fifth is `Borden Systems` -- a company name with no legal
    form, which no structural rule reaches (see `docs/measurements.md`).

    Structural like every other rule here: the stem is a closed set of five and
    the suffix a closed set of three or four. This reads a convention, not a
    name.
    """
    from akashi.domain.extraction import extract_from_answer
    from akashi.domain.segment import segment_answer
    from akashi.infrastructure.languages import DEFAULT

    found = [
        one.text
        for one in extract_from_answer(segment_answer(text, DEFAULT), DEFAULT)
        if one.kind.value == "proper_noun"
    ]
    assert found == expected


def test_the_chinese_rule_has_no_lookaround_and_the_japanese_one_does() -> None:
    """Not an inconsistency. Japanese has a particle either side to break on;
    Chinese runs straight from a preposition into the party and from the party
    into a verb. Requiring a break on the right found one of the two in the
    corpus, and requiring one on the left found neither.
    """
    from akashi.infrastructure.languages import DEFAULT

    def party_rule(code: str) -> str:
        pack = next(one for one in DEFAULT if one.code == code)
        return next(rule.pattern for rule in pack.rules if "甲乙丙丁戊" in rule.pattern)

    assert "(?<!" in party_rule("ja")
    assert "(?<!" not in party_rule("zh")
