"""Looking for one particular, and the two ways a substring search lies.

Both failures are in the same direction -- reporting a particular as grounded
when it is not there -- which is the direction akashi cannot afford to be wrong
in. A missed match makes a correct answer look worse than it is; a false match
makes a fabricated one look correct.
"""

from __future__ import annotations

import itertools
import re

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from akashi.domain.matching import _RUNS, find_all, pattern_for, required_run
from akashi.domain.span import Span
from akashi.domain.text import search_form


def where(form: str, haystack: str) -> list[str]:
    hay = search_form(haystack)
    return [span.slice(haystack) for span in find_all(form, hay)]


def hits(form: str, haystack: str) -> int:
    return len(find_all(form, search_form(haystack)))


# --- A number inside a longer number -----------------------------------------


@pytest.mark.parametrize(
    ("form", "haystack"),
    [
        ("2.4", "the tent weighs 2.40kg"),
        ("2.4", "the tent weighs 12.4kg"),
        ("2.4", "the tent weighs 12.45kg"),
        ("30", "there were 300 of them"),
        ("30", "there were 130 of them"),
        ("300", "the total was 2.300"),
        ("三千人", "一万三千人が参加した"),
        ("1,200", "the total was 11,200"),
    ],
)
def test_a_number_does_not_ground_against_a_longer_one(form: str, haystack: str) -> None:
    """The failure akashi exists to catch, running backwards. If ``2.4``
    resolved inside ``2.40`` then a changed figure would ground against the
    figure it was changed from."""
    assert where(form, haystack) == []


@pytest.mark.parametrize(
    ("form", "haystack"),
    [
        ("2.4", "the tent weighs 2.4kg"),
        ("2.4kg", "the tent weighs 2.4kg exactly"),
        ("30", "there were 30 of them"),
        ("30", "30 were counted"),
        ("30", "we counted 30"),
        ("三千人", "参加者は三千人だった"),
        ("2026-08-30", "signed on 2026-08-30."),
    ],
)
def test_a_number_that_is_really_there_is_found(form: str, haystack: str) -> None:
    assert len(where(form, haystack)) == 1


def test_a_particle_beside_a_numeral_is_not_a_continuation() -> None:
    """Two of the three languages have no word boundaries. ``\\b`` would reject
    this -- ``は`` is a particle and ``\\w`` cannot tell it from a numeral --
    and would accept ``三千人`` inside ``一万三千人``, which is a different
    number. Comparing character classes gets both right."""
    assert where("三千人", "参加者は三千人でした") == ["三千人"]
    assert where("三千人", "一万三千人でした") == []


def test_a_latin_word_does_not_ground_inside_a_longer_word() -> None:
    assert where("iso 9001", "certified to ISO 9001") == ["ISO 9001"]
    assert where("abc", "abcdef") == []


# --- A quantity written with and without its space ---------------------------


@pytest.mark.parametrize(
    ("form", "haystack", "expected"),
    [
        ("2.4kg", "the tent weighs 2.4 kg", "2.4 kg"),
        ("2.4kg", "the tent weighs 2.4kg", "2.4kg"),
        ("2.4 kg", "the tent weighs 2.4kg", "2.4kg"),
        ("第30条", "第 30 条による", "第 30 条"),
        ("第 30 条", "第30条による", "第30条"),
        ("$45,000", "cost $ 45,000 in total", "$ 45,000"),
        ("1,200万円", "費用は 1,200 万円 でした", "1,200 万円"),
    ],
)
def test_the_internal_spacing_of_a_particular_is_free(
    form: str, haystack: str, expected: str
) -> None:
    """``text.py`` deliberately does not collapse this difference: doing so for
    prose would make ``a b`` and ``ab`` one sentence. The tolerance belongs
    here, where it is about a particular rather than about text."""
    assert where(form, haystack) == [expected]


def test_free_spacing_does_not_make_two_different_numbers_one() -> None:
    assert where("2.4kg", "the tent weighs 2.5 kg") == []
    assert where("第30条", "第31条による") == []


def test_a_pattern_is_built_from_the_runs_of_a_particular() -> None:
    pattern = pattern_for("2.4kg")
    assert pattern is not None
    assert pattern.pattern == r"2\.4\s*kg"


def test_a_particular_with_nothing_in_it_has_no_pattern() -> None:
    """Not something that fails to resolve -- something that was never a
    particular. The caller has to tell those apart."""
    assert pattern_for("") is None
    assert pattern_for("   ") is None
    assert find_all("", search_form("anything")) == ()


# --- Several places ----------------------------------------------------------


def test_every_place_is_reported_and_not_the_first() -> None:
    """Ambiguity is information. A short particular genuinely occurs in several
    places, and picking one implies a precision that is not there."""
    assert len(where("30", "30 tents, 30 stoves, 30 packs")) == 3


