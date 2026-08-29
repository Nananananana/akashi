"""Six outcomes, and the three that all mean "nothing wrong" for different reasons.

ADR-0005 is the reason this file is mostly about the distinctions rather than
about the happy path. A check that treats "I looked and found nothing wrong"
the same as "I did not look" lies by omission, and the whole product is the
claim that akashi does not.
"""

from __future__ import annotations

import pytest

from akashi.domain.anchor import Layer
from akashi.domain.coverage import (
    STANDING_LIMITS,
    Assessment,
    Coverage,
    Skipped,
    SkipRule,
    assess,
)
from akashi.domain.evidence import Evidence, item
from akashi.domain.extraction import extract_from_segment, kinds_not_extracted
from akashi.domain.particular import ParticularKind
from akashi.domain.segment import Segmentation, segment_answer
from akashi.domain.span import Span
from akashi.domain.verdict import (
    CheckedParticular,
    CheckedSegment,
    Standing,
    Verdict,
    check_segment,
)
from akashi.infrastructure.languages import DEFAULT

SOURCES = Evidence.of(
    [
        item(
            "itm_01",
            "The tent weighs 2.4kg and the stove 300g.",
            document_id="doc_4b1e",
            source_path="notes/gear.md",
            start=1200,
        )
    ]
)


def look(answer: str, evidence: Evidence = SOURCES) -> Assessment:
    """Segment, extract and check, the way the use case will."""
    segmentation: Segmentation = segment_answer(answer, DEFAULT)
    checked = [
        check_segment(segment, extract_from_segment(segment, DEFAULT), evidence)
        for segment in segmentation.segments
    ]
    return assess(checked, kinds_not_extracted(DEFAULT))


def verdicts(answer: str, evidence: Evidence = SOURCES) -> list[str]:
    return [segment.verdict.value for segment in look(answer, evidence).segments]


# --- The six outcomes --------------------------------------------------------


def test_every_particular_in_the_sources_is_grounded() -> None:
    assert verdicts("The tent weighs 2.4kg.") == ["grounded"]


def test_a_particular_that_is_not_in_the_sources_floats() -> None:
    assert verdicts("The tent weighs 2.6kg.") == ["floating"]


def test_one_floating_particular_makes_the_segment_float() -> None:
    """A segment is a verdict, and a verdict is about the whole of it."""
    assert verdicts("It weighs 2.4kg, not 2.6kg.") == ["floating"]


def test_a_segment_with_nothing_to_check_is_unbearing_and_not_a_pass() -> None:
    assert verdicts("The tent was light and easy to carry.") == ["unbearing"]


def test_code_is_not_examined_and_says_so() -> None:
    answer = "Here:\n\n```python\nweight = 2.6\n```"
    assessment = look(answer)
    assert [segment.verdict.value for segment in assessment.segments] == [
        "unbearing",
        "unchecked",
    ]
    unchecked = assessment.segments[1]
    assert "line number" in unchecked.because


def test_contradicted_is_defined_and_produced_by_nothing_yet() -> None:
    """v0.4, after the corpus exists to price its false positives. Defined now
    so the vocabulary is stable while the detector is not, and asserted so that
    it cannot ship by accident."""
    assert Verdict.CONTRADICTED.value == "contradicted"
    assert "contradicted" not in verdicts("The tent weighs 2.6kg, not 2.4kg.")


def test_the_verdict_vocabulary_is_closed() -> None:
    assert {verdict.value for verdict in Verdict} == {
        "grounded",
        "floating",
        "contradicted",
        "unbearing",
        "unchecked",
        "unverifiable",
    }


# --- Particulars -------------------------------------------------------------


def test_a_grounded_particular_carries_where_it_was_found() -> None:
    checked = look("The tent weighs 2.4kg.").segments[0].particulars[0]
    assert checked.standing is Standing.GROUNDED
    assert checked.locations[0].anchor.span == Span(1216, 1221)
    assert "notes/gear.md" in checked.describe()


