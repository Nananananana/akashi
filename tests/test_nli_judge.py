"""The second judge, and the decisions it makes on a caller's behalf.

`NliJudge` fills the same port `ClaudeJudge` does, which is the whole claim
being tested here: a judge is a module and a dispatch entry, not a second path
through the audit.

Everything below runs against an injected predictor. The real model is a 2GB
download and a network call; what is worth pinning is not that transformers
works, it is the arithmetic akashi wraps around it -- the thresholds, the band,
which context is reported, and the bound on how much CPU one audit may spend.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from akashi.errors import ContractError
from akashi.infrastructure.adapters.nli_judge import (
    DEFAULT_MODEL,
    MAX_PAIRS,
    MODEL_SCOPES,
    NliJudge,
)
from akashi.ports.judge import Claim, Judge, Standing

CLAIM = Claim(segment_id="seg_001", text="The tent weighs 2.4kg.", particular="2.4kg")
EVIDENCE = ["A stove.", "The tent weighs 2.4kg.", "A map."]


def scoring(*scores: float) -> object:
    """A predictor returning fixed scores, and recording what it was asked."""

    class Predictor:
        def __init__(self) -> None:
            self.pairs: list[tuple[str, str]] = []

        def __call__(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
            self.pairs = list(pairs)
            return list(scores)

    return Predictor()


# --- it is the same port ------------------------------------------------------


def test_it_satisfies_the_judge_port() -> None:
    """The point of the port. Adding entailment needed no change to
    `claims_for`, to `judge_report`, or to anything that decides a verdict."""
    assert isinstance(NliJudge(predictor=scoring(0.9)), Judge)


def test_the_command_line_reaches_it_by_name() -> None:
    from akashi.interfaces.cli.main import _judge

    assert _judge("nli").model == DEFAULT_MODEL


def test_any_other_name_is_still_a_claude_model() -> None:
    """Adding a door does not close one, and `--judge` took a model name before
    it took an engine name."""
    from akashi.interfaces.cli.main import _judge

    assert _judge("claude-opus-5").model == "claude-opus-5"


# --- the threshold is half the finding, so it is on every judgement ----------


def test_a_score_at_the_threshold_is_supported() -> None:
    judge = NliJudge(predictor=scoring(0.1, 0.5, 0.1), supported_at=0.5)
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert judgement.standing is Standing.SUPPORTED


def test_a_score_below_it_is_unsupported() -> None:
    judge = NliJudge(predictor=scoring(0.1, 0.49, 0.1), supported_at=0.5)
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert judgement.standing is Standing.UNSUPPORTED


def test_the_judgement_says_which_number_decided_it() -> None:
    """A 0-1 score becomes a word because somebody picked a threshold, and a
    reader who cannot see the threshold cannot disagree with it."""
    judge = NliJudge(predictor=scoring(0.1, 0.83, 0.1), supported_at=0.5)
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert "0.83" in judgement.because
    assert "supported at 0.50" in judgement.because


def test_the_judgement_names_the_context_it_agreed_with() -> None:
    """So a reader can open the one the model actually read, rather than the
    pile it was handed."""
    judge = NliJudge(predictor=scoring(0.1, 0.83, 0.2))
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert "context 2 of 3" in judgement.because


def test_there_is_no_unclear_band_unless_one_is_asked_for() -> None:
    """The default model's authors describe a binary decision, and inventing an
    abstention band on top of somebody else's calibration is akashi guessing."""
    judge = NliJudge(predictor=scoring(0.1, 0.4, 0.1))
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert judgement.standing is Standing.UNSUPPORTED
    assert "unsupported below" not in judgement.because


def test_a_band_is_available_and_says_so_on_the_judgement() -> None:
    judge = NliJudge(predictor=scoring(0.1, 0.5, 0.1), supported_at=0.7, unsupported_below=0.3)
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert judgement.standing is Standing.UNCLEAR
    assert "supported at 0.70, unsupported below 0.30" in judgement.because


def test_a_band_that_runs_the_wrong_way_is_refused() -> None:
    """It would leave no score that could be either, and every claim would come
    back `unclear` for a reason that is not about the claim."""
    with pytest.raises(ContractError, match="no score that could be either"):
        NliJudge(supported_at=0.3, unsupported_below=0.7)


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_a_threshold_outside_the_score_range_is_refused(bad: float) -> None:
    with pytest.raises(ContractError, match="between 0 and 1"):
        NliJudge(supported_at=bad)


# --- what the model says about itself travels ---------------------------------


