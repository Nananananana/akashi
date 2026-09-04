"""The invariants the whole pipeline rests on, asserted end to end.

The per-module property tests check each stage against itself. These check the
stages against *each other*, which is where the interesting failures live: an
offset that is right inside a segment and wrong once lifted into the answer, a
count that is right per segment and wrong in the aggregate, a particular that
grounds in one evidence set and not in a superset of it.

Generation is CJK-heavy on purpose. Half of what akashi handles is text where a
character is not a byte, a sentence has no spaces, and a digit can be written
four ways -- and a generator of ASCII prose would exercise none of the code
that exists because of that.
"""

from __future__ import annotations

import itertools

from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

from akashi.domain.coverage import Assessment, assess
from akashi.domain.evidence import Evidence, EvidenceItem, item
from akashi.domain.extraction import extract_from_answer, extract_from_segment
from akashi.domain.segment import Segmentation, segment_answer
from akashi.domain.verdict import Standing, Verdict, check_segment
from akashi.infrastructure.languages import DEFAULT

# --- Generators --------------------------------------------------------------

#: Fragments rather than characters, so the generator produces the shapes a
#: model actually emits: a table row, a fence, a wrapped line, a figure with a
#: counter attached to it.
_FRAGMENTS = [
    "テントは",
    "重さは",
    "軽い",
    "前回より",
    "参加者は",
    "帐篷重",
    "比上次轻",
    "The tent weighs ",
    "and the stove ",
    "It was light",
    "2.4kg",
    "2.6kg",
    "300g",
    "２.４kg",
    "12人",
    "三千人",
    "第30条",
    "第13条",
    "2026年8月30日",
    "2026-08-30",
    "1,200万円",
    "45,000",
    "12.5%",
    "14:30",
    "。",
    "、",
    "，",
    ". ",
    ", ",
    " ",
    "\n",
    "\n\n",
    "「",
    "」",
    "- ",
    "# ",
    "| ",
    "> ",
    "```",
]

ANSWERS = st.lists(st.sampled_from(_FRAGMENTS), max_size=60).map("".join)

SOURCES = st.lists(st.sampled_from(_FRAGMENTS), max_size=40).map("".join)


def evidence_of(*texts: str) -> Evidence:
    """An evidence set from plain strings, ids assigned in order."""
    return Evidence.of(
        [
            item(f"itm_{index:02d}", text, document_id=f"doc_{index:02d}", start=index * 1000)
            for index, text in enumerate(texts, start=1)
            if text
        ]
    )


def run(answer: str, evidence: Evidence) -> tuple[Segmentation, Assessment]:
    segmentation = segment_answer(answer, DEFAULT)
    checked = [
        check_segment(segment, extract_from_segment(segment, DEFAULT), evidence)
        for segment in segmentation.segments
    ]
    return segmentation, assess(checked)


SLOW = settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])


# --- The two invariants everything else rests on -----------------------------


@given(answer=ANSWERS)
@SLOW
def test_the_segments_tile_the_answer_apart_from_whitespace(answer: str) -> None:
    """Nothing a model wrote is lost between segments, and nothing is counted
    twice. Every count on a report is over these."""
    segments = segment_answer(answer, DEFAULT).segments
    at = 0
    for segment in segments:
        assert not answer[at : segment.span.start].strip()
        at = segment.span.end
    assert not answer[at:].strip()

    for earlier, later in itertools.pairwise(segments):
        assert earlier.span.end <= later.span.start


@given(answer=ANSWERS)
@SLOW
def test_every_offset_slices_back_to_the_text_it_names(answer: str) -> None:
    """An offset that has drifted points a reader at the wrong sentence while
    still looking like a finding, which is the failure ADR-0004 refuses fuzzy
    matching to avoid."""
    segmentation = segment_answer(answer, DEFAULT)
    for segment in segmentation.segments:
        assert answer[segment.span.start : segment.span.end] == segment.text
    for particular in extract_from_answer(segmentation, DEFAULT):
        assert answer[particular.span.start : particular.span.end] == particular.text


# --- The stages against each other -------------------------------------------


@given(answer=ANSWERS)
@SLOW
def test_every_particular_sits_inside_the_segment_that_claims_it(answer: str) -> None:
    segmentation = segment_answer(answer, DEFAULT)
    by_id = {segment.segment_id: segment for segment in segmentation.segments}
    for particular in extract_from_answer(segmentation, DEFAULT):
        assert by_id[particular.segment_id].span.contains(particular.span)


@given(answer=ANSWERS, sources=st.lists(SOURCES, max_size=3))
@SLOW
def test_the_assessment_covers_every_segment_exactly_once(answer: str, sources: list[str]) -> None:
    segmentation, assessment = run(answer, evidence_of(*sources))
    assert [checked.segment for checked in assessment.segments] == list(segmentation.segments)


