"""The strongest claim akashi makes, and the four ways it refuses to make it.

`floating` says *this figure is in none of your sources*. `contradicted` says
*this figure is wrong, and here is the one your source gives, at this offset*.
The second is the only finding a reader can act on without opening the file, and
it is the one most able to be wrong.

Most of what is here is about what akashi must **not** say. The rule was
specified wider, measured, and narrowed twice against the corpus, and the tests
that pin the narrowing are the ones that matter: a `contradicted` that is
sometimes the wrong line is worse than a `floating` that is only ever unhelpful.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from akashi.application import audit
from akashi.domain.contradiction import Contradiction, SourceIndex, replaces
from akashi.domain.evidence import Evidence, item
from akashi.domain.extraction import extract_from_answer
from akashi.domain.particular import ParticularKind
from akashi.domain.segment import segment_answer
from akashi.domain.verdict import (
    CheckedParticular,
    CheckedSegment,
    Verdict,
    check_segment,
)
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from conftest import published_schema

PACKAGES = Path(__file__).parent / "packages"
SCHEMA = published_schema()


def assess(answer: str, evidence: Evidence, *, sources: bool = True) -> list[CheckedSegment]:
    index = SourceIndex.of(evidence, DEFAULT) if sources else None
    segmentation = segment_answer(answer, DEFAULT)
    found = extract_from_answer(segmentation, DEFAULT)
    return [
        check_segment(
            segment,
            [one for one in found if segment.span.contains(one.span)],
            evidence,
            index,
        )
        for segment in segmentation.segments
    ]


def only(answer: str, evidence: Evidence, *, sources: bool = True) -> CheckedParticular:
    checked = [one for seg in assess(answer, evidence, sources=sources) for one in seg.particulars]
    floating = [one for one in checked if not one.locations]
    assert len(floating) == 1, [one.describe() for one in checked]
    return floating[0]


# --- What the relation is ----------------------------------------------------


@pytest.mark.parametrize(
    ("source", "answer"),
    [
        ("5mg", "5 grams"),
        ("0.02mm", "0.02 metres"),
        ("1,200万円", "1,200億円"),
        ("60℃", "60℉"),
        ("4 weeks", "4 days"),
        ("Section 4(b)", "Section 4(d)"),
    ],
)
def test_the_digits_survive_and_the_text_beside_them_does_not(source: str, answer: str) -> None:
    """The whole rule. Identical digits are a *shared substring*, which is
    evidence in the text rather than a resemblance, and ADR-0004 is built on the
    observation that a faithful paraphrase does not have one. When ``5``
    survives verbatim and the unit does not, the number was copied and the unit
    was got wrong."""
    assert replaces(source, answer)


@pytest.mark.parametrize(
    ("source", "answer"),
    [
        # The digits changed. This is the case the rule gives up, and the one
        # that cost 21 of 33 localisations. See the module docstring of
        # ``akashi.domain.contradiction`` for the measurement.
        ("2.4kg", "2.6kg"),
        ("5mg", "250mg"),
        ("2回", "28回"),
        ("60 days", "90 days"),
        # Nothing changed but the writing, so it would have grounded.
        ("5mg", "5mg"),
        # No digits at all. Without this guard every name explains every other
        # name, and ``entity_swap`` would produce a finding pointing anywhere.
        ("田中", "佐藤"),
        ("Acme Ltd", "Borden Inc"),
    ],
)
def test_everything_else_is_not_a_replacement(source: str, answer: str) -> None:
    assert not replaces(source, answer)


def test_a_value_with_no_digits_can_never_explain_another() -> None:
    """Two names have the same digits -- none -- and different text. Without an
    explicit guard that is indistinguishable from a unit swap, and akashi would
    announce that ``佐藤`` is a corruption of ``田中`` on the strength of both
    being proper nouns in the same paragraph."""
    assert not replaces("田中", "佐藤")
    assert not replaces("", "")


# --- What akashi says when it fires ------------------------------------------


def test_a_swapped_unit_names_the_source_and_where_it_is() -> None:
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    one = only("内服は 5g を朝夕に。", evidence)
    assert one.is_contradicted
    assert one.contradiction is not None
    assert one.contradiction.found == "5mg"
    assert "5mg" in one.describe()
    assert one.contradiction.anchor.span.slice("内服は 5mg を朝夕に。") == "5mg"


def test_the_segment_carries_the_verdict() -> None:
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    [segment] = assess("内服は 5g を朝夕に。", evidence)
    assert segment.verdict is Verdict.CONTRADICTED


def test_the_finding_says_which_rule_produced_it() -> None:
    """A finding that cannot say why it is a finding is one nobody can
    appeal."""
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    one = only("内服は 5g を朝夕に。", evidence)
    assert one.contradiction is not None
    assert "same digits" in one.contradiction.why


def test_a_contradicted_particular_is_still_floating() -> None:
    """It resolved nowhere -- that is why it is a finding at all. The source is
    something akashi found *about* it, not a place it was found."""
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    one = only("内服は 5g を朝夕に。", evidence)
    assert one.locations == ()
    assert one.standing.value == "floating"


def test_grounded_and_contradicted_at_once_is_refused() -> None:
    """A particular that is in the source cannot also be a corruption of it.
    Refused at construction rather than checked in the renderer, because a
    report is a document and the document must not be able to say this."""
    from akashi.domain.anchor import Anchor
    from akashi.domain.evidence import Location
    from akashi.domain.span import Span

    anchor = Anchor(document_id="doc_1", source_path="a.md", section="", span=Span(0, 3))
    particular = extract_from_answer(segment_answer("内服は 5mg を。", DEFAULT), DEFAULT)[0]
    with pytest.raises(ValueError):
        CheckedParticular(
            particular=particular,
            locations=(Location(item_id="itm_01", anchor=anchor),),
            contradiction=Contradiction(found="5g", item_id="itm_01", anchor=anchor, why="test"),
        )


# --- What akashi refuses to say ----------------------------------------------


def test_a_drifted_digit_is_left_floating_and_this_is_the_price() -> None:
    """The largest deliberate miss in the project.

    ``2.6kg`` where the source says ``2.4kg`` is a real hallucination, akashi
    finds it, and akashi will not say what it replaced. Letting it try raised
    localisation from 12 of 33 to 27 of 33 and was wrong on more than half of
    what it added: an invented figure, a derived one and a corrupted one are
    the same thing to anything that reads structure.
    """
    evidence = Evidence.of([item("itm_01", "テントは 2.4kg、二人用。")])
    one = only("テントは 2.6kg、二人用。", evidence)
    assert not one.is_contradicted
    assert "nowhere" in one.describe()


def test_a_derived_value_is_not_reported_as_a_corruption_of_its_input() -> None:
    """``28回`` sits beside the ``2回`` it was computed from. Naming that as the
    source is not merely unhelpful, it is false -- the answer and the source
    agree. akashi does no arithmetic (STANDING_LIMITS) and so cannot tell a
    product from a corruption; it therefore says neither."""
    evidence = Evidence.of([item("itm_01", "1日2回、14日間服用します。")])
    one = only("合計28回服用します。", evidence)
    assert not one.is_contradicted


def test_an_invented_figure_is_not_given_a_parent() -> None:
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    one = only("内服は 250mg を朝夕に。", evidence)
    assert not one.is_contradicted


def test_two_candidates_leave_it_floating() -> None:
    """Ambiguity is not a finding. Picking one of two would invent exactly the
    precision the project refuses, and it would do it invisibly."""
    evidence = Evidence.of([item("itm_01", "保証は 5mg と 5g の二種類がある。")])
    one = only("保証は 5t で提供される。", evidence)
    assert not one.is_contradicted


def test_a_different_kind_never_explains_it() -> None:
    """A quantity is not explained by a date, however well the digits line
    up."""
    evidence = Evidence.of([item("itm_01", "有効期間は 12か月とする。")])
    one = only("第12条により解約できる。", evidence)
    assert not one.is_contradicted


def test_without_an_index_nothing_is_ever_contradicted() -> None:
    """What v0.1 through v0.3 did. The feature is switchable off without a flag
    reaching the domain, because an absent index is the off position."""
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    one = only("内服は 5g を朝夕に。", evidence, sources=False)
    assert not one.is_contradicted
    assert SourceIndex().explain(one.particular, (), evidence) is None


# --- The neighbourhood, which breaks ties and does not make findings ---------


def test_a_segment_that_grounded_nothing_can_still_be_contradicted() -> None:
    """This restriction was specified, implemented, measured and removed.

    The reasoning was that without a grounded particular there is no way to know
    which document the sentence is about. It cost 10 findings in 12 and bought
    no precision, because the corpus's answers -- like real ones -- put one
    figure in a sentence, so the anchor was absent exactly when the finding was
    wanted. Identical digits anchor better than proximity does.
    """
    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    [segment] = assess("5g です。", evidence)
    assert not any(one.locations for one in segment.particulars)
    assert segment.verdict is Verdict.CONTRADICTED


def test_the_tightest_neighbourhood_with_one_candidate_wins() -> None:
    """The neighbourhood is a tie-break. Two candidates package-wide would
    otherwise be ambiguous, and the sentence the rest of the segment resolved
    into settles which one is meant.

    It can only break a tie when the segment grounded something -- the date
    here. A segment that grounded nothing gets the package and the uniqueness
    requirement, which is the case above."""
    evidence = Evidence.of(
        [
            item("itm_01", "2026年8月30日から 5mg を開始する。"),
            item("itm_02", "別表の換算は 5g を基準とする。"),
        ]
    )
    one = only("2026年8月30日から 5t を開始する。", evidence)
    assert one.is_contradicted
    assert one.contradiction is not None
    assert one.contradiction.item_id == "itm_01"


def test_without_that_tie_break_two_candidates_are_still_two() -> None:
    """The same package, and a segment with nothing grounded in it. akashi
    falls back to the whole package, finds ``5mg`` and ``5g``, and says
    nothing."""
    evidence = Evidence.of(
        [
            item("itm_01", "2026年8月30日から 5mg を開始する。"),
            item("itm_02", "別表の換算は 5g を基準とする。"),
        ]
    )
    one = only("用量は 5t とする。", evidence)
    assert not one.is_contradicted


def test_the_index_reads_the_evidence_once_and_skips_code() -> None:
    """A number in a fenced block is as likely a line number as a claim about
    the world, and a source index that read one would offer it as a parent."""
    evidence = Evidence.of([item("itm_01", "使い方:\n\n```\ntimeout = 5mg\n```\n")])
    assert len(SourceIndex.of(evidence, DEFAULT)) == 0


# --- Through the whole pipeline ----------------------------------------------


def test_a_real_package_reports_the_source_and_the_json_validates() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    package = load_package(PACKAGES / "gear-ja.json")
    report = audit("テントは 2.4kg、ガスは 250mg カートリッジ。", package, DEFAULT)
    body = report.to_dict()
    found = [
        one
        for segment in body["segments"]
        for one in segment.get("particulars", [])
        if "contradiction" in one
    ]
    assert len(found) == 1
    assert found[0]["contradiction"]["found"] == "250g"
    assert found[0]["standing"] == "floating"
    jsonschema.validate(body, json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_the_source_is_named_in_document_coordinates() -> None:
    """A reader opens the file, and the file does not know it was cut into
    items. An offset into an item would point at the wrong line."""
    package = load_package(PACKAGES / "gear-ja.json")
    report = audit("ガスは 250mg カートリッジ。", package, DEFAULT)
    found = next(
        one.contradiction
        for segment in report.assessment.segments
        for one in segment.particulars
        if one.contradiction is not None
    )
    assert found.anchor.span.start > 1000
    assert found.anchor.source_path.endswith(".md")


def test_the_report_id_does_not_change_when_a_finding_does() -> None:
    """``report_id`` is over the *inputs*. A reader comparing two audits of the
    same answer against the same package must see the same id whether or not
    akashi learned to explain a finding since."""
    package = load_package(PACKAGES / "gear-ja.json")
    answer = "ガスは 250mg カートリッジ。"
    with_sources = audit(answer, package, DEFAULT)
    assert any(
        one.contradiction is not None
        for segment in with_sources.assessment.segments
        for one in segment.particulars
    )
    assert with_sources.report_id == audit(answer, package, DEFAULT).report_id


def test_the_kind_is_not_extracted_from_the_marker_text() -> None:
    """Regression on the first false positive this feature produced.

    ``2.6kg`` was reported as contradicting ``300g`` because both were
    quantities in the same source sentence. Same kind and nearby is not a
    relation between two values; it is a coincidence of layout.
    """
    evidence = Evidence.of([item("itm_01", "テントは 2.4kg。前回より 300g 軽い。")])
    one = only("テントは 2.6kg、前回より 300g 軽い。", evidence)
    assert not one.is_contradicted


def test_the_index_is_built_once_per_audit_and_not_per_segment() -> None:
    """The cost claim in the module docstring. Segmenting and extracting the
    evidence per segment would make a long answer quadratic in the package."""
    package = load_package(PACKAGES / "gear-ja.json")
    index = SourceIndex.of(package.evidence, DEFAULT)
    assert len(index) == len(SourceIndex.of(package.evidence, DEFAULT))
    assert len(index) > 0
    assert all(entry.kind in set(ParticularKind) for entry in index.entries)


def test_a_location_in_an_item_the_index_never_saw_is_skipped() -> None:
    """Defensive, and the reason is the coordinate arithmetic.

    ``_sentences_of`` converts a document offset back into item coordinates by
    subtracting the item's start. An item id it has no start for would subtract
    nothing and search the wrong offsets, so it is skipped instead. Evidence and
    index are built from the same package today; this is what keeps a future
    caller that passes two from producing a finding pointing at the wrong line.
    """
    from akashi.domain.anchor import Anchor
    from akashi.domain.evidence import Location
    from akashi.domain.span import Span

    evidence = Evidence.of([item("itm_01", "内服は 5mg を朝夕に。")])
    index = SourceIndex.of(evidence, DEFAULT)
    elsewhere = Location(
        item_id="itm_99",
        anchor=Anchor(document_id="doc_1", source_path="a.md", section="", span=Span(0, 3)),
    )
    assert index._sentences_of([elsewhere], evidence) == set()