def test_the_number_of_places_is_capped() -> None:
    """A particular that occurs everywhere carries no more information for
    being counted exactly."""
    assert hits("30", "30 " * 200) == 32


def test_a_match_at_the_very_start_and_end_is_found() -> None:
    assert where("30", "30") == ["30"]


# --- Offsets -----------------------------------------------------------------


def test_a_hit_reports_offsets_into_the_original_text() -> None:
    """Not into the reduced form. A reader opens the document, and the document
    is the original."""
    haystack = "The  tent   weighs ２.４kg."
    span = find_all("2.4kg", search_form(haystack))[0]
    assert span.slice(haystack) == "２.４kg"


def test_a_hit_across_a_collapsed_run_covers_the_whole_run() -> None:
    haystack = "第\n30\n条"
    span = find_all("第30条", search_form(haystack))[0]
    assert span.slice(haystack) == "第\n30\n条"


# --- Properties --------------------------------------------------------------

_PIECES = [*"0123456789", ".", ",", " ", "kg", "第", "条", "三", "千", "人", "は", "abc"]
TEXTS = st.lists(st.sampled_from(_PIECES), max_size=40).map("".join)


# --- the literal a haystack must contain to be worth searching ---------------
#
# `Evidence.locate` skips an item whose text does not hold this, which turns a
# regex walk and a tuple into one substring test. That is a speed change and it
# is allowed to be one only while the skip is *sound* -- so the property below
# is what makes it a speed change rather than an answer change.


def test_the_required_run_is_one_of_the_runs_the_pattern_is_built_from() -> None:
    """Both are `_RUNS.findall(form)`, and they have to stay that way. A
    prefilter reasoned about a pattern it no longer shares a derivation with is
    a filter that has quietly stopped being a check."""
    for form in ("2.45kg", "2.4kg", "第30条", "12 March 2026", "1,200 units"):
        pattern = pattern_for(form)
        assert pattern is not None
        runs = _RUNS.findall(form)
        probe = required_run(form)
        assert probe in runs, f"{probe!r} is not one of {form!r}'s runs {runs}"
        assert len(probe) == max(len(run) for run in runs), "a shorter run is less selective"
        assert re.escape(probe) in pattern.pattern

    assert required_run("") == ""
    assert required_run("   ") == ""


#: Forms and a text that really does contain each, so the property below is
#: about a hit rather than about the absence of one.
#:
#: Written out because the generated `TEXTS` almost never happen to contain a
#: form. A poison replacing the probe with a literal that need not be present
#: at all went straight through the first version of these: the assertion sat
#: under `if find_all(...)`, hypothesis produced hardly any text that hit, and
#: a test that reaches its assertion on almost no example is green about almost
#: nothing.
HITTING = [
    ("30", "there were 30 of them"),
    ("2.4", "the tent weighs 2.4 kilograms"),
    ("2.4kg", "the tent weighs 2.4 kg exactly"),
    ("第30条", "第30条による"),
    ("三千人", "三千人が参加した"),
    ("1,200", "the total was 1,200 units"),
    ("12 March 2026", "signed on 12 March 2026 by both"),
]


@pytest.mark.parametrize(("form", "haystack"), HITTING)
def test_the_required_run_is_present_wherever_a_hit_is(form: str, haystack: str) -> None:
    """The direction that makes skipping safe: a hit implies the run is there.

    Stated this way round on purpose. The other direction -- the run is there,
    so there is a hit -- is false and must stay false: `2.4` occurs in `12.40`
    and is not a match, which is the whole of `_bounded`.
    """
    # Folded first, which is what `Evidence.locate` passes: `particular.form`
    # is already reduced. Reading `required_run` off the unfolded text is how a
    # sound prefilter becomes unsound -- folding lowercases, so the probe for
    # `12 March 2026` would be `March`, which is in no reduced text anywhere.
    folded = search_form(form).text
    hay = search_form(haystack)
    assert find_all(folded, hay), "this pair does not hit, so it says nothing about skipping"
    assert required_run(folded) in hay.text, (
        f"{folded!r} was found in {haystack!r} whose reduced text does not contain "
        f"{required_run(folded)!r}; skipping on that test would drop a real hit"
    )


@given(form=st.sampled_from([form for form, _ in HITTING]), before=TEXTS, after=TEXTS)
def test_the_skip_and_the_search_agree_on_every_text(form: str, before: str, after: str) -> None:
    """What `Evidence.locate` actually does, as a property: filtering first and
    searching gives what searching alone gives.

    The form is *placed* in the text rather than hoped for. Padding on both
    sides is what makes it a real question -- the boundary rules decide whether
    the placed copy still counts, and either answer is fine here so long as the
    two ways of arriving at it agree.
    """
    folded = search_form(form).text
    hay = search_form(before + form + after)
    probe = required_run(folded)
    filtered = () if (probe and probe not in hay.text) else find_all(folded, hay)
    assert filtered == find_all(folded, hay)


