"""What the evidence does say, when akashi cannot say the answer is in it.

`floating` on its own is a dead end. It tells a reader the figure is in none of
the text and leaves them to go and read all of it -- which akashi has already
done. This hands over the candidates it looked at.

The whole design risk is that a list beside a floating value reads as *"did you
mean"*. Every test below is about keeping it from meaning that: no similarity,
no ranking, no confidence, a name that cannot be mistaken for a finding, and
nothing offered at all when the value grounded.
"""

from __future__ import annotations

import pytest

from akashi import evaluate
from akashi.domain.verdict import CheckedParticular, Standing


def particulars(answer: str, contexts: list[str]) -> list[CheckedParticular]:
    report = evaluate(answer=answer, contexts=contexts).report
    return [one for segment in report.assessment.segments for one in segment.particulars]


CONTEXTS = ["The tent weighs 3.1kg. The pack is 900g.", "Gas is 250mg."]


# --- the refusal becomes an answer --------------------------------------------


def test_a_floating_figure_is_told_what_the_evidence_carries_instead() -> None:
    """The defect this closes. Before, a reader learned only that 2.6kg was in
    none of the text -- true, and the end of the conversation."""
    [one] = particulars("The tent weighs 2.6kg.", CONTEXTS)
    assert one.standing is Standing.FLOATING
    assert [entry.text for entry in one.nearby] == ["3.1kg", "900g", "250mg"]


def test_every_neighbour_carries_the_offset_a_reader_would_open() -> None:
    """A list of strings would be a hint. A list of offsets is evidence."""
    [one] = particulars("The tent weighs 2.6kg.", CONTEXTS)
    assert one.nearby
    for entry in one.nearby:
        span = entry.anchor.span
        assert span.end > span.start
        source = CONTEXTS[int(entry.item_id.split("_")[-1]) - 1]
        assert source[span.start : span.end] == entry.text


def test_the_nearest_scope_comes_first() -> None:
    """Scope is the ordering and the only one. The item the rest of the segment
    grounded into is nearer than one nothing grounded into.

    The grounded value is deliberately in the *second* document, so that scope
    order and document order disagree. Written the other way round the test
    passed with the scopes removed entirely, which is a test that agrees with
    every implementation.
    """
    contexts = ["Gas is 250mg.", "The tent weighs 3.1kg. The pack is 900g."]
    [grounded, floating] = particulars("The pack is 900g and the tent weighs 2.6kg.", contexts)
    assert grounded.standing is Standing.GROUNDED
    assert grounded.locations[0].item_id == "itm_02", "the setup does not separate the two orders"
    assert floating.standing is Standing.FLOATING
    assert floating.nearby[0].item_id == "itm_02", (
        "document order would have put itm_01 first; scope order must not"
    )


def test_only_the_same_kind_is_offered() -> None:
    """A date does not explain a quantity, and offering one would be noise
    dressed as help."""
    [one] = particulars(
        "The tent weighs 2.6kg.", ["Signed on 2024-03-01 by Borden Systems. Mass 3.1kg."]
    )
    assert {entry.kind for entry in one.nearby} == {one.particular.kind}


# --- and it never becomes a claim ----------------------------------------------


def test_a_grounded_particular_is_offered_nothing() -> None:
    """akashi knows where that string is. A list of other values beside it
    would invite a reader to doubt a fact."""
    [one] = particulars("The tent weighs 3.1kg.", CONTEXTS)
    assert one.standing is Standing.GROUNDED
    assert one.nearby == ()


def test_a_grounded_particular_carrying_neighbours_is_refused() -> None:
    """Not reachable through `audit`, and the invariant is asserted where it
    can be violated -- a future caller constructing one by hand."""
    from akashi.domain.anchor import Anchor
    from akashi.domain.contradiction import SourceParticular
    from akashi.domain.evidence import Location
    from akashi.domain.particular import Particular, ParticularKind
    from akashi.domain.span import Span

    anchor = Anchor(document_id="doc", span=Span(0, 5))
    with pytest.raises(ValueError, match="grounded and also carries neighbours"):
        CheckedParticular(
            particular=Particular(kind=ParticularKind.QUANTITY, text="2.4kg", span=Span(0, 5)),
            locations=(Location(item_id="itm_01", anchor=anchor),),
            nearby=(
                SourceParticular(
                    item_id="itm_01",
                    kind=ParticularKind.QUANTITY,
                    text="3.1kg",
                    anchor=anchor,
                    sentence=Span(0, 5),
                ),
            ),
        )


def test_a_named_source_is_not_replaced_by_a_list() -> None:
    """When akashi can say *the source gives 5mg instead*, that is a stronger
    statement than three candidates, and the list must not dilute it."""
    found = [
        one
        for one in particulars("The dose is 5 grams.", ["The dose is 5mg. Volume 250ml."])
        if one.contradiction is not None
    ]
    if not found:
        pytest.skip("this pair produced no contradiction, so it does not exercise the rule")
    assert found[0].nearby == ()


