"""A dataset, not a row at a time.

Every rival takes a table and returns a table; akashi took one answer, so a
person with 500 rows wrote the loop, the aggregation and the error handling
themselves -- and wrote them the way the number tempts you to, which is a mean
of the per-row shares over the rows that happened not to raise.

Both of those are wrong in ways this file pins down.
"""

from __future__ import annotations

import pytest

from akashi import Results, evaluate_samples
from akashi.errors import ContractError

#: One grounded particular. Share 1.0.
ONE = {"question": "q", "answer": "The tent weighs 2.4kg.", "contexts": ["The tent weighs 2.4kg."]}

#: One grounded, three floating. Share 0.25.
FOUR = {
    "question": "q",
    "answer": "A is 1.1kg, B is 2.2kg, C is 3.3kg, D is 4.4kg.",
    "contexts": ["D is 4.4kg."],
}

#: Nothing to check at all. Share None.
NONE = {"question": "q", "answer": "It depends on the weather.", "contexts": ["Anything."]}

#: No context, which akashi refuses rather than scoring zero.
BAD = {"question": "q", "answer": "The tent weighs 2.4kg.", "contexts": []}


# --- the aggregate is over particulars, not over rows ------------------------


def test_the_share_is_not_the_mean_of_the_row_shares() -> None:
    """The whole reason this returns an object rather than a list.

    A mean weights a one-particular answer the same as a forty-particular one.
    Here the two differ by a quarter, which is more than most people would
    accept as a rounding difference in a number they are about to quote.
    """
    results = evaluate_samples([ONE, FOUR])
    assert [one.grounded_share for one in results] == [1.0, 0.25]

    mean = (1.0 + 0.25) / 2
    assert results.grounded_share == pytest.approx(2 / 5)
    assert results.grounded_share != pytest.approx(mean)


def test_a_row_with_nothing_checkable_is_not_a_zero() -> None:
    """It has not scored. Averaging it in as 0.0 reports a failure that did not
    happen, and the temptation to do it is exactly why this is not a mean."""
    with_nothing = evaluate_samples([ONE, NONE])
    assert with_nothing[1].grounded_share is None
    assert with_nothing.grounded_share == 1.0
    assert with_nothing.scored == 1


def test_no_row_with_anything_to_check_is_none_rather_than_zero() -> None:
    results = evaluate_samples([NONE, NONE])
    assert len(results) == 2
    assert results.grounded_share is None


# --- a refused row loses itself and nothing else -----------------------------


def test_one_bad_row_does_not_lose_the_others() -> None:
    results = evaluate_samples([ONE, BAD, FOUR])
    assert len(results) == 2
    assert [one.grounded_share for one in results] == [1.0, 0.25]


def test_a_refused_row_is_kept_and_says_which_one_and_why() -> None:
    """Dropping it silently is the failure this project exists to remove: a run
    over 499 rows reported as a run over 500."""
    results = evaluate_samples([ONE, BAD, FOUR])
    [refusal] = results.refused
    assert refusal.index == 1
    assert "no context" in refusal.reason


def test_the_description_names_the_refusals_beside_the_number() -> None:
    """Whoever prints this is the one who will quote the number."""
    said = evaluate_samples([ONE, BAD, FOUR]).describe()
    assert "0.400" in said
    assert "5 particulars" in said
    assert "2 of 2 rows" in said
    assert "1 refused" in said


def test_a_clean_run_does_not_mention_refusals() -> None:
    assert "refused" not in evaluate_samples([ONE, FOUR]).describe()


def test_an_empty_dataset_is_empty_rather_than_an_error() -> None:
    results = evaluate_samples([])
    assert len(results) == 0
    assert results.grounded_share is None


# --- the shape a table wants --------------------------------------------------


def test_every_row_carries_the_limits_it_was_produced_under() -> None:
    """A column of numbers is precisely the thing that gets copied away from
    the note beside the table."""
    for row in evaluate_samples([ONE, FOUR]).rows():
        assert row["limits"]
        assert any("statement about strings" in line for line in row["limits"])


def test_a_row_can_be_traced_back_to_its_report() -> None:
    results = evaluate_samples([ONE, FOUR])
    for index, row in enumerate(results.rows()):
        assert row["row"] == index
        assert row["report_id"] == results[index].report.report_id


def test_the_rows_are_plain_data() -> None:
    """`pandas.DataFrame(results.rows())` has to work, and akashi does not
    depend on pandas."""
    import json

    json.dumps(evaluate_samples([ONE, FOUR, NONE]).rows())


def test_the_three_vocabularies_mix_in_one_dataset() -> None:
    results = evaluate_samples(
        [
            {"user_input": "q", "response": ONE["answer"], "retrieved_contexts": ONE["contexts"]},
            {"input": "q", "actual_output": ONE["answer"], "retrieval_context": ONE["contexts"]},
            ONE,
        ]
    )
    assert len(results) == 3
    assert {one.grounded_share for one in results} == {1.0}


def test_it_takes_an_iterator_rather_than_only_a_list() -> None:
    """A dataset that does not fit in memory is the ordinary case for the
    people this is for."""
    results = evaluate_samples(iter([ONE, FOUR]))
    assert len(results) == 2


def test_the_collection_is_the_reports_and_adds_nothing() -> None:
    """A shell, like `evaluate`: the per-row numbers are the reports' own."""
    from akashi import evaluate_sample

    results = evaluate_samples([ONE, FOUR])
    assert [one.report.report_id for one in results] == [
        evaluate_sample(ONE).report.report_id,
        evaluate_sample(FOUR).report.report_id,
    ]


def test_results_is_exported() -> None:
    assert (
        Results(
            (),
        ).grounded_share
        is None
    )


# --- the shapes a dataset actually arrives in --------------------------------


class FakeFrame:
    """A DataFrame's two relevant behaviours: it has columns, and iterating it
    gives their names rather than the rows."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.columns = list(rows[0]) if rows else []

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.columns)

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return self._rows


def test_a_dataframe_is_read_as_rows_and_not_as_column_names() -> None:
    """The quiet wrong answer this exists to stop. Iterating a DataFrame gives
    'question', 'answer', 'contexts' -- three strings, all refused, and an empty
    `Results` carrying three refusals that look like the caller's data was bad.
    """
    frame = FakeFrame([dict(ONE), dict(FOUR)])
    assert list(iter(frame)) == ["question", "answer", "contexts"]

    results = evaluate_samples(frame)
    assert len(results) == 2
    assert results.refused == ()
    assert [one.grounded_share for one in results] == [1.0, 0.25]


def test_one_mapping_is_refused_rather_than_read_as_its_keys() -> None:
    with pytest.raises(ContractError, match="would audit its keys"):
        evaluate_samples(ONE)


def test_one_string_is_refused_rather_than_read_as_its_characters() -> None:
    with pytest.raises(ContractError, match="list of its characters"):
        evaluate_samples("an answer")


def test_a_plain_iterable_of_dicts_still_goes_straight_through() -> None:
    """Adding a door does not close one; a HuggingFace Dataset is this shape."""
    results = evaluate_samples(iter([ONE, FOUR]))
    assert len(results) == 2
