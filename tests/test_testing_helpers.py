"""akashi where the rest of somebody's checks already live.

The thing being tested is not the arithmetic -- `evaluate` is tested elsewhere.
It is what a person reads at 2am when CI is red: whether the failure names the
finding or just a number, and whether a waiver can quietly stop meaning
anything.
"""

from __future__ import annotations

import pytest

from akashi.testing import GroundingError, assert_grounded, assert_sample_grounded

ANSWER = "The tent weighs 2.4kg and the gas is 9.9kg."
CONTEXTS = ["The tent weighs 2.4kg.", "Gas cartridge, 250mg."]


def test_it_passes_when_the_bar_is_met() -> None:
    result = assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.5)
    assert result.grounded_share == 0.5


def test_it_returns_the_result_so_a_test_can_go_on() -> None:
    """Otherwise the next assertion audits the same answer a second time."""
    result = assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.5)
    assert result.grounded == ("2.4kg",)


def test_it_fails_when_the_bar_is_not_met() -> None:
    with pytest.raises(GroundingError):
        assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.9)


def test_the_failure_is_an_assertion_error() -> None:
    """So unittest, plain scripts and anything that treats an exception as a
    failure all work, not only pytest."""
    assert issubclass(GroundingError, AssertionError)


def test_the_failure_carries_the_report() -> None:
    with pytest.raises(GroundingError) as raised:
        assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.9)
    assert raised.value.result.floating == ("9.9kg",)


# --- what a person reads when the build is red -------------------------------


def test_the_message_names_the_floating_particulars() -> None:
    """`assert 0.5 >= 0.9` says a build went red and nothing about why."""
    with pytest.raises(GroundingError) as raised:
        assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.9)
    message = str(raised.value)
    assert "9.9kg" in message
    assert "0.500" in message
    assert "1 of 2 checkable particulars" in message


def test_the_message_carries_the_limits_the_number_was_produced_under() -> None:
    """The same reason `limits` is on the artefact: the CI log is where this
    number will be read, and the README is not open beside it."""
    with pytest.raises(GroundingError) as raised:
        assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.9)
    assert "statement about strings" in str(raised.value)


def test_the_message_says_what_was_skipped() -> None:
    with pytest.raises(GroundingError) as raised:
        assert_grounded(answer="```\ncode\n```\nThe gas is 9.9kg.", contexts=CONTEXTS, at_least=0.9)
    assert "skipped" in str(raised.value)


def test_an_answer_with_nothing_checkable_fails_rather_than_passing() -> None:
    """A share of `None` compared against a bar is not a pass. Treating it as
    one is how a test that checks nothing stays green forever."""
    with pytest.raises(GroundingError, match="no share to compare"):
        assert_grounded(answer="It depends on the weather.", contexts=CONTEXTS, at_least=0.0)


# --- a waiver that stopped meaning anything ----------------------------------


def test_a_named_floating_particular_can_be_waived() -> None:
    """A figure the answer computed, a date it formatted differently."""
    result = assert_grounded(
        answer=ANSWER, contexts=CONTEXTS, at_least=1.0, allow_floating=["9.9kg"]
    )
    assert result.floating == ("9.9kg",)


def test_a_waiver_for_something_that_no_longer_floats_is_itself_a_failure() -> None:
    """The defect this exists for. A suite full of stale waivers is a suite
    that has stopped checking, and nothing else would ever say so."""
    with pytest.raises(GroundingError, match="did not float"):
        assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=0.5, allow_floating=["2.4kg"])


def test_a_waiver_for_something_absent_entirely_is_also_a_failure() -> None:
    with pytest.raises(GroundingError, match="did not float"):
        assert_grounded(
            answer=ANSWER, contexts=CONTEXTS, at_least=0.5, allow_floating=["17 tonnes"]
        )


def test_the_message_says_which_waivers_were_applied() -> None:
    with pytest.raises(GroundingError) as raised:
        assert_grounded(
            answer="The tent weighs 3.3kg and the gas is 9.9kg.",
            contexts=CONTEXTS,
            at_least=1.0,
            allow_floating=["9.9kg"],
        )
    assert "waived by allow_floating: 9.9kg" in str(raised.value)


# --- the bar is the caller's ---------------------------------------------------


def test_there_is_no_default_bar() -> None:
    """A threshold akashi picked would be a threshold nobody chose, on a number
    whose meaning depends on the corpus it was computed over."""
    with pytest.raises(TypeError):
        assert_grounded(answer=ANSWER, contexts=CONTEXTS)  # type: ignore[call-arg]


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_a_bar_outside_the_range_is_refused(bad: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        assert_grounded(answer=ANSWER, contexts=CONTEXTS, at_least=bad)


# --- and it takes the shapes the rest of akashi takes -------------------------


def test_it_takes_a_ragas_sample() -> None:
    result = assert_sample_grounded(
        {"user_input": "q", "response": ANSWER, "retrieved_contexts": CONTEXTS}, at_least=0.5
    )
    assert result.grounded_share == 0.5


def test_it_takes_a_deepeval_sample() -> None:
    result = assert_sample_grounded(
        {"input": "q", "actual_output": ANSWER, "retrieval_context": CONTEXTS}, at_least=0.5
    )
    assert result.grounded_share == 0.5


def test_options_reach_the_audit() -> None:
    """`matcher`, `languages` and the rest are the same options `evaluate` takes;
    this is a shell over it, not a second way in."""
    from akashi.domain.matching import matcher_named

    result = assert_grounded(
        answer=ANSWER, contexts=CONTEXTS, at_least=0.5, matcher=matcher_named("exact")
    )
    assert result.report.audited.matcher == "exact"