@given(haystack=TEXTS)
def test_every_hit_is_inside_the_text_it_was_found_in(haystack: str) -> None:
    for span in find_all("30", search_form(haystack)):
        assert 0 <= span.start < span.end <= len(haystack)


@given(haystack=TEXTS, form=st.sampled_from(["30", "2.4", "2.4kg", "第30条", "三千人"]))
def test_hits_are_ordered_and_never_overlap(haystack: str, form: str) -> None:
    spans = find_all(form, search_form(haystack))
    for earlier, later in itertools.pairwise(spans):
        assert earlier.start <= later.start


@given(haystack=TEXTS, form=st.sampled_from(["30", "2.4", "2.4kg", "第30条"]))
def test_searching_twice_finds_the_same_places(haystack: str, form: str) -> None:
    hay = search_form(haystack)
    assert find_all(form, hay) == find_all(form, hay)


@given(haystack=TEXTS)
def test_a_hit_slices_back_to_something_that_reduces_to_the_particular(
    haystack: str,
) -> None:
    """The property that makes an offset worth reporting: what a reader opens
    at that offset is what akashi said was there. Reduced on both sides, since
    the tolerance is what made them equal in the first place."""
    for span in find_all("2.4kg", search_form(haystack)):
        recovered = search_form(span.slice(haystack)).text
        assert recovered.replace(" ", "") == "2.4kg"


@given(needle=st.sampled_from(["30", "2.4", "abc"]), padding=st.sampled_from(["", " ", "は", "、"]))
def test_a_particular_surrounded_by_nothing_that_continues_it_is_found(
    needle: str, padding: str
) -> None:
    haystack = f"{padding}{needle}{padding}"
    assume(search_form(haystack).text)
    assert find_all(needle, search_form(haystack))


@given(digits=st.text(alphabet="0123456789", min_size=1, max_size=3))
def test_a_number_is_never_found_inside_a_longer_run_of_digits(digits: str) -> None:
    assert find_all(digits, search_form(f"9{digits}9")) == ()


def test_an_empty_haystack_holds_nothing() -> None:
    assert find_all("30", search_form("")) == ()
    assert find_all("30", search_form("   ")) == ()


def test_a_span_of_a_hit_is_a_real_span() -> None:
    span = find_all("30", search_form("we counted 30 tents"))[0]
    assert isinstance(span, Span)
    assert len(span) == 2


# --- A comma binds digits only when it is a thousands separator --------------
#
# The boundary rule exists so `45` does not match inside `45,000`. It did that
# by treating every comma between digits as binding, which is right for a
# thousands separator and wrong for a list.
#
# NFKC turns the fullwidth `，` into `,`, so `见第3，5，7条` -- an ordinary
# Chinese enumeration -- became digit-comma-digit three times over, and every
# clause number in it failed to resolve into the document it came from. An
# honest answer quoting that list would have been reported as fabricated, in the
# language akashi claims to read.
#
# Found by `test_every_particular_of_the_sources_grounds_in_the_sources`, the
# property test asserting that anything extracted from the evidence resolves
# back into it, on `2026-08-30，2.4kg`. It is pinned there as an `@example`.


@pytest.mark.parametrize(
    ("needle", "haystack", "matches", "why"),
    [
        ("45", "Liability is capped at 45,000 dollars.", 0, "inside a thousands group"),
        ("000", "Liability is capped at 45,000 dollars.", 0, "the group itself"),
        ("45,000", "Liability is capped at 45,000 dollars.", 1, "the whole number"),
        ("234", "Revenue was 1,234,567 dollars.", 0, "a middle group"),
        ("2.4", "The tolerance is 12.45mm.", 0, "inside a decimal"),
        ("3", "见第3，5，7条。", 1, "an enumeration member"),
        ("5", "见第3，5，7条。", 1, "and the one after it"),
        ("7", "见第3，5，7条。", 1, "and the last"),
        ("12", "寸法は 12，34 です。", 1, "japanese, fullwidth comma"),
        ("30", "at 30,2 metres", 1, "two digits after the comma is not a group"),
        ("30", "at 30,20 metres", 1, "nor is four"),
        ("30", "at 30,200 metres", 0, "three digits is"),
        ("30", "at 30,2000 metres", 1, "four digits is not"),
    ],
)
def test_a_comma_binds_only_a_thousands_group(
    needle: str, haystack: str, matches: int, why: str
) -> None:
    assert len(find_all(needle, search_form(haystack))) == matches, why


def test_the_rule_is_symmetric() -> None:
    """A separator on the left has to be read the same way as one on the right,
    or `第3，5，7条` half works: `3` grounds and `5` does not."""
    enumeration = search_form("见第3，5，7条。")
    assert all(find_all(digit, enumeration) for digit in ("3", "5", "7"))

    grouped = search_form("45,000")
    assert not find_all("45", grouped)
    assert not find_all("000", grouped)