def test_the_default_models_stated_language_scope_is_on_the_judgement() -> None:
    """HHEM-2.1-Open is English-only by its own model card, and about half of
    what akashi reads is Japanese and Chinese."""
    judge = NliJudge(predictor=scoring(0.1, 0.9, 0.1))
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert "English-only" in judgement.scope


def test_the_scope_reaches_the_report_as_a_limit() -> None:
    """The artefact travels and the model card does not (ADR-0005)."""
    import dataclasses

    from akashi.application import audit
    from akashi.application.judging import judge_report
    from akashi.infrastructure.languages import DEFAULT
    from akashi.infrastructure.packages.plain import package_from_contexts

    package = package_from_contexts(EVIDENCE)
    report = audit("The tent weighs 2.6kg.", package, DEFAULT)
    judge = NliJudge(predictor=scoring(*[0.9] * len(EVIDENCE)))
    judged = dataclasses.replace(report, judged=judge_report(report, judge, package.evidence))

    assert judged.judged, "nothing was judged, so this checks nothing"
    assert any("English-only" in line for line in judged.to_dict()["limits"])


def test_a_model_akashi_has_no_note_about_claims_nothing() -> None:
    """Silence is not a claim of universality. akashi does not know what
    somebody's own fine-tune covers and does not invent a sentence saying so."""
    judge = NliJudge("someone/their-own-finetune", predictor=scoring(0.1, 0.9, 0.1))
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert judgement.scope == ""
    assert judgement.model == "someone/their-own-finetune"


def test_every_shipped_default_has_a_scope_note() -> None:
    """A default akashi chose is one akashi has to have read the card for."""
    assert DEFAULT_MODEL in MODEL_SCOPES
    assert all(note.strip() for note in MODEL_SCOPES.values())


# --- the resource this one actually spends ------------------------------------


def test_every_claim_is_scored_against_every_context() -> None:
    judge = NliJudge(predictor=(predictor := scoring(*[0.5] * 6)))
    claims = [CLAIM, Claim(segment_id="seg_002", text="It rained.")]
    judge.judge(claims, EVIDENCE)
    assert predictor.pairs == [  # type: ignore[attr-defined]
        (text, claim.text) for claim in claims for text in EVIDENCE
    ]


def test_the_sentence_is_the_hypothesis_not_the_particular() -> None:
    """A bare `2.4kg` entails nothing on its own."""
    judge = NliJudge(predictor=(predictor := scoring(*[0.5] * 3)))
    judge.judge([CLAIM], EVIDENCE)
    assert {pair[1] for pair in predictor.pairs} == {CLAIM.text}  # type: ignore[attr-defined]


def test_too_many_pairs_is_refused_rather_than_run() -> None:
    """Every pair is a forward pass. 64 claims against 200 chunks is minutes of
    CPU for somebody who asked for one audit."""
    claims = [Claim(segment_id=f"seg_{n:03d}", text="x") for n in range(65)]
    with pytest.raises(ContractError, match=str(MAX_PAIRS)):
        NliJudge(predictor=scoring(0.5)).judge(claims, ["y"] * 64)


def test_no_evidence_is_refused_rather_than_scored_zero() -> None:
    with pytest.raises(ContractError, match="needs a premise"):
        NliJudge(predictor=scoring(0.5)).judge([CLAIM], [])


def test_no_claims_asks_nothing() -> None:
    judge = NliJudge(predictor=(predictor := scoring(0.5)))
    assert judge.judge([], EVIDENCE) == ()
    assert predictor.pairs == []  # type: ignore[attr-defined]


def test_a_predictor_that_returns_the_wrong_count_is_refused() -> None:
    """akashi lines the scores up positionally; a missing one moves every
    judgement after it onto the wrong claim."""
    with pytest.raises(ContractError, match="2 scores for 3 pairs"):
        NliJudge(predictor=scoring(0.5, 0.5)).judge([CLAIM], EVIDENCE)


def test_the_particular_survives_onto_the_judgement() -> None:
    judge = NliJudge(predictor=scoring(0.1, 0.9, 0.1))
    [judgement] = judge.judge([CLAIM], EVIDENCE)
    assert judgement.particular == "2.4kg"
    assert judgement.segment_id == "seg_001"


# --- and nothing here loads unless it is asked for ----------------------------


def test_importing_the_adapter_does_not_import_torch() -> None:
    """`import akashi` on a machine with the extra installed must still reach
    neither an HTTP client nor a 2GB tensor library."""
    import subprocess
    import sys

    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, akashi.infrastructure.adapters.nli_judge as m; "
            "assert 'torch' not in sys.modules and 'transformers' not in sys.modules; "
            "print(m.DEFAULT_MODEL)",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert DEFAULT_MODEL in run.stdout