def test_a_floating_particular_is_found_nowhere_rather_than_nearly() -> None:
    checked = look("The tent weighs 2.6kg.").segments[0].particulars[0]
    assert checked.standing is Standing.FLOATING
    assert checked.locations == ()
    assert checked.describe().endswith("floating (nowhere)")


def test_a_particular_found_twice_is_ambiguous_and_that_is_information() -> None:
    twice = Evidence.of(
        [item("itm_01", "2.4kg here."), item("itm_02", "2.4kg there.", document_id="doc_2")]
    )
    checked = look("The tent weighs 2.4kg.", twice).segments[0].particulars[0]
    assert checked.is_ambiguous
    assert checked.standing is Standing.GROUNDED


def test_grounded_only_in_an_interpretation_says_so() -> None:
    guessed = Evidence.of([item("itm_01", "Probably 2.4kg.", layer=Layer.INTERPRETATION)])
    checked = look("The tent weighs 2.4kg.", guessed).segments[0].particulars[0]
    assert checked.in_an_interpretation


def test_grounded_in_a_fact_and_an_interpretation_is_grounded_in_the_fact() -> None:
    """``all`` rather than ``any``. A particular in one fact and one
    interpretation is grounded in a fact, and saying otherwise would understate
    the evidence."""
    both = Evidence.of(
        [
            item("itm_01", "Probably 2.4kg.", layer=Layer.INTERPRETATION),
            item("itm_02", "Measured 2.4kg.", document_id="doc_2", layer=Layer.FACT),
        ]
    )
    checked = look("The tent weighs 2.4kg.", both).segments[0].particulars[0]
    assert not checked.in_an_interpretation


def test_a_floating_particular_is_not_in_an_interpretation_either() -> None:
    checked = look("The tent weighs 2.6kg.").segments[0].particulars[0]
    assert not checked.in_an_interpretation


# --- A segment that was not examined -----------------------------------------


def test_an_unexamined_segment_must_say_why() -> None:
    segment = segment_answer("```\nx = 1\n```", DEFAULT).segments[0]
    with pytest.raises(ValueError, match="does not say why"):
        CheckedSegment(segment=segment, verdict=Verdict.UNCHECKED)


def test_an_examined_segment_may_not_carry_an_excuse() -> None:
    segment = segment_answer("The tent is light.", DEFAULT).segments[0]
    with pytest.raises(ValueError, match="reads as an excuse"):
        CheckedSegment(segment=segment, verdict=Verdict.GROUNDED, because="it looked fine")


def test_an_unexamined_segment_may_not_carry_particulars() -> None:
    segment = segment_answer("The tent weighs 2.4kg.", DEFAULT).segments[0]
    found = extract_from_segment(segment, DEFAULT)
    with pytest.raises(ValueError, match="carries particulars"):
        CheckedSegment(
            segment=segment,
            particulars=(CheckedParticular(particular=found[0]),),
            verdict=Verdict.UNCHECKED,
            because="because",
        )


# --- The account -------------------------------------------------------------


def test_every_skipped_span_names_the_rule_that_skipped_it() -> None:
    assessment = look("The tent was light.\n\n```\nx = 2.6\n```")
    assert [(skip.rule.value, skip.segment_id) for skip in assessment.skipped] == [
        ("no_particulars", "seg_001"),
        ("not_prose", "seg_002"),
    ]


def test_a_skip_with_no_reason_is_refused() -> None:
    with pytest.raises(ValueError, match="silent gap"):
        Skipped(span=Span(0, 5), rule=SkipRule.NO_PARTICULARS, reason="")


def test_the_account_is_derived_from_the_verdicts_rather_than_passed_in() -> None:
    """The only way to guarantee that a segment akashi did not examine cannot
    fail to appear in the account."""
    assessment = look("The tent was light. It weighs 2.4kg.")
    unbearing = [s for s in assessment.segments if s.verdict is Verdict.UNBEARING]
    assert len(assessment.skipped) == len(unbearing) == 1


def test_the_skips_are_in_a_fixed_order() -> None:
    answer = "```\nx=1\n```\n\nIt was light.\n\nIt weighs 2.4kg."
    first = look(answer).skipped
    assert first == look(answer).skipped
    assert [skip.span.start for skip in first] == sorted(skip.span.start for skip in first)