@given(answer=ANSWERS, sources=st.lists(SOURCES, max_size=3))
@SLOW
def test_the_coverage_adds_up(answer: str, sources: list[str]) -> None:
    """A denominator that did not is a denominator a reader would be misled by,
    and it is checked here as well as on construction because the counts and
    the segments are computed in two places."""
    _, assessment = run(answer, evidence_of(*sources))
    coverage = assessment.coverage
    assert coverage.segments == len(assessment.segments)
    assert coverage.bearing + coverage.unbearing + coverage.unexamined == coverage.segments
    counts = assessment.particular_counts()
    assert counts[Standing.GROUNDED.value] + counts[Standing.FLOATING.value] == coverage.checked


@given(answer=ANSWERS, sources=st.lists(SOURCES, max_size=3))
@SLOW
def test_every_skipped_span_belongs_to_a_segment_that_was_not_checked(
    answer: str, sources: list[str]
) -> None:
    """ADR-0005: every discarding path carries its reason to the end. A skip
    that named no segment would be a gap nobody could follow up."""
    _, assessment = run(answer, evidence_of(*sources))
    spans = {checked.span for checked in assessment.segments}
    for skip in assessment.skipped:
        assert skip.span in spans
        assert skip.reason


@given(answer=ANSWERS, sources=st.lists(SOURCES, max_size=3))
@SLOW
def test_every_reported_location_lands_inside_the_item_that_reported_it(
    answer: str, sources: list[str]
) -> None:
    """A location that escaped its item would point a reader at text that was
    never sent."""
    evidence = evidence_of(*sources)
    by_id: dict[str, EvidenceItem] = {entry.item_id: entry for entry in evidence.items}
    _, assessment = run(answer, evidence)
    for checked in assessment.segments:
        for particular in checked.particulars:
            for location in particular.locations:
                owner = by_id[location.item_id]
                assert owner.anchor.span.contains(location.anchor.span)


# --- Grounding behaves like grounding ----------------------------------------


@given(answer=ANSWERS, sources=st.lists(SOURCES, min_size=1, max_size=2))
@SLOW
def test_adding_evidence_never_makes_a_grounded_particular_float(
    answer: str, sources: list[str]
) -> None:
    """Monotonicity. Grounding is "this string is somewhere in what was sent",
    so sending more can only add places -- and a resolution rule that broke
    this would be one where two items interfered with each other."""
    fewer = evidence_of(sources[0])
    more = evidence_of(*sources)

    _, before = run(answer, fewer)
    _, after = run(answer, more)

    grounded_before = {
        particular.particular.span for checked in before.segments for particular in checked.grounded
    }
    grounded_after = {
        particular.particular.span for checked in after.segments for particular in checked.grounded
    }
    assert grounded_before <= grounded_after


@given(answer=ANSWERS)
@SLOW
def test_nothing_grounds_against_an_empty_package(answer: str) -> None:
    """ADR-0006's floor. With nothing sent there is nothing to be grounded in,
    and every particular floats -- correctly, and uselessly, which is why the
    caller says so in words rather than printing the share."""
    _, assessment = run(answer, Evidence())
    for checked in assessment.segments:
        assert checked.verdict is not Verdict.GROUNDED
        assert all(one.standing is Standing.FLOATING for one in checked.particulars)
    assert assessment.grounded_share in (None, 0.0)


@given(source=SOURCES)
# Pinned the moment it was drawn, before anything was looked at. `@example` is a
# decorator and does not change what `function_digest` reads, so adding one
# keeps the accumulated database -- while the first instinctive edit to print
# the input would have orphaned it silently.
@example(source="2026-08-30，2.4kg")
# Two more, captured as strings before anything was edited and pinned with the
# fixes. Both are the same shape as the first and neither was reachable from it:
# a comma between digits that reads as a thousands separator and is not.
#
#   `2026-08-30，300g`   the `30` before the comma is a *day*, so `30,300` is not
#                        a number. `_is_number_tail` reads what is in front of
#                        the run before deciding it is one.
#   `45,000，300g`       the number's own separator is half-width and the pause is
#                        full-width; NFKC folded both to `,` and with it the
#                        distinction the author made. `_same_width` keeps it.
@example(source="2026-08-30，300g")
@example(source="45,000，300g")
@SLOW
def test_every_particular_of_the_sources_grounds_in_the_sources(source: str) -> None:
    """The round trip. Everything akashi can extract from the text that was
    sent must resolve back into it -- a failure here would be normalization,
    extraction and the boundary rule disagreeing with each other rather than
    with a model."""
    evidence = evidence_of(source)
    assume(not evidence.is_empty)
    _, assessment = run(source, evidence)
    for checked in assessment.segments:
        for particular in checked.particulars:
            assert particular.standing is Standing.GROUNDED, (
                f"{particular.particular.describe()} was extracted from the evidence "
                f"and did not resolve back into it"
            )


# --- Reproducibility ---------------------------------------------------------


@given(answer=ANSWERS, sources=st.lists(SOURCES, max_size=3))
@SLOW
def test_the_whole_pipeline_run_twice_gives_the_same_assessment(
    answer: str, sources: list[str]
) -> None:
    """ADR-0003, at the level a report inherits it from. Same inputs, same
    verdicts, same order, same counts."""
    evidence = evidence_of(*sources)
    assert run(answer, evidence)[1] == run(answer, evidence)[1]