def test_the_particular_is_not_its_own_neighbour() -> None:
    """Offering the value back as *what the evidence says instead* would be a
    lie by omission.

    Exercised against the index directly rather than through `evaluate`: no
    answer reaches this state today, because a particular whose exact text the
    evidence carries as a particular of its own grounds instead of floating. The
    guard is for a matcher stricter than any shipped one -- which is a thing a
    caller can supply -- and a defensive branch nothing can reach is a branch
    that quietly stops working.
    """
    from akashi.domain.anchor import Anchor
    from akashi.domain.contradiction import SourceIndex, SourceParticular
    from akashi.domain.evidence import Evidence, item
    from akashi.domain.particular import Particular, ParticularKind
    from akashi.domain.span import Span

    def entry(text: str, start: int) -> SourceParticular:
        return SourceParticular(
            item_id="itm_01",
            kind=ParticularKind.QUANTITY,
            text=text,
            anchor=Anchor(document_id="doc", span=Span(start, start + len(text))),
            sentence=Span(0, 40),
        )

    index = SourceIndex(entries=(entry("2.4kg", 0), entry("3.1kg", 10)))
    floating = Particular(kind=ParticularKind.QUANTITY, text="2.4kg", span=Span(0, 5))
    evidence = Evidence.of([item("itm_01", "2.4kg and 3.1kg", document_id="doc")])

    offered = index.nearby(floating, (), evidence)
    assert offered, "nothing was offered, so the exclusion is not what is being seen"
    assert [one.text for one in offered] == ["3.1kg"]


def test_the_list_is_bounded() -> None:
    """An answer against two hundred retrieved chunks would otherwise put two
    hundred values beside one floating figure, which is the same as saying
    nothing in a longer form."""
    many = [f"Mass {n}.{n % 10}kg." for n in range(1, 60)]
    [one] = particulars("The tent weighs 999.9kg.", many)
    assert 0 < len(one.nearby) <= 5


# --- what the artefact says ----------------------------------------------------


def test_the_report_carries_them_under_a_name_that_is_not_a_finding() -> None:
    body = evaluate(answer="The tent weighs 2.6kg.", contexts=CONTEXTS).to_dict()
    [one] = [p for s in body["segments"] for p in s.get("particulars", [])]
    assert one["standing"] == "floating"
    assert [entry["text"] for entry in one["nearby_in_evidence"]] == ["3.1kg", "900g", "250mg"]
    assert "contradiction" not in one


def test_the_published_schema_describes_what_they_are_not() -> None:
    """A consumer reading these as candidate corrections is reading something
    akashi did not say, and the contract is where that has to be written."""
    import json
    from pathlib import Path

    schema = json.loads(
        (Path("src/akashi/schemas/audit-report-1.json")).read_text(encoding="utf-8")
    )
    described = schema["$defs"]["particular"]["properties"]["nearby_in_evidence"]["description"]
    assert "NOT a finding" in described
    assert "no similarity" in described


def test_the_report_still_validates() -> None:
    import json
    from pathlib import Path

    import jsonschema

    schema = json.loads(
        (Path("src/akashi/schemas/audit-report-1.json")).read_text(encoding="utf-8")
    )
    body = evaluate(answer="The tent weighs 2.6kg.", contexts=CONTEXTS).to_dict()
    jsonschema.validate(body, schema)


def test_report_id_does_not_move_when_neighbours_appear() -> None:
    """They are derived from the same inputs by the same code, so they are part
    of the audit rather than an annotation on it -- but they are also not an
    input, and a reader rechecking a report must get the same id."""
    first = evaluate(answer="The tent weighs 2.6kg.", contexts=CONTEXTS).report
    again = evaluate(answer="The tent weighs 2.6kg.", contexts=CONTEXTS).report
    assert first.report_id == again.report_id
    assert first.to_dict() == again.to_dict()


def test_the_certificate_lists_them_and_says_they_are_not_proposals() -> None:
    """The certificate is what somebody signs. A list of values beside a
    floating one, unlabelled, is the one place this feature could do harm."""
    from akashi.infrastructure.rendering.certificate import certificate

    body = evaluate(
        answer="The tent weighs 2.6kg.", contexts=["The tent weighs 3.1kg. The pack is 900g."]
    ).to_dict()
    page = certificate(body)
    assert "the evidence carries, near here" in page
    assert "listed, not proposed" in page
    assert "3.1kg" in page


def test_a_grounded_answer_puts_no_such_line_on_the_certificate() -> None:
    from akashi.infrastructure.rendering.certificate import certificate

    body = evaluate(
        answer="The tent weighs 3.1kg.", contexts=["The tent weighs 3.1kg. The pack is 900g."]
    ).to_dict()
    assert "near here" not in certificate(body)


def test_the_one_call_api_hands_them_over_too() -> None:
    """`result.floating` told a caller a figure was absent and stopped there.
    Anyone building on akashi had to walk the report to get further."""
    from akashi import evaluate as run

    result = run(answer="The tent weighs 2.6kg.", contexts=["The tent weighs 3.1kg."])
    assert result.floating == ("2.6kg",)
    assert result.nearby == {"2.6kg": ("3.1kg",)}
