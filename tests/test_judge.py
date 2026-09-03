"""A judge annotates an audit; it does not make one.

ADR-0003 said no model runs at audit time, ever, and it was right about the
reason: a verdict that moves when nobody changed anything is not an audit trail.
ADR-0017 keeps that and draws the line one step further out — a *verdict* may
not come from a model, which is not the same rule as nothing a model says may
appear on the artefact.

Every test here is one of the ways that distinction could be lost.

The judge below is a stand-in. A seam against the real SDK needs a network and
an API key and is not something a test suite should carry; what a stand-in can
check is the shape of the boundary, and the boundary is the subject.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

import pytest

from akashi.application import audit
from akashi.application.judging import MAX_CLAIMS, claims_for, judge_report
from akashi.domain.package import ContextPackage
from akashi.domain.report import AuditReport
from akashi.domain.verdict import Verdict
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import as_text
from akashi.ports.judge import Claim, Judge, Judgement, Standing

PACKAGES = Path(__file__).parent / "packages"

#: Grounds `2.4kg` and floats `9.9kg`, so there is exactly one thing to judge.
ANSWER = "テントは 2.4kg、ガスは 9.9kg。"


class Stub:
    """Answers every claim the same way, and says who it is."""

    def __init__(self, standing: Standing = Standing.SUPPORTED, model: str = "stub@1") -> None:
        self._standing = standing
        self._model = model
        self.seen: list[Claim] = []
        self.evidence: list[str] = []

    @property
    def model(self) -> str:
        return self._model

    def judge(self, claims: Sequence[Claim], evidence: Sequence[str]) -> tuple[Judgement, ...]:
        self.seen = list(claims)
        self.evidence = list(evidence)
        return tuple(
            Judgement(
                segment_id=claim.segment_id,
                particular=claim.particular,
                standing=self._standing,
                because="the stub says so",
                model=self._model,
            )
            for claim in claims
        )


def package() -> ContextPackage:
    return load_package(PACKAGES / "gear-ja.json")


def annotated() -> tuple[AuditReport, Stub]:
    report = audit(ANSWER, package(), DEFAULT)
    stub = Stub()
    return dataclasses.replace(report, judged=judge_report(report, stub, package().evidence)), stub


# --- what a judge is shown ---------------------------------------------------


def test_a_grounded_particular_is_never_sent() -> None:
    """akashi already knows the string, the document and the offset. Replacing a
    fact with an opinion could only make the report worse."""
    asked = [claim.particular for claim in claims_for(audit(ANSWER, package(), DEFAULT))]
    assert "9.9kg" in asked
    assert "2.4kg" not in asked


def test_a_contradicted_particular_is_never_sent() -> None:
    """akashi has already named the value the source gives and the offset it
    sits at, which is a stronger and checkable statement than an opinion."""
    report = audit("テントは 2.6kg です。", package(), DEFAULT)
    contradicted = [
        one
        for segment in report.assessment.segments
        for one in segment.particulars
        if one.contradiction is not None
    ]
    if not contradicted:
        pytest.skip("this answer produced no contradiction; the case is elsewhere")
    named = {claim.particular for claim in claims_for(report)}
    assert contradicted[0].particular.text not in named


def test_the_claim_carries_its_sentence() -> None:
    """A bare `9.9kg` entails nothing. What a reader of the evidence would have
    to agree with is the sentence around it."""
    claim = claims_for(audit(ANSWER, package(), DEFAULT))[0]
    assert claim.particular == "9.9kg"
    assert claim.text.strip()
    assert claim.particular in claim.text


def test_the_evidence_is_handed_over_whole() -> None:
    """Trimming it to what akashi thinks is relevant would make the judge's
    answer depend on akashi's own matching, which is the thing the judge is
    there to be independent of."""
    _report, stub = annotated()
    assert stub.evidence == [item.text for item in package().evidence.items]


def test_a_report_with_nothing_floating_asks_nothing() -> None:
    """No claims, no call, no cost."""
    report = audit("テントは 2.4kg。", package(), DEFAULT)
    stub = Stub()
    assert judge_report(report, stub, package().evidence) == ()
    assert stub.seen == []


def test_the_number_of_claims_is_bounded() -> None:
    """A judge costs money per claim. The bound is on the report, so a long
    enough answer cannot turn one audit into an unbounded number of calls."""
    assert MAX_CLAIMS <= 64


# --- what a judgement is, and is not -----------------------------------------


def test_a_judgement_shares_no_word_with_a_verdict() -> None:
    """The most important line here. A reader skimming must not be able to read
    `supported` as `grounded`."""
    from akashi.domain.verdict import Standing as AkashiStanding

    akashi_words = {one.value for one in Verdict} | {one.value for one in AkashiStanding}
    judge_words = {one.value for one in Standing}
    assert not (akashi_words & judge_words)


def test_judgements_do_not_move_the_report_id() -> None:
    """The id hashes the deterministic inputs. The same audit with and without
    judgements carries one id, and `recheck` re-derives it without a network."""
    plain = audit(ANSWER, package(), DEFAULT)
    report, _ = annotated()
    assert report.report_id == plain.report_id


def test_judgements_change_no_count_and_no_verdict() -> None:
    """`Findings`, `Traced` and `Coverage` are the same report either way."""
    plain = audit(ANSWER, package(), DEFAULT).to_dict()
    report, _ = annotated()
    body = report.to_dict()
    for key in ("segments", "counts", "coverage", "unchecked"):
        assert body[key] == plain[key]


def test_every_judgement_names_its_model() -> None:
    """Two runs against two model versions are two different answers."""
    report, _ = annotated()
    assert all(one.model for one in report.judged)
    with pytest.raises(ValueError, match="no model named"):
        Judgement(segment_id="s", standing=Standing.UNCLEAR, because="", model="")


def test_the_artefact_says_what_a_judgement_is() -> None:
    """The artefact travels and the documentation does not (ADR-0005)."""
    from akashi.domain.report import JUDGEMENT_LIMITS

    plain = audit(ANSWER, package(), DEFAULT).to_dict()
    report, _ = annotated()
    body = report.to_dict()
    assert len(body["limits"]) == len(plain["limits"]) + len(JUDGEMENT_LIMITS)
    assert any("not reproducible" in line for line in body["limits"])
    assert any("does not mean the claim is in the text" in line for line in body["limits"])


def test_the_rendering_keeps_them_in_separate_sections() -> None:
    report, _ = annotated()
    printed = as_text(report)
    assert "Judged" in printed
    assert "Not akashi verdicts" in printed
    assert "supported" not in printed.split("Judged")[0]


def test_a_judge_that_answers_the_wrong_number_of_claims_is_refused() -> None:
    """A missing answer shifts every judgement after it onto the wrong
    sentence, and filling the gap would put akashi's own guess on the report
    under somebody else's name."""

    class Short(Stub):
        def judge(self, claims: Sequence[Claim], evidence: Sequence[str]) -> tuple[Judgement, ...]:
            return super().judge(claims, evidence)[:-1]

    report = audit(ANSWER, package(), DEFAULT)
    with pytest.raises(ValueError, match="answered 0 of 1"):
        judge_report(report, Short(), package().evidence)


