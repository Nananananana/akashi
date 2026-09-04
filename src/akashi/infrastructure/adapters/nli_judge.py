"""A judge that is a model on this machine, not a model behind an API.

The same `Judge` port `ClaudeJudge` implements, filled by a natural-language
inference model running locally. That the port needed no change to accept it is
the reason it was written as a port.

**Why this exists at all.** akashi compares strings, and `docs/measurements.md`
records what that costs on the five cases rivals are built for: two fabrications
scored 1.0 and one correct paraphrase scored 0.0. Refusing entailment on
principle was the wrong call -- it left akashi weaker than the tools people
already have at the one question they ask most.

**Why it is not the default.** It is a model, so it is not reproducible, it is
not free, and it does not run offline until something has been downloaded. Every
one of those is a fact about the answer and none of them is a reason to refuse.
``--judge nli`` asks for it.

Three things this reports that comparable tools do not:

**The threshold, on every judgement.** A 0-1 consistency score becomes
`supported` or `unsupported` because somebody picked a number, and the number is
half the finding. It goes in ``because`` beside the score.

**Which context won.** The claim is scored against each evidence item separately
and the best is reported with its index, so a reader can go and read the one the
model actually agreed with rather than the pile it was handed.

**Where the model says it does not apply.** HHEM-2.1-Open is English-only by its
own model card, and about half of what akashi reads is Japanese and Chinese. So
a judgement carries a ``scope`` and the report carries it as a limit. A number
produced outside the range its authors claim is not a weaker number, it is a
different kind of thing, and a report that does not say so is the failure this
project exists to remove.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from akashi.errors import ContractError
from akashi.ports.judge import Claim, Judgement, Standing

__all__ = ["DEFAULT_MODEL", "MAX_PAIRS", "MODEL_SCOPES", "NliJudge"]

#: Apache-2.0, 110M parameters, under 600MB at 32-bit, about 1.5s for a 2k-token
#: input on a CPU. Purpose-built for exactly this question rather than adapted to
#: it, which is why it is the default over a general NLI checkpoint.
DEFAULT_MODEL: Final = "vectara/hallucination_evaluation_model"

#: What each shipped default says about itself, quoted rather than assessed.
#: akashi has not measured either on its own corpus and does not imply that it
#: has; the line travels so that a reader knows which question to ask.
MODEL_SCOPES: Final[dict[str, str]] = {
    "vectara/hallucination_evaluation_model": (
        "The judge vectara/hallucination_evaluation_model (HHEM-2.1-Open) states "
        "English-only support on its own model card. Judgements on text in another "
        "language are outside the range its authors claim, and akashi has not measured "
        "what it does there."
    ),
    "MoritzLaurer/deberta-v3-base-zeroshot-v2.0-c": (
        "The judge MoritzLaurer/deberta-v3-base-zeroshot-v2.0-c is an English entailment "
        "model; the '-c' variant is the one its author guarantees was trained only on "
        "commercially-licensed data."
    ),
}

#: Claims times evidence items, bounded. Every pair is a forward pass, and 64
#: claims against 200 retrieved chunks is 12,800 of them -- minutes of CPU for
#: somebody who asked for one audit. The same reasoning as `MAX_CLAIMS`, on the
#: resource this adapter actually spends.
MAX_PAIRS: Final = 4096


class NliJudge:
    """Judgements from a local entailment model, with the threshold on each one."""

    __slots__ = ("_model", "_predict", "_supported_at", "_unsupported_below")

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        predictor: Any = None,
        supported_at: float = 0.5,
        unsupported_below: float | None = None,
    ) -> None:
        """``predictor`` takes ``[(premise, hypothesis), ...]`` and returns scores.

        Taking it as an argument is what makes this testable without a download,
        and what lets a caller bring a model akashi has never heard of -- their
        own fine-tune, a quantised copy, something served over a socket.

        ``supported_at`` is the score at or above which a claim is `supported`.
        ``unsupported_below`` opens an `unclear` band underneath it; left unset it
        equals ``supported_at``, so the answer is binary the way the default
        model's own authors describe it. A caller who wants abstention sets it
        lower and gets a band rather than a sharper line.
        """
        if not 0.0 <= supported_at <= 1.0:
            raise ContractError(f"supported_at is a score between 0 and 1, got {supported_at}")
        floor = supported_at if unsupported_below is None else unsupported_below
        if floor > supported_at:
            raise ContractError(
                f"unsupported_below ({floor}) is above supported_at ({supported_at}), which "
                f"leaves no score that could be either. The band runs upward: below the "
                f"floor is unsupported, at or above supported_at is supported."
            )
        self._model = model
        self._predict = predictor
        self._supported_at = supported_at
        self._unsupported_below = floor

    @property
    def model(self) -> str:
        return self._model

    @property
    def scope(self) -> str:
        """What this model says about where it applies, or nothing.

        Empty for a model akashi ships no note about -- a caller's own fine-tune.
        Silence here means akashi does not know, which is a different thing from
        the model claiming to be universal, and neither is asserted.
        """
        return MODEL_SCOPES.get(self._model, "")

    def judge(self, claims: Sequence[Claim], evidence: Sequence[str]) -> tuple[Judgement, ...]:
        if not claims:
            return ()
        if not evidence:
            raise ContractError(
                "an entailment model needs a premise and none was given. A claim scored "
                "against no evidence comes back unsupported for a reason that has nothing "
                "to do with the claim."
            )
        if len(claims) * len(evidence) > MAX_PAIRS:
            raise ContractError(
                f"{len(claims)} claims against {len(evidence)} contexts is "
                f"{len(claims) * len(evidence)} forward passes, over the {MAX_PAIRS} this "
                f"adapter spends in one call. Narrow the evidence, or judge in batches."
            )

        pairs = [(text, _hypothesis(claim)) for claim in claims for text in evidence]
        scores = list(self._predictor()(pairs))
        if len(scores) != len(pairs):
            raise ContractError(
                f"the predictor returned {len(scores)} scores for {len(pairs)} pairs. akashi "
                f"lines these up positionally, and a missing score moves every judgement "
                f"after it onto the wrong claim."
            )

        width = len(evidence)
        return tuple(
            self._judgement(claim, scores[index * width : (index + 1) * width])
            for index, claim in enumerate(claims)
        )

    def _judgement(self, claim: Claim, scores: Sequence[float]) -> Judgement:
        best = max(range(len(scores)), key=lambda index: scores[index])
        score = float(scores[best])
        if score >= self._supported_at:
            standing = Standing.SUPPORTED
        elif score < self._unsupported_below:
            standing = Standing.UNSUPPORTED
        else:
            standing = Standing.UNCLEAR
        band = (
            f", unsupported below {self._unsupported_below:.2f}"
            if self._unsupported_below != self._supported_at
            else ""
        )
        return Judgement(
            segment_id=claim.segment_id,
            particular=claim.particular,
            standing=standing,
            because=(
                f"consistency {score:.2f} against context {best + 1} of {len(scores)}; "
                f"supported at {self._supported_at:.2f}{band}"
            ),
            model=self._model,
            scope=self.scope,
        )

    def _predictor(self) -> Any:
        if self._predict is None:
            self._predict = _load(self._model)
        return self._predict


def _hypothesis(claim: Claim) -> str:
    """What the model is asked to check.

    The sentence, always. A bare ``2.4kg`` entails nothing on its own, and the
    particular is what the audit was about rather than what a reader can check.
    """
    return claim.text


def _load(model: str) -> Any:
    """The transformers dependency, imported here and nowhere else.

    Inside the function rather than at the top, so that importing
    ``akashi.infrastructure.adapters`` without the extra installed is a message
    about what to install rather than a traceback.
    """
    try:
        from transformers import AutoModelForSequenceClassification
    except ModuleNotFoundError as error:  # pragma: no cover - depends on the environment
        raise ContractError(
            "a local judge needs transformers and torch, which akashi does not install: "
            "`pip install 'akashi[nli]'`. akashi itself has no dependencies; a judge is the "
            "one thing that changes that, and this one also downloads a model."
        ) from error

    loaded = AutoModelForSequenceClassification.from_pretrained(model, trust_remote_code=True)
    return loaded.predict
