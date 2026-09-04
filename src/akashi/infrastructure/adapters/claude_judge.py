"""A judge that reads, backed by the Anthropic API.

The one layer permitted to know that anything outside akashi exists, and the
first thing here that reaches the network. Everything below it stays offline and
stdlib-only: `pip install akashi` brings no dependency and opens no socket, and
this module is behind an extra (`akashi[claude]`) and an explicit `--judge`.

**It answers a question akashi cannot.** akashi compares strings, so a claim the
answer paraphrased out of the evidence is `floating` -- true, and not what the
reader wanted to know. This asks whether the evidence supports it, and returns
an opinion labelled as one, under the name of the model that gave it.

Three decisions worth the words:

**Structured output, not prose.** `output_config.format` constrains the reply to
a schema, so one claim in gives one judgement out and a caller can line them up.
Parsing a model's prose for a verdict is the kind of step that works until the
day it silently does not.

**One request for every claim in the report, not one per claim.** A judge that
answered each claim alone would see the sentence and not the answer around it,
and would cost a round trip per floating figure.

**A refusal is not a judgement.** If the model declines, or answers with fewer
judgements than there were claims, this raises. Filling the gap with `unclear`
would put akashi's own guess on the report under somebody else's name.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Final

from akashi.errors import ContractError
from akashi.ports.judge import Claim, Judgement, Standing

__all__ = ["DEFAULT_MODEL", "ClaudeJudge"]

#: What answers when nobody chooses. Named on every judgement it produces,
#: because two runs against two model versions are two different answers.
DEFAULT_MODEL: Final = "claude-opus-5"

_SYSTEM: Final = (
    "You decide whether a body of evidence supports a claim, and nothing else.\n"
    "\n"
    "You are the second half of an audit. The first half already compared strings: "
    "every claim you are given is one whose exact wording does NOT appear in the "
    "evidence. That is why it reached you. So 'it is not written there' is never an "
    "answer -- it is the premise.\n"
    "\n"
    "For each claim, answer:\n"
    "  supported    the evidence entails it, in other words or after obvious reading\n"
    "  unsupported  the evidence is about this and does not entail it, or contradicts it\n"
    "  unclear      the evidence does not settle it either way\n"
    "\n"
    "Rules:\n"
    "- Use only the evidence given. Do not use anything you know about the world.\n"
    "- A number that had to be calculated from the evidence is 'unsupported' unless "
    "the evidence states the result.\n"
    "- 'because' is one sentence, quoting the part of the evidence you relied on. "
    "If you relied on nothing, say that.\n"
    "- Answer every claim, in the order given, once each."
)

_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "judgements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "standing": {"type": "string", "enum": ["supported", "unsupported", "unclear"]},
                    "because": {"type": "string"},
                },
                "required": ["standing", "because"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["judgements"],
    "additionalProperties": False,
}


class ClaudeJudge:
    """Judgements from Claude, with the model named on each one."""

    __slots__ = ("_client", "_effort", "_model")

    def __init__(
        self, client: Any = None, model: str = DEFAULT_MODEL, effort: str = "high"
    ) -> None:
        """``client`` is an `anthropic.Anthropic`; one is made if none is given.

        Taking it as an argument is what keeps this testable without a network
        and what lets a caller bring their own configured client -- a proxy, a
        base URL, a different credential.
        """
        self._client = client if client is not None else _client()
        self._model = model
        self._effort = effort

    @property
    def model(self) -> str:
        return self._model

    def judge(self, claims: Sequence[Claim], evidence: Sequence[str]) -> tuple[Judgement, ...]:
        if not claims:
            return ()

        response = self._client.messages.create(
            model=self._model,
            max_tokens=16000,
            system=_SYSTEM,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            messages=[{"role": "user", "content": _prompt(claims, evidence)}],
        )

        if getattr(response, "stop_reason", "") == "refusal":
            details = getattr(response, "stop_details", None)
            raise ContractError(
                f"the judge declined to answer ({getattr(details, 'category', 'no category')}). "
                f"akashi records what a judge said and does not supply an answer on its "
                f"behalf, so this report has no judgements rather than invented ones."
            )

        return _read(response, claims, self._model)


def _client() -> Any:
    """The SDK, imported here and nowhere else.

    Imported inside the function rather than at the top, so that importing
    `akashi.infrastructure.adapters` on a machine without the extra installed
    does not fail. Absence is a message about what to install, not a traceback.
    """
    try:
        import anthropic
    except ModuleNotFoundError as error:  # pragma: no cover - depends on the environment
        raise ContractError(
            "a Claude judge needs the anthropic SDK, which akashi does not install: "
            "`pip install 'akashi[claude]'`. akashi itself has no dependencies and "
            "reaches no network, and a judge is the one thing that changes that."
        ) from error
    return anthropic.Anthropic()


def _prompt(claims: Sequence[Claim], evidence: Sequence[str]) -> str:
    """The evidence whole, then the claims numbered.

    The evidence is not trimmed to what akashi thinks is relevant: that would
    make the judge's answer depend on akashi's own matching, which is the thing
    the judge is here to be independent of.
    """
    parts = ["<evidence>"]
    parts += [f"<item index={index}>\n{text}\n</item>" for index, text in enumerate(evidence, 1)]
    parts += ["</evidence>", "", "<claims>"]
    for index, claim in enumerate(claims, 1):
        subject = f" (about: {claim.particular})" if claim.particular else ""
        parts.append(f"{index}.{subject} {claim.text}")
    parts += ["</claims>", "", f"Answer all {len(claims)} claims, in order."]
    return "\n".join(parts)


def _read(response: Any, claims: Sequence[Claim], model: str) -> tuple[Judgement, ...]:
    text = next(
        (block.text for block in getattr(response, "content", []) if block.type == "text"), ""
    )
    try:
        body = json.loads(text)
        answers = body["judgements"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ContractError(
            f"the judge's reply did not match the schema it was asked for: {error}. "
            f"akashi does not read a verdict out of prose -- a step that works until "
            f"the day it silently does not is worse than one that refuses."
        ) from error

    if len(answers) != len(claims):
        raise ContractError(
            f"the judge answered {len(answers)} of {len(claims)} claims. Filling the gap "
            f"would put akashi's own guess on the report under somebody else's name, and "
            f"a missing answer shifts every judgement after it onto the wrong sentence."
        )

    return tuple(
        Judgement(
            segment_id=claim.segment_id,
            particular=claim.particular,
            standing=Standing(answer["standing"]),
            because=str(answer["because"]),
            model=model,
        )
        for claim, answer in zip(claims, answers, strict=True)
    )
