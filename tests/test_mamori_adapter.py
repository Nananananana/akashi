"""The seam between akashi and the redactor, and why it is not zero lines.

ADR-0008: an answer generated from a protected prompt talks about
`<PERSON_001>`, and auditing it without putting the values back reports every
honest particular as fabricated. `mamori` puts them back. This is what sits
between them.

`ports/restorer.py` said `mamori`'s `PrivacySession` *"already satisfies it
without knowing akashi exists"*. It does not: `restore` returns a
`RestorationResult`, not a string, and the difference between an object carrying
`.text` and the text is the entire content of the adapter.

Nothing here imports `mamori`. Lifting `.text` needs no knowledge of the class
it came from, so akashi installs and runs without the package and a caller who
has a session hands it over. The seam test that uses the *real* library is a
separate job (#59) — this file is about the shape.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from akashi.application import audit
from akashi.application.admit import admit
from akashi.domain.evidence import Evidence, item
from akashi.domain.package import ContextPackage, Protection
from akashi.errors import ContractError
from akashi.infrastructure.adapters import MamoriRestorer
from akashi.infrastructure.languages import DEFAULT
from akashi.ports import Restorer

PSEUDONYMIZED = ContextPackage(
    contract="tsumugi.context-package/1",
    evidence=Evidence.of([item("itm_01", "担当は田中太郎、金額は 45,000 円。")]),
    protection=Protection(by="mamori@0.27.0", scope="session-2f11", reversible=True),
    declares_protection=True,
)


class Session:
    """The shape `mamori.PrivacySession` presents: a result object, not text."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        # `mapping or {...}` here read an empty dict as "no mapping given" and
        # handed back the default, so the test for a restorer that puts nothing
        # back was quietly restoring. An empty mapping is a session for the
        # wrong scope, which is a case rather than an absence.
        self.mapping = {"<PERSON_001>": "田中太郎"} if mapping is None else mapping

    def restore(self, text: str) -> object:
        for token, value in self.mapping.items():
            text = text.replace(token, value)
        return type("RestorationResult", (), {"text": text})()


# --- Why the adapter is not zero lines ---------------------------------------


def test_a_session_passes_the_runtime_check_and_still_returns_the_wrong_thing() -> None:
    """The reason the port's docstring was believable, and wrong.

    `Restorer` is `runtime_checkable`, and `isinstance` against a `Protocol`
    checks that the method is **present** — not what it returns. So a session
    passes, the caller gets an object where it expected a string, and akashi
    runs a regex over it three layers away.
    """
    session = Session()
    assert isinstance(session, Restorer)
    assert not isinstance(session.restore("x"), str)


def test_without_the_adapter_the_failure_is_a_regex_error_far_from_the_seam() -> None:
    """What the message would have been. `TypeError: expected string or
    bytes-like object` says nothing about restorers, sessions or ADR-0008."""
    from akashi.domain.protection import find_placeholders

    with pytest.raises(TypeError, match="expected string"):
        find_placeholders(Session().restore("担当は <PERSON_001> です。"))  # type: ignore[arg-type]


# --- What it does ------------------------------------------------------------


def test_it_hands_back_the_text() -> None:
    restorer = MamoriRestorer(Session())
    assert restorer.restore("担当は <PERSON_001> です。") == "担当は 田中太郎 です。"


def test_it_satisfies_the_port_it_was_written_for() -> None:
    assert isinstance(MamoriRestorer(Session()), Restorer)
    assert isinstance(MamoriRestorer(Session()).restore("x"), str)


def test_something_that_is_not_a_session_is_refused_by_name() -> None:
    """Named at the seam rather than crashing later. A caller whose restorer
    already returns a string does not need this wrapper, and the message says
    so instead of only saying no."""

    class ReturnsAString:
        def restore(self, text: str) -> str:
            return text

    with pytest.raises(ContractError, match="no usable 'text'"):
        MamoriRestorer(ReturnsAString()).restore("x")


def test_a_placeholder_the_session_does_not_know_is_left_in_place() -> None:
    """`mamori`'s behaviour and what the port asks for. A restorer that
    silently dropped an unknown token would produce text that looks restored
    and is not, which is the one outcome worse than refusing."""
    restored = MamoriRestorer(Session()).restore("<PERSON_001> と <PERSON_009>。")
    assert "田中太郎" in restored
    assert "<PERSON_009>" in restored


# --- Through the pipeline ADR-0008 describes ---------------------------------


def test_a_pseudonymized_answer_is_restored_and_then_audited() -> None:
    """The whole point. Without the restorer this answer audits as fabricated
    in full; with it, the name grounds in the document it came from."""
    answer = "担当は <PERSON_001>、金額は 45,000 円でした。"
    report = audit(answer, PSEUDONYMIZED, DEFAULT, restorer=MamoriRestorer(Session()))

    grounded = [
        one.particular.text for segment in report.assessment.segments for one in segment.grounded
    ]
    assert "45,000 円" in grounded
    assert "田中太郎" in report.answer
    assert "<PERSON_001>" not in report.answer


def test_the_report_names_who_restored_it() -> None:
    """akashi watched this one happen, so it is not an assertion (ADR-0013).
    The distinction is on the report rather than in the caller's memory."""
    answer = "担当は <PERSON_001> です。"
    report = audit(answer, PSEUDONYMIZED, DEFAULT, restorer=MamoriRestorer(Session()))
    assert report.provenance.restored_by == "mamori@0.27.0"
    assert not report.provenance.restoration_asserted


def test_a_restorer_for_the_wrong_scope_is_still_refused() -> None:
    """The adapter does not weaken the check above it. A session holding no
    mapping returns its input unchanged, and auditing that would report every
    honest particular as floating."""
    from akashi.errors import ProtectedResponseError

    with pytest.raises(ProtectedResponseError, match="put nothing back"):
        admit("担当は <PERSON_001> です。", PSEUDONYMIZED, MamoriRestorer(Session({})))


# --- What the adapter is allowed to be ---------------------------------------


def test_the_adapter_imports_nothing() -> None:
    """The contract permits this package to name `mamori` and it does not need
    to. akashi installs and runs without the library; a caller who has a
    session hands it over.

    Checked structurally rather than by trying an import, because an import
    that happens to work in this environment proves nothing about a machine
    where the package is absent.
    """
    source = Path(__file__).parents[1] / "src" / "akashi" / "infrastructure" / "adapters"
    modules = sorted(source.glob("*.py"))
    assert modules, (
        f"no modules under {source} -- this test would pass having read nothing. "
        f"`for x in []: assert ...` is green, so the population is checked before "
        f"the loop rather than assumed by it. Has the adapters package moved?"
    )
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            assert "mamori" not in names, f"{module.name} imports mamori"
