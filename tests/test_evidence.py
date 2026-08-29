"""The closed world, and the things that are deliberately not in it.

ADR-0006 and ADR-0012. The evidence set is ``items[]`` and nothing else, and
the withheld candidates are a different type rather than the same list behind a
flag -- so that grounding a particular in something that was deliberately not
sent is unrepresentable instead of merely unwritten.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from akashi.domain.anchor import Anchor, Layer
from akashi.domain.evidence import Evidence, EvidenceItem, Withheld, item
from akashi.domain.extraction import extract_from_answer
from akashi.domain.particular import Particular, ParticularKind
from akashi.domain.segment import segment_answer
from akashi.domain.span import Span
from akashi.infrastructure.languages import DEFAULT

GEAR = item(
    "itm_01",
    "The tent weighs 2.4kg and the stove 300g.",
    document_id="doc_4b1e",
    source_path="notes/design/gear.md",
    section="Gear",
    start=1200,
)


def particulars(answer: str) -> tuple[Particular, ...]:
    return extract_from_answer(segment_answer(answer, DEFAULT), DEFAULT)


def one(answer: str) -> Particular:
    found = particulars(answer)
    assert len(found) == 1, f"expected one particular in {answer!r}, found {len(found)}"
    return found[0]


# --- Grounding ---------------------------------------------------------------


def test_a_particular_that_was_sent_is_located_in_document_coordinates() -> None:
    """Not item coordinates. A reader opens the file, and the file does not
    know it was cut into items."""
    locations = Evidence.of([GEAR]).locate(one("The tent weighs 2.4kg."))
    assert len(locations) == 1
    location = locations[0]
    assert location.item_id == "itm_01"
    assert location.anchor.document_id == "doc_4b1e"
    assert location.anchor.span == Span(1216, 1221)
    assert location.anchor.source_path == "notes/design/gear.md"
    assert location.describe() == "itm_01 notes/design/gear.md (Gear)[1216:1221]"


def test_a_particular_that_was_not_sent_is_located_nowhere() -> None:
    assert Evidence.of([GEAR]).locate(one("The tent weighs 2.6kg.")) == ()


def test_a_particular_is_located_in_every_item_that_holds_it() -> None:
    """Ambiguity is information. Two items quoting the same figure is a real
    thing to know about a package."""
    other = item("itm_02", "Confirmed: 2.4kg.", document_id="doc_77a2", start=40)
    locations = Evidence.of([GEAR, other]).locate(one("The tent weighs 2.4kg."))
    assert [location.item_id for location in locations] == ["itm_01", "itm_02"]


def test_locations_come_back_in_a_fixed_order() -> None:
    """ADR-0003. A report over the same package is the same report every time."""
    other = item("itm_02", "Confirmed: 2.4kg and 2.4kg.", document_id="doc_77a2")
    evidence = Evidence.of([GEAR, other])
    particular = one("The tent weighs 2.4kg.")
    assert evidence.locate(particular) == evidence.locate(particular)
    assert [location.item_id for location in evidence.locate(particular)] == [
        "itm_01",
        "itm_02",
        "itm_02",
    ]


def test_grounding_in_an_interpretation_says_so() -> None:
    """``kiseki``'s distinction survives the crossing. A report that flattened
    it would launder a judgement into a fact."""
    guess = item("itm_03", "Probably about 2.4kg.", layer=Layer.INTERPRETATION)
    fact = item("itm_04", "Measured at 2.4kg.", layer=Layer.FACT)

    interpreted = Evidence.of([guess]).locate(one("The tent weighs 2.4kg."))
    assert interpreted[0].in_an_interpretation

    measured = Evidence.of([fact]).locate(one("The tent weighs 2.4kg."))
    assert not measured[0].in_an_interpretation


def test_an_item_with_no_declared_layer_is_not_an_interpretation_by_default() -> None:
    assert not Evidence.of([GEAR]).locate(one("The tent weighs 2.4kg."))[0].in_an_interpretation


# --- What is not evidence ----------------------------------------------------


def test_the_withheld_candidates_are_a_different_type_from_the_evidence() -> None:
    """ADR-0012. There is no way to write ``locate`` over them, because they do
    not carry the text -- and the contract says they never will."""
    withheld = Withheld(rule="budget_exhausted", reason="ranked 7th; would not fit")
    assert not hasattr(withheld, "text")
    assert not hasattr(withheld, "locate")


def test_what_was_withheld_is_counted_and_reported() -> None:
    """Context for the reader. Four floating particulars beside nine candidates
    dropped for budget is a retrieval problem; four beside none is a model
    problem."""
    evidence = Evidence.of(
        [GEAR],
        [
            Withheld(rule="budget_exhausted", reason="ranked 7th; would not fit"),
            Withheld(rule="budget_exhausted", reason="ranked 8th; would not fit"),
            Withheld(rule="below_threshold", reason="scored 0.11"),
        ],
    )
    assert evidence.withheld_by_rule() == {"below_threshold": 1, "budget_exhausted": 2}


def test_a_withheld_candidate_carries_a_rule_and_a_reason() -> None:
    with pytest.raises(ValueError, match="no rule"):
        Withheld(rule="", reason="something")
    with pytest.raises(ValueError, match="carries no reason"):
        Withheld(rule="budget_exhausted", reason="")


def test_a_figure_that_only_exists_in_the_wider_corpus_still_floats() -> None:
    """ADR-0006, stated as a test because it is the counter-intuitive half. The
    evidence is what was *sent*, and a lucky guess is still a guess."""
    evidence = Evidence.of([item("itm_01", "The tent is light.")])
    assert evidence.locate(one("The tent weighs 2.4kg.")) == ()


# --- The shape of an evidence set --------------------------------------------


def test_an_item_and_its_anchor_must_agree_about_length() -> None:
    with pytest.raises(ValueError, match="one of the two is wrong"):
        EvidenceItem(
            item_id="itm_01",
            text="The tent weighs 2.4kg.",
            anchor=Anchor(document_id="doc_4b1e", span=Span(1200, 1205)),
        )


def test_an_item_needs_an_id_to_be_cited_by() -> None:
    with pytest.raises(ValueError, match="cannot be cited"):
        item("", "The tent weighs 2.4kg.")


def test_two_items_may_not_share_an_id() -> None:
    """A location names an item, and a report a reader cannot follow back to
    one item is a report they cannot check."""
    with pytest.raises(ValueError, match="share the id"):
        Evidence.of([item("itm_01", "one"), item("itm_01", "two")])


def test_an_anchor_needs_a_document() -> None:
    with pytest.raises(ValueError, match="names nothing"):
        Anchor(document_id="", span=Span(0, 5))


def test_narrowing_an_anchor_past_its_own_span_is_refused() -> None:
    """An offset that escaped its item would point a reader at text that was
    never sent."""
    anchor = Anchor(document_id="doc", span=Span(100, 110))
    assert anchor.narrowed(Span(2, 5)).span == Span(102, 105)
    with pytest.raises(ValueError, match="outside the item"):
        anchor.narrowed(Span(2, 50))


def test_narrowing_drops_the_hashes_rather_than_carrying_a_wrong_one() -> None:
    anchor = Anchor(
        document_id="doc", span=Span(100, 110), text_hash="sha256:abc", document_hash="sha256:def"
    )
    assert anchor.narrowed(Span(0, 4)).text_hash == ""


def test_an_empty_package_is_recognisable_as_such() -> None:
    """Every particular then floats, correctly and uselessly. The caller says
    so rather than printing a score."""
    empty = Evidence()
    assert empty.is_empty
    assert len(empty) == 0
    assert empty.characters == 0
    assert empty.locate(one("The tent weighs 2.4kg.")) == ()


def test_an_evidence_set_measures_how_much_was_sent() -> None:
    assert Evidence.of([GEAR]).characters == len(GEAR.text)


def test_an_items_reduced_form_is_built_once() -> None:
    """An audit looks for every particular of the answer in every item, so
    reducing per lookup would be the whole cost of an audit, repeated."""
    assert GEAR.form is GEAR.form
    assert GEAR.form.text == "the tent weighs 2.4kg and the stove 300g."


# --- Properties --------------------------------------------------------------

ANSWERS = st.lists(
    st.sampled_from(
        ["The tent weighs ", "2.4kg", "300g", "2.6kg", " and ", ". ", "第30条", "テント"]
    ),
    max_size=12,
).map("".join)


@given(answer=ANSWERS)
def test_every_location_lands_inside_the_item_that_reported_it(answer: str) -> None:
    evidence = Evidence.of([GEAR])
    for particular in particulars(answer):
        for location in evidence.locate(particular):
            assert GEAR.anchor.span.contains(location.anchor.span)


@given(answer=ANSWERS)
def test_locating_twice_gives_the_same_answer(answer: str) -> None:
    evidence = Evidence.of([GEAR])
    for particular in particulars(answer):
        assert evidence.locate(particular) == evidence.locate(particular)


@given(answer=ANSWERS)
def test_a_particular_taken_from_the_evidence_always_grounds(answer: str) -> None:
    """The other direction of the same check: everything akashi can extract
    from the sources must resolve back into them. A failure here would be a
    normalization or a boundary rule disagreeing with itself."""
    evidence = Evidence.of([GEAR])
    for particular in particulars(GEAR.text):
        assert evidence.locate(particular), f"{particular.describe()} came from the evidence"


def test_a_particular_from_the_evidence_grounds_in_the_evidence() -> None:
    evidence = Evidence.of([GEAR])
    found = particulars(GEAR.text)
    assert [p.text for p in found] == ["2.4kg", "300g"]
    for particular in found:
        assert len(evidence.locate(particular)) == 1


def test_a_particular_of_the_wrong_kind_still_only_matches_its_own_text() -> None:
    """Kinds do not participate in resolution. They are what makes
    ``contradicted`` possible later, and letting one gate a match would mean a
    mis-classified particular silently stopped being checked."""
    evidence = Evidence.of([GEAR])
    as_a_number = Particular(kind=ParticularKind.NUMBER, span=Span(0, 5), text="2.4kg")
    assert len(evidence.locate(as_a_number)) == 1