@given(answer=ANSWERS, sources=st.lists(SOURCES, min_size=2, max_size=3))
@SLOW
def test_the_order_of_the_evidence_changes_where_things_are_found_and_not_whether(
    answer: str, sources: list[str]
) -> None:
    """Two items in a different order are the same closed world. The locations
    are reported per item and so may be ordered differently; what must not
    change is which particulars grounded."""
    forwards = evidence_of(*sources)
    backwards = evidence_of(*reversed(sources))

    def standings(evidence: Evidence) -> list[tuple[int, str]]:
        _, assessment = run(answer, evidence)
        return [
            (one.particular.span.start, one.standing.value)
            for checked in assessment.segments
            for one in checked.particulars
        ]

    assert standings(forwards) == standings(backwards)


# --- the companion: what the strategy has to produce for any of this to mean ---
#
# Every property in this file is an implication over the particulars a generated
# answer bears, and every one of them is **vacuously true of an answer bearing
# none**. Measured: with `extract_from_segment` returning `()`, all twelve pass.
#
# The fix is not to assert the population inside a property. A property must
# hold on inputs that legitimately produce nothing, and a check inside it would
# fail on exactly the inputs it is satisfied by. So the strategy's own promise
# is checked once, separately, on fixed input -- and when `_FRAGMENTS` stops
# carrying anything akashi extracts, this one test says so instead of twelve
# properties going quiet.
#
# The distinction is `mamori`'s: whether being empty is a fact about *that
# input* or a fact about *this run*.


def test_the_fragments_produce_what_the_properties_are_about() -> None:
    """Not a property. A fixed answer, built from the fragments the strategies
    sample, that must bear particulars, ground some of them, and float others.

    Each of the three is a different half of this file going quiet:

    * no particulars — every offset and containment invariant is vacuous
    * nothing grounded — the location invariants have nothing to locate
    * nothing floating — the standing invariants only ever see one value
    """
    answer = "テントは2.4kg、参加者は12人。The tent weighs 2.6kg"
    evidence = evidence_of("テントは2.4kg、参加者は12人。", "The tent weighs 2.4kg")

    segmentation, assessment = run(answer, evidence)
    assert len(segmentation.segments) >= 2, "the segmenter stopped splitting these fragments"

    particulars = [one for segment in assessment.segments for one in segment.particulars]
    assert len(particulars) >= 3, (
        f"the fragments bear {len(particulars)} particulars; every invariant here is "
        f"an implication over them and is vacuously true when there are none"
    )

    grounded = [one for one in particulars if one.locations]
    floating = [one for one in particulars if not one.locations]
    assert grounded, "nothing resolved, so the location invariants have nothing to locate"
    assert floating, "nothing floated, so the standing invariants only ever see one value"


def test_every_fragment_that_should_bear_something_does() -> None:
    """The fragments are a list somebody edits, and a fragment that stopped
    being extractable would narrow what the properties explore without changing
    a single test name.

    Only the ones that carry a figure, a count or a date are named here. The
    prose fragments are there to be prose and bear nothing on purpose.
    """
    from akashi.domain.extraction import extract_from_answer
    from akashi.domain.segment import segment_answer

    bearing = ["2.4kg", "2.6kg", "300g", "２.４kg", "12人", "三千人"]
    for fragment in bearing:
        assert fragment in _FRAGMENTS, f"{fragment!r} left the strategy; update this list"
        found = extract_from_answer(segment_answer(fragment, DEFAULT), DEFAULT)
        assert found, f"{fragment!r} is in the strategy and akashi extracts nothing from it"


def test_the_properties_explore_the_list_the_companion_checks() -> None:
    """The tie between the two companions above and the twelve properties below.

    Poisoned to find this: point `ANSWERS` and `SOURCES` at prose that bears
    nothing, and **all fourteen pass** -- the properties go vacuous again and
    both companions stay green, because they check `_FRAGMENTS` and a fixed
    answer and the strategies no longer use either.

    So a companion that guards twelve tests needs guarding itself, which is
    `mamori`'s point: the wider a check's cover, the worse it is when the check
    is the thing that breaks. This is the narrowest thing that closes it -- the
    strategies must draw from the list the companions vouch for, asserted on the
    source rather than on a run, because a strategy pointed elsewhere is a
    *change*, not a random outcome.
    """
    import ast
    import pathlib

    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    drawn: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not ({"ANSWERS", "SOURCES"} & set(names)):
            continue
        pools = {
            argument.id
            for call in ast.walk(node.value)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "sampled_from"
            for argument in call.args
            if isinstance(argument, ast.Name)
        }
        for name in names:
            drawn[name] = pools

    assert set(drawn) == {"ANSWERS", "SOURCES"}, (
        f"expected both strategies to be assigned here; found {sorted(drawn)}"
    )
    for name, pools in drawn.items():
        assert pools == {"_FRAGMENTS"}, (
            f"{name} draws from {sorted(pools) or 'something this cannot read'}, and the "
            f"companions above vouch for _FRAGMENTS. A strategy pointed at another list "
            f"leaves twelve properties exploring text nobody checked for particulars."
        )