def test_the_stub_satisfies_the_port() -> None:
    assert isinstance(Stub(), Judge)


# --- the one door ------------------------------------------------------------


def test_importing_akashi_does_not_import_the_sdk() -> None:
    """`akashi.infrastructure.adapters` deliberately does not re-export the
    judge. Without that, `import akashi` reaches an HTTP client on any machine
    with the extra installed -- which is what the import-linter contract found.
    """
    # The SDK has to be *installed* for this to mean anything: with it absent
    # the assertion below is true of every possible implementation, which is the
    # shape of check this repository spends its time removing. CI installs
    # `[dev,claude]` in the job that runs the suite.
    pytest.importorskip(
        "anthropic",
        reason="without the SDK installed this test passes whatever akashi does",
    )
    program = (
        "import sys, akashi, akashi.interfaces.cli.main, "
        "akashi.infrastructure.adapters; print('anthropic' in sys.modules)"
    )
    result = subprocess.run(  # noqa: S603 - the program is the literal above
        [sys.executable, "-c", program], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False", "importing akashi pulled in the SDK"


def test_the_adapter_is_usable_without_the_sdk_installed() -> None:
    """Absence is a message about what to install, not an ImportError from
    `import akashi`. The SDK is imported inside a function, and a caller who
    brings a client never reaches that import at all."""
    from akashi.infrastructure.adapters.claude_judge import ClaudeJudge

    assert isinstance(ClaudeJudge(client=object()), Judge)


def test_the_adapter_reads_a_structured_reply_and_names_the_model() -> None:
    """The reply is constrained by a schema rather than parsed out of prose: a
    step that works until the day it silently does not is worse than one that
    refuses."""
    from akashi.infrastructure.adapters.claude_judge import ClaudeJudge

    class Block:
        type = "text"
        text = json.dumps(
            {"judgements": [{"standing": "unsupported", "because": "the evidence gives 2.4kg"}]}
        )

    class Response:
        content: ClassVar[list[object]] = [Block()]
        stop_reason = "end_turn"

    class Client:
        def __init__(self) -> None:
            self.messages = self

        def create(self, **kwargs: Any) -> Response:
            self.kwargs = kwargs
            return Response()

    client = Client()
    judged = ClaudeJudge(client=client, model="pretend@9").judge(
        [Claim(segment_id="seg_001", text="ガスは 9.9kg。", particular="9.9kg")],
        ["ガスは 250mg。"],
    )
    assert judged[0].standing is Standing.UNSUPPORTED
    assert judged[0].model == "pretend@9"
    assert client.kwargs["output_config"]["format"]["type"] == "json_schema"


def test_a_refused_reply_is_not_turned_into_a_judgement() -> None:
    """akashi records what a judge said and does not answer on its behalf."""
    from akashi.errors import ContractError
    from akashi.infrastructure.adapters.claude_judge import ClaudeJudge

    class Response:
        content: ClassVar[list[object]] = []
        stop_reason = "refusal"
        stop_details = None

    class Client:
        def __init__(self) -> None:
            self.messages = self

        def create(self, **kwargs: Any) -> Response:
            return Response()

    with pytest.raises(ContractError, match="declined"):
        ClaudeJudge(client=Client()).judge([Claim(segment_id="s", text="t", particular="p")], ["e"])


def test_the_help_names_the_model_the_adapter_would_use() -> None:
    """The CLI cannot import the adapter to build its help text without pulling
    the SDK into every run, so the model name is written twice. This is what
    keeps the two in step."""
    import contextlib
    import io

    from akashi.infrastructure.adapters.claude_judge import DEFAULT_MODEL
    from akashi.interfaces.cli.main import _parser

    printed = io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stdout(printed):
        _parser().parse_args(["audit", "--help"])
    assert DEFAULT_MODEL in printed.getvalue(), (
        "the CLI's --judge help names a different model from the one the adapter "
        "would use. The name is written twice because the CLI cannot import the "
        "adapter without pulling the SDK into every run; this is what keeps the "
        "two in step."
    )


def test_the_report_schema_requires_the_model_on_every_judgement() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    from conftest import published_schema

    schema = json.loads(published_schema().read_text(encoding="utf-8"))
    judged = schema["properties"]["judged"]
    assert set(judged["items"]["required"]) >= {"model", "standing", "because"}
    assert judged["items"]["properties"]["standing"]["enum"] == [
        "supported",
        "unsupported",
        "unclear",
    ]
    report, _ = annotated()
    jsonschema.validate(report.to_dict(), schema)
