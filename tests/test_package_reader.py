"""Reading somebody else's contract, and refusing what it does not recognise.

ADR-0007. akashi imports `tsumugi` nowhere, so this reader is a second
implementation of a published contract and the two can drift. These tests are
the price of that: the fixtures are real documents, they are checked against
the published schema in `test_contract_conformance.py`, and everything the
reader refuses is refused on purpose and named.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from akashi.domain.anchor import Layer
from akashi.errors import AkashiError, ContractError
from akashi.infrastructure.packages import (
    ContextPackage,
    Protection,
    load_package,
    read_package,
)

PACKAGES = Path(__file__).parent / "packages"


def minimal(**changes: Any) -> dict[str, Any]:
    """The smallest thing the reader accepts, so a test can break one field."""
    package: dict[str, Any] = {
        "contract": "tsumugi.context-package/1",
        "items": [
            {
                "item_id": "itm_01",
                "text": "The tent weighs 2.4kg.",
                "anchor": {"document_id": "doc_01", "start": 0, "end": 22},
            }
        ],
        "omissions": [],
    }
    package.update(changes)
    return package


# --- The fixtures read ------------------------------------------------------


def test_a_japanese_package_reads() -> None:
    package = load_package(PACKAGES / "gear-ja.json")
    assert package.contract == "tsumugi.context-package/1"
    assert package.query == "テントの重量は?"
    assert [item.item_id for item in package.evidence.items] == ["itm_01", "itm_02", "itm_03"]
    assert package.evidence.items[0].anchor.source_path == "notes/2025-06-03-装備メモ.md"
    assert package.producer_version == "0.2.0"
    assert package.providers == ("filesystem", "kiseki@0.10.0")


def test_an_english_package_reads() -> None:
    package = load_package(PACKAGES / "contract-en.json")
    assert len(package.evidence) == 2
    assert package.evidence.items[1].anchor.section == "Liability"


def test_the_layer_survives_the_crossing() -> None:
    """``kiseki``'s distinction, read off a document. An interpretation that
    arrived as an interpretation must not become a fact by being parsed."""
    package = load_package(PACKAGES / "gear-ja.json")
    layers = [item.layer for item in package.evidence.items]
    assert layers == [Layer.FACT, Layer.FACT, Layer.INTERPRETATION]
    assert package.evidence.items[2].producer == "kiseki@0.10.0"


def test_the_omissions_are_read_as_receipts() -> None:
    """Counted and reported, never searched (ADR-0012)."""
    package = load_package(PACKAGES / "gear-ja.json")
    assert package.evidence.withheld_by_rule() == {
        "budget_exhausted": 1,
        "redundant_candidate": 1,
    }
    assert package.evidence.withheld[0].reason.startswith("ranked 7th")


def test_a_protected_package_says_who_protected_it() -> None:
    package = load_package(PACKAGES / "protected-ja.json")
    assert package.is_protected
    assert package.protection == Protection(by="mamori@0.17.0", scope="sess_2f11", reversible=True)
    assert package.declares_protection


def test_an_unprotected_package_says_so_rather_than_saying_nothing() -> None:
    """``null`` and absent are different: one is a package that told akashi it
    was not protected, the other is a package that told akashi nothing. ADR-0008
    refuses on the second."""
    package = load_package(PACKAGES / "gear-ja.json")
    assert not package.is_protected
    assert package.declares_protection

    silent = read_package(minimal())
    assert not silent.is_protected
    assert not silent.declares_protection


# --- The contract field ------------------------------------------------------


def test_the_frozen_contract_is_accepted() -> None:
    assert read_package(minimal()).contract == "tsumugi.context-package/1"


def test_the_pre_freeze_draft_is_accepted() -> None:
    """Packages written before the freeze carry it. Refusing evidence over a
    version string would be the wrong trade."""
    package = read_package(minimal(contract="tsumugi.context-package/1-draft"))
    assert package.contract == "tsumugi.context-package/1-draft"


@pytest.mark.parametrize(
    "contract",
    [
        "tsumugi.context-package/2",
        "tsumugi.context-package/0",
        "somebody.else/1",
        "tsumugi.context-package",
        "",
    ],
)
def test_an_unrecognised_contract_is_refused(contract: str) -> None:
    """Read first, refused rather than guessed at. Guessing at a version is how
    a consumer reads a field that changed meaning and reports the wrong thing
    with complete confidence."""
    with pytest.raises(ContractError):
        read_package(minimal(contract=contract))


def test_a_package_with_no_contract_is_refused() -> None:
    package = minimal()
    del package["contract"]
    with pytest.raises(ContractError, match="no readable 'contract'"):
        read_package(package)


def test_a_contract_that_is_not_a_string_is_refused() -> None:
    with pytest.raises(ContractError, match="no readable 'contract'"):
        read_package(minimal(contract=1))


# --- Fields akashi does not know ---------------------------------------------


def test_an_unfamiliar_field_is_read_past_rather_than_refused() -> None:
    """Unknown is not wrong. Refusing here would break akashi on any producer
    that is not tsumugi and on tsumugi's own version 2, and would throw away an
    audit it can perform in order to report a fact it can state."""
    package = minimal(something_new={"invented": True}, another=[1, 2, 3])
    assert len(read_package(package).evidence) == 1


def test_an_unfamiliar_field_is_written_down_rather_than_ignored() -> None:
    """Version 1 is **closed** -- ``additionalProperties: false`` everywhere,
    so an extension is indistinguishable from corruption, on purpose (tsumugi
    ADR-0022). This package does not conform, and reading it in silence is
    auditing a document whose reader is never told which document it was.

    akashi used to ignore these, on the strength of version 1's earlier promise
    that *"a field may be added"*. The promise was withdrawn; the copy in
    ``tests/contracts/`` going stale is what surfaced it.
    """
    package = minimal(something_new={"invented": True}, another=[1, 2, 3])
    assert read_package(package).unrecognised == ("something_new", "another")


def test_an_unfamiliar_field_inside_an_item_is_written_down_with_its_path() -> None:
    """The index is in the path. "somewhere in items" sends a reader through
    the whole list to find what akashi already knew."""
    package = minimal()
    package["items"][0]["invented_field"] = "whatever"
    read = read_package(package)
    assert len(read.evidence) == 1
    assert read.unrecognised == ("items[0].invented_field",)


def test_a_conforming_package_has_nothing_written_down() -> None:
    """The half that makes the check worth having. A list that is never empty
    is a list a reader learns to skip, and the fields akashi does not *use* --
    ``budget``, ``constraints``, ``output_schema`` -- are named by the contract
    and must not appear here."""
    package = minimal(
        budget={"limit": 1, "estimate": 1, "unit": "token", "estimator": "x"},
        constraints={},
        output_schema={},
        created_at="2026-09-01T00:00:00Z",
        instructions="",
    )
    assert read_package(package).unrecognised == ()


def test_an_unfamiliar_layer_is_refused() -> None:
    """A *value* akashi does not know, rather than a field. ``kiseki``'s three
    layers are a closed set, and treating a fourth as an ordinary fact is the
    laundering the distinction exists to stop."""
    package = minimal()
    package["items"][0]["provenance"] = {"layer": "speculation", "producer": "x"}
    with pytest.raises(ContractError, match="akashi does not know"):
        read_package(package)


def test_an_item_with_no_declared_layer_is_read_as_undeclared() -> None:
    assert read_package(minimal()).evidence.items[0].layer is None


# --- Fail closed on a malformed package --------------------------------------


def test_a_package_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(ContractError, match="a JSON object"):
        read_package([1, 2, 3])


def test_a_package_with_no_items_is_refused() -> None:
    package = minimal()
    del package["items"]
    with pytest.raises(ContractError, match="no 'items'"):
        read_package(package)


def test_items_that_are_not_a_list_are_refused() -> None:
    with pytest.raises(ContractError, match="not a list"):
        read_package(minimal(items={"itm_01": "text"}))


@pytest.mark.parametrize("field", ["item_id", "text", "anchor"])
def test_an_item_missing_a_required_field_is_refused(field: str) -> None:
    package = minimal()
    del package["items"][0][field]
    with pytest.raises(ContractError, match=f"items\\[0\\] has no '{field}'"):
        read_package(package)


@pytest.mark.parametrize("field", ["document_id", "start", "end"])
def test_an_anchor_missing_a_required_field_is_refused(field: str) -> None:
    package = minimal()
    del package["items"][0]["anchor"][field]
    with pytest.raises(ContractError, match="anchor has no"):
        read_package(package)


def test_an_anchor_that_ends_before_it_starts_is_refused() -> None:
    package = minimal()
    package["items"][0]["anchor"] = {"document_id": "doc_01", "start": 90, "end": 10}
    with pytest.raises(ContractError, match="before it starts"):
        read_package(package)


def test_an_anchor_that_disagrees_with_its_text_is_refused() -> None:
    """The reported offsets are only worth something if the item really covers
    the span it claims. A package that gets this wrong is refused rather than
    audited into offsets that point at the wrong text."""
    package = minimal()
    package["items"][0]["anchor"]["end"] = 5
    with pytest.raises(ContractError, match="not a usable evidence item"):
        read_package(package)


def test_a_negative_offset_is_refused() -> None:
    package = minimal()
    package["items"][0]["anchor"]["start"] = -1
    with pytest.raises(ContractError, match="not an offset"):
        read_package(package)


def test_a_boolean_offset_is_refused() -> None:
    """``True`` is an ``int`` in Python and would otherwise read as offset 1."""
    package = minimal()
    package["items"][0]["anchor"]["start"] = True
    with pytest.raises(ContractError, match="not an offset"):
        read_package(package)


def test_two_items_sharing_an_id_are_refused() -> None:
    package = minimal()
    package["items"].append(dict(package["items"][0]))
    with pytest.raises(ContractError, match="not a usable evidence set"):
        read_package(package)


def test_an_omission_with_no_reason_is_refused() -> None:
    package = minimal(omissions=[{"rule": "budget_exhausted"}])
    with pytest.raises(ContractError, match="omissions\\[0\\] has no 'reason'"):
        read_package(package)


def test_omissions_that_are_not_a_list_are_refused() -> None:
    with pytest.raises(ContractError, match="'omissions' that is not a list"):
        read_package(minimal(omissions="none"))


def test_an_omission_without_an_anchor_is_still_read() -> None:
    """The contract requires one, and a receipt with a rule and a reason is
    still a usable receipt. akashi never searches these, so a missing anchor
    costs it nothing (ADR-0012)."""
    package = minimal(omissions=[{"rule": "truncated_by_cap", "reason": "top 200 only"}])
    read = read_package(package)
    assert read.evidence.withheld[0].anchor is None
    assert read.evidence.withheld_by_rule() == {"truncated_by_cap": 1}


def test_a_protection_that_is_neither_null_nor_an_object_is_refused() -> None:
    package = minimal(provenance={"protection": "yes"})
    with pytest.raises(ContractError, match="neither null nor an object"):
        read_package(package)


# --- A protection block is read as strictly as the contract writes it --------
#
# The contract requires ``by``, ``scope`` and ``reversible``, the first two with
# ``minLength: 1``. The reader used to take ``scope`` as optional and
# ``reversible`` through ``bool()``, so a malformed block was audited as
# "irreversible, scope unstated". That is the safe direction and it was still
# wrong: it was reached by accident, and ADR-0008 turns on ``reversible``.


WHOLE = {"by": "mamori@0.17.0", "scope": "sess_2f11", "reversible": True}


@pytest.mark.parametrize("missing", ["by", "scope", "reversible"])
def test_a_protection_block_missing_any_field_is_refused(missing: str) -> None:
    block = {key: value for key, value in WHOLE.items() if key != missing}
    with pytest.raises(ContractError, match=f"has no '{missing}'"):
        read_package(minimal(provenance={"protection": block}))


@pytest.mark.parametrize("blank", ["by", "scope"])
def test_a_protection_field_the_contract_requires_content_in_may_not_be_empty(
    blank: str,
) -> None:
    """``minLength: 1``. A producer that sends ``""`` has said nothing while
    appearing to have answered, and ``scope`` is what a reader would use to
    decide which part of the package the redaction touched."""
    with pytest.raises(ContractError, match=f"has an empty '{blank}'"):
        read_package(minimal(provenance={"protection": {**WHOLE, blank: ""}}))


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None, []])
def test_reversible_must_be_a_boolean_and_is_not_coerced(value: object) -> None:
    """The reason this is not ``bool(raw.get("reversible"))``.

    That reads the string ``"false"`` as ``True`` — a package nobody can
    restore, audited as though it could be. Every value here is refused rather
    than interpreted, including the ones that would have come out right.
    """
    with pytest.raises(ContractError, match="'reversible' that is not a boolean"):
        read_package(minimal(provenance={"protection": {**WHOLE, "reversible": value}}))


def test_a_whole_protection_block_still_reads() -> None:
    read = read_package(minimal(provenance={"protection": WHOLE}))
    assert read.protection == Protection(**WHOLE)  # type: ignore[arg-type]
    assert read.declares_protection


def test_null_and_absent_are_still_different_after_the_tightening() -> None:
    """``declares_protection`` does the same job it always did. A malformed
    block is now a third thing: refused outright, rather than joining either
    of the two the contract distinguishes."""
    declared = read_package(minimal(provenance={"protection": None}))
    assert declared.protection is None
    assert declared.declares_protection

    silent = read_package(minimal(provenance={}))
    assert silent.protection is None
    assert not silent.declares_protection


# --- Loading from a file -----------------------------------------------------


def test_a_missing_file_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="cannot read the package"):
        load_package(tmp_path / "nothing.json")


def test_a_file_that_is_not_json_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="is not JSON"):
        load_package(broken)


def test_a_file_is_read_as_utf8_whatever_the_platform_thinks(tmp_path: Path) -> None:
    """Half of what akashi audits is CJK, and a package read with the wrong
    encoding audits as fabricated in full."""
    written = tmp_path / "ja.json"
    written.write_text(
        json.dumps(minimal(query="テントの重量は?"), ensure_ascii=False), encoding="utf-8"
    )
    assert load_package(written).query == "テントの重量は?"


def test_a_path_may_be_a_string() -> None:
    assert load_package(str(PACKAGES / "gear-ja.json")).query == "テントの重量は?"


# --- What akashi deliberately does not read ----------------------------------


def test_the_reader_keeps_nothing_it_has_no_use_for() -> None:
    """A reader that parsed the budget and the selection scores would be a
    second place for the contract to drift, for no gain: akashi audits an
    answer against the text that was sent and has no opinion about how it was
    chosen."""
    fields = set(ContextPackage.__dataclass_fields__)
    assert "budget" not in fields
    assert "instructions" not in fields
    assert "selection" not in fields


def test_every_refusal_is_an_akashi_error() -> None:
    """A caller catches one type. A reader that let a ``KeyError`` escape would
    make a malformed package look like a bug in akashi."""
    assert issubclass(ContractError, AkashiError)
    with pytest.raises(AkashiError):
        read_package({"contract": "nonsense/9"})