def test_nothing_is_skipped_when_everything_bears_something() -> None:
    assert look("The tent weighs 2.4kg. The stove is 300g.").skipped == ()


# --- Coverage ----------------------------------------------------------------


def test_the_denominators_are_published() -> None:
    assessment = look("The tent was light. It weighs 2.4kg and 2.6kg.")
    assert assessment.coverage.segments == 2
    assert assessment.coverage.bearing == 1
    assert assessment.coverage.unbearing == 1
    assert assessment.coverage.unexamined == 0
    assert assessment.coverage.particulars == 2
    assert assessment.coverage.checked == 2


def test_every_segment_is_in_exactly_one_bucket() -> None:
    with pytest.raises(ValueError, match="Every segment is in exactly one"):
        Coverage(segments=5, bearing=1, unbearing=1, unexamined=1)


def test_more_particulars_cannot_be_checked_than_were_extracted() -> None:
    with pytest.raises(ValueError, match="checked out of"):
        Coverage(particulars=2, checked=3)


def test_the_kinds_no_rule_covers_are_on_the_coverage() -> None:
    assessment = look("The tent weighs 2.4kg.")
    assert assessment.coverage.kinds_not_extracted == (ParticularKind.PROPER_NOUN.value,)


def test_the_counts_include_the_verdicts_that_are_zero() -> None:
    """``contradicted`` at zero is a different statement from ``contradicted``
    being absent from the summary."""
    counts = look("The tent weighs 2.4kg.").counts()
    assert counts["contradicted"] == 0
    assert set(counts) == {verdict.value for verdict in Verdict}


def test_the_coverage_describes_itself_for_a_reader() -> None:
    assessment = look("The tent was light. It weighs 2.4kg.")
    assert assessment.coverage.describe() == (
        "2 segments: 1 bearing, 1 unbearing, 0 unexamined; 1 of 1 particulars checked"
    )


# --- The share ---------------------------------------------------------------


def test_the_grounded_share_is_over_what_was_checked() -> None:
    assessment = look("It weighs 2.4kg, not 2.6kg.")
    assert assessment.grounded_share == 0.5


def test_an_answer_with_nothing_checkable_has_no_share_rather_than_a_perfect_one() -> None:
    """``None`` rather than ``1.0``. An answer with nothing to check has not
    scored perfectly, and a number would be read as though it had."""
    assert look("The tent was light and easy to carry.").grounded_share is None


def test_an_empty_answer_has_no_share() -> None:
    assert look("").grounded_share is None


# --- The limits --------------------------------------------------------------


def test_the_limits_travel_with_the_assessment() -> None:
    """On the artefact rather than in the documentation. The artefact travels;
    the documentation does not."""
    assessment = look("The tent weighs 2.4kg.")
    assert assessment.limits == STANDING_LIMITS
    assert len(assessment.limits) == 4


def test_the_limits_name_the_two_declared_misses_and_the_two_false_positives() -> None:
    joined = " ".join(STANDING_LIMITS).lower()
    assert "assembled from two documents" in joined
    assert "reversed" in joined
    assert "arithmetic" in joined
    assert "not about truth" in joined


@pytest.mark.parametrize(
    "word", ["verified fact", "factually correct", "proven true", "is true", "is false"]
)
def test_the_forbidden_vocabulary_appears_in_no_wording_akashi_ships(word: str) -> None:
    """ADR-0004 made unavoidable rather than a style rule. akashi establishes
    that a string is where the answer implies it is, and nothing stronger."""
    shipped = " ".join(
        [
            *STANDING_LIMITS,
            *(verdict.value for verdict in Verdict),
            *(standing.value for standing in Standing),
            *(rule.value for rule in SkipRule),
        ]
    ).lower()
    assert word not in shipped


# --- Determinism -------------------------------------------------------------


def test_assessing_the_same_answer_twice_gives_the_same_assessment() -> None:
    """ADR-0003, at the level everything above this inherits it from."""
    answer = "The tent weighs 2.4kg. It was light. ```\nx=1\n```"
    assert look(answer) == look(answer)
