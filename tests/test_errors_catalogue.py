"""The catalogue of refusals, and the guard that keeps it honest (Sora R-E1).

An orchestrator talking to seven libraries is the only place that can answer
*"is something broken, or did I do this?"*, and it answers it by folding
failures together -- which needs a stable **name**, not a sentence. A sentence
may quote what it was given; a name cannot, which is what lets a record of
failures say it holds no values.

Sora asked for the same shape of check it saw work on `report_id`: **the
catalogue and the kinds akashi can actually raise must agree, in both
directions.** A catalogue listing a kind nothing raises teaches a consumer to
handle a case that cannot happen; a raise site with a kind nobody catalogued is
a failure their screen cannot name. Both are silent.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from akashi.errors import (
    CATALOGUE,
    CONTRACT,
    OPEN_NAMESPACES,
    AkashiError,
    ContractError,
    ProtectedResponseError,
    SegmentationError,
    catalogue,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "akashi"

#: Any producer string; the tests below are about shape, not about a version.
BY = "akashi/0.0.0-test"

#: The kinds a raise site gets without asking, one per exception class.
DEFAULTS = {
    cls.default_kind
    for cls in (AkashiError, ContractError, ProtectedResponseError, SegmentationError)
}


def raisable() -> set[str]:
    """Every kind that some `raise` in the package can produce.

    Read out of the source rather than by importing and provoking each one:
    provoking them needs a hundred fixtures, and a fixture that stops matching
    its raise site fails silently in the direction that matters. What the file
    says is what ships.
    """
    found: set[str] = set()
    for module in sorted(SRC.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            name = node.exc.func
            base = name.id if isinstance(name, ast.Name) else getattr(name, "attr", "")
            if not base.endswith("Error") or base not in {
                "AkashiError",
                "ContractError",
                "ProtectedResponseError",
                "SegmentationError",
            }:
                continue
            explicit = next(
                (
                    keyword.value.value
                    for keyword in node.exc.keywords
                    if keyword.arg == "kind" and isinstance(keyword.value, ast.Constant)
                ),
                None,
            )
            if explicit is not None:
                found.add(str(explicit))
            else:
                found.add({"ProtectedResponseError": "ProtectedResponse"}.get(base, base))
    return found


# --- the two directions Sora asked for ---------------------------------------


def test_every_kind_in_the_catalogue_is_one_something_can_raise() -> None:
    """A catalogue entry nothing raises teaches a consumer to handle a case
    that cannot happen, and they find out by never seeing it."""
    catalogued = {entry.kind for entry in CATALOGUE}
    unreachable = catalogued - raisable()
    assert not unreachable, f"catalogued but never raised: {sorted(unreachable)}"


def test_every_kind_something_can_raise_is_in_the_catalogue() -> None:
    """The other direction, and the one that decays: a raise site added with a
    new `kind=` and no catalogue entry is a failure a consumer's screen cannot
    name, and nothing else would say so."""
    catalogued = {entry.kind for entry in CATALOGUE}
    uncatalogued = raisable() - catalogued
    assert not uncatalogued, f"raised but not catalogued: {sorted(uncatalogued)}"


def test_the_scan_is_reading_something() -> None:
    """Both tests above pass on an empty set. akashi raises a hundred-odd
    times, so a scan that found nothing found the wrong thing."""
    found = raisable()
    assert len(found) >= 4, f"the scan found only {sorted(found)}"
    assert found | {"ProtectedResponse"} >= DEFAULTS or "ContractError" in found


# --- a kind is a name, and a name carries no values ---------------------------


def test_a_raise_site_that_says_nothing_is_still_named() -> None:
    """What makes the set closed by construction rather than by anybody
    remembering: the default is the class name, which is already catalogued."""
    assert ContractError("anything").kind == "ContractError"
    assert ProtectedResponseError("anything").kind == "ProtectedResponse"
    assert AkashiError("anything").kind == "AkashiError"


def test_a_kind_never_carries_what_it_was_given() -> None:
    """The property that lets a consumer's incident log say it holds no values.
    A kind is chosen from a closed set at the raise site; the sentence beside
    it may quote an input, and the kind may not."""
    raised = ContractError("the file /home/someone/private.db is malformed", kind="ContractError")
    assert "private.db" in str(raised)
    assert "private.db" not in raised.kind


@pytest.mark.parametrize("entry", CATALOGUE, ids=lambda entry: entry.kind)
def test_no_entry_carries_a_value_or_a_hole_to_put_one_in(entry: Any) -> None:
    """Sora asked for this explicitly: no paths, no templates. A reader who
    finds `{}` in a catalogue fills it from a log, and then the catalogue has
    taught somebody to write down the thing it exists to keep out."""
    for sentence in (entry.detail, entry.detail_ja):
        assert "{" not in sentence and "}" not in sentence
        assert "/home" not in sentence and "C:\\" not in sentence
        assert not sentence.startswith(" ") and sentence.strip() == sentence


@pytest.mark.parametrize("entry", CATALOGUE, ids=lambda entry: entry.kind)
def test_both_sentences_are_written_and_are_not_the_same_one(entry: Any) -> None:
    """Sora's reasoning, adopted: two sentences written by the same hand cannot
    disagree, so akashi writes the Japanese rather than leaving a consumer to
    invent it. An empty one, or the English copied across, would hand the
    invention back."""
    assert entry.detail.strip()
    assert entry.detail_ja.strip()
    assert entry.detail_ja != entry.detail
    assert any(ord(character) > 0x3000 for character in entry.detail_ja)


# --- the shape of the document ------------------------------------------------


def test_the_document_declares_a_draft_contract() -> None:
    body = catalogue(by=BY)
    assert body["contract"] == CONTRACT
    assert CONTRACT.endswith("-draft"), "the field set can still move; say so in the name"


def test_the_document_is_plain_data() -> None:
    json.dumps(catalogue(by=BY), ensure_ascii=False)


def test_every_entry_carries_every_field_a_consumer_folds_on() -> None:
    for entry in catalogue(by=BY)["errors"]:
        assert set(entry) == {"kind", "status", "outcome", "retryable", "detail", "detail_ja"}
        assert entry["outcome"] in {"refused", "unavailable", "failed", "timed_out"}
        assert isinstance(entry["retryable"], bool)


def test_open_namespaces_is_empty_and_that_is_a_fact() -> None:
    """akashi builds no kind out of another project's vocabulary. It reads
    mamori's and tsumugi's contracts, and a document of either shape that it
    refuses is refused under akashi's name -- what failed is akashi's reading,
    not their writing."""
    assert catalogue(by=BY)["open_namespaces"] == []
    assert OPEN_NAMESPACES == ()


def test_almost_nothing_is_retryable_and_the_exceptions_reach_a_network() -> None:
    """The field only akashi can answer, and Sora was guessing it from
    `outcome`. The same inputs give the same report forever (ADR-0003), so a
    refusal that became an acceptance on a second identical call would mean the
    audit was not deterministic. Only what reaches a model can differ."""
    retryable = {entry.kind for entry in CATALOGUE if entry.retryable}
    assert retryable == {"JudgeRefused"}, retryable


# --- the three Sora named, reached through the real code ----------------------


def test_a_surrogate_record_refuses_under_its_own_name() -> None:
    """Sora's screen can now say "a record containing surrogates cannot be
    audited" instead of "the audit was refused", which is a different sentence
    for the person who owns the document."""
    from akashi.infrastructure.packages import read_protection_scope

    record = {
        "contract": "mamori.protection-scope/1+surrogate",
        "by": "mamori/0.31.0",
        "scope": "session-abc123def456",
        "reversible": False,
        "mode": "surrogate",
        "placeholders": [],
        "protected": [{"kind": "PERSON", "count": 1}],
        "masked": [],
    }
    with pytest.raises(ContractError) as raised:
        read_protection_scope(record)
    assert raised.value.kind == "SurrogateRecord"


def test_a_pre_split_record_refuses_under_the_same_name() -> None:
    """Same kind, because it is the same thing to do about it: the text carries
    values akashi cannot tell from real ones."""
    from akashi.infrastructure.packages import read_protection_scope

    record = {
        "contract": "mamori.protection-scope/1",
        "by": "mamori/0.31.0",
        "scope": "session-abc123def456",
        "reversible": False,
        "mode": "placeholder",
        "placeholders": [],
        "protected": [{"kind": "PERSON", "count": 2}],
        "masked": [],
    }
    with pytest.raises(ContractError) as raised:
        read_protection_scope(record)
    assert raised.value.kind == "SurrogateRecord"


def test_a_package_and_a_record_that_disagree_refuse_under_their_own_name() -> None:
    import dataclasses

    from akashi.application.admit import effective_protection
    from akashi.domain.package import Protection
    from akashi.infrastructure.packages.plain import package_from_contexts

    package = dataclasses.replace(
        package_from_contexts(["x"]),
        protection=Protection(by="mamori/0.30.0", scope="session-other", reversible=True),
        declares_protection=True,
    )
    other = Protection(by="mamori/0.31.0", scope="session-abc123def456", reversible=False)
    with pytest.raises(ProtectedResponseError) as raised:
        effective_protection(package, other)
    assert raised.value.kind == "ProtectionMismatch"


# --- the command line ----------------------------------------------------------


def test_the_command_prints_the_document_and_exits_zero(tmp_path: Path) -> None:
    """Printing what akashi can refuse is not itself a refusal, and a consumer
    comparing it against their copy in CI needs a zero."""
    import contextlib

    from akashi.interfaces.cli.main import AUDITED, main

    out = tmp_path / "errors.json"
    with out.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
        code = main(["errors", "--json"])
    assert code == AUDITED
    from akashi import __version__

    body = json.loads(out.read_text(encoding="utf-8"))
    assert body == catalogue(by=f"akashi/{__version__}")


def test_the_table_names_every_kind_for_a_person(tmp_path: Path) -> None:
    import contextlib

    from akashi.interfaces.cli.main import AUDITED, main

    out = tmp_path / "errors.txt"
    with out.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
        assert main(["errors"]) == AUDITED
    printed = out.read_text(encoding="utf-8")
    for entry in CATALOGUE:
        assert entry.kind in printed


def test_a_broken_tiling_is_a_refusal_and_not_a_traceback() -> None:
    """What the catalogue guard found: `SegmentationError` was exported,
    documented against ADR-0009, and raised by nothing.

    The domain raises a built-in and deliberately -- `domain` imports nothing,
    not even `errors`, which is what keeps ADR-0001's set genuinely empty. So
    the class cannot be raised where the invariant lives, and for a long time
    it was raised nowhere else either. A broken tiling left the command line as
    a traceback, which reads as a bug in the tool rather than as a refusal.

    `application` is the layer that may name it and where the audit stops.
    """
    from unittest.mock import patch

    # The function, not the package attribute: `akashi.application` re-exports
    # `audit` as a name bound to the function, so `application.audit.audit`
    # does not exist.
    from akashi.application.audit import audit as run_audit
    from akashi.infrastructure.languages import DEFAULT
    from akashi.infrastructure.packages.plain import package_from_contexts

    # Patched where `audit` resolves it -- the module binds the name at import,
    # so replacing it in `domain.segment` would intercept nothing. The same
    # mistake `tests/test_performance.py` records making.
    with (
        patch(
            "akashi.application.audit.segment_answer",
            side_effect=ValueError("seg_001 runs past the end"),
        ),
        pytest.raises(SegmentationError) as raised,
    ):
        run_audit("x", package_from_contexts(["y"]), DEFAULT)

    assert raised.value.kind == "SegmentationError"
    assert isinstance(raised.value, AkashiError), "the CLI's refusal handler must see it"
    assert isinstance(raised.value, ValueError), "anything written against the old type still works"
    assert "runs past the end" in str(raised.value)


def test_the_document_says_which_akashi_wrote_it() -> None:
    """Sora's R-E1 example carried `by` and the first implementation did not.

    A consumer comparing their pinned copy against this one in CI is comparing
    against a *version*; a document that does not name it makes the difference
    real and unattributable. Same shape and same reasoning as
    `mamori.protection-scope/1`: the version says which rules were in force.
    """
    assert catalogue(by=BY)["by"] == BY


def test_a_catalogue_with_no_producer_is_refused_rather_than_published() -> None:
    """Required rather than defaulted. A default is a document somebody
    eventually publishes unlabelled, and `errors` imports nothing -- not even
    the version -- so the caller is the only one who can say."""
    import inspect

    # The signature, not just the empty string. A poison that gave `by` a
    # default left every test here green -- because none of them called
    # `catalogue()` with no argument, which is exactly the call a default
    # exists to permit.
    parameter = inspect.signature(catalogue).parameters["by"]
    assert parameter.default is inspect.Parameter.empty, "a default is an unlabelled document"

    with pytest.raises(ValueError, match="no producer"):
        catalogue(by="")


def test_the_command_line_stamps_the_running_version() -> None:
    import contextlib
    import io

    from akashi import __version__
    from akashi.interfaces.cli.main import main

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        main(["errors", "--json"])
    assert json.loads(captured.getvalue())["by"] == f"akashi/{__version__}"


def test_the_producer_matches_the_shape_the_family_uses() -> None:
    """`name/version`, which is what mamori's contract requires of the same
    field -- so a consumer reading several catalogues parses one shape."""
    import re

    from akashi import __version__
    from akashi.interfaces.cli.main import main  # noqa: F401

    assert re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._+-]+", f"akashi/{__version__}")
