"""The fixtures are documents `tsumugi` would actually produce.

akashi's reader is a second implementation of somebody else's contract
(ADR-0007), and a hand-written fixture plus a hand-written reader can agree
with each other and both be wrong. This is what stops that: every fixture is
validated against the schema `tsumugi` publishes, vendored under
`tests/contracts/`.

It is not the whole answer. A copy of a schema goes stale, and the thing that
will catch a real drift is the v0.5 seam test, which builds a package with the
reference producer rather than reading one somebody typed. This is the cheap
half, and it runs on every push.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

jsonschema = pytest.importorskip("jsonschema", reason="a dev dependency; see [dev] in pyproject")

ROOT = Path(__file__).parent
PACKAGES = ROOT / "packages"
SCHEMA = ROOT / "contracts" / "context-package-1.json"


def fixtures() -> list[Path]:
    found = sorted(PACKAGES.glob("*.json"))
    assert found, "no fixture packages; this test is measuring nothing"
    return found


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("package", fixtures(), ids=lambda p: p.name)
def test_every_fixture_conforms_to_the_published_contract(
    package: Path, schema: dict[str, Any]
) -> None:
    document = json.loads(package.read_text(encoding="utf-8"))
    jsonschema.validate(document, schema)


@pytest.mark.parametrize("package", fixtures(), ids=lambda p: p.name)
def test_every_anchor_agrees_with_the_length_of_its_own_text(package: Path) -> None:
    """The schema cannot express this and it is the invariant every reported
    offset rests on. An item whose anchor is the wrong length points a reader
    at text that was never sent."""
    document = json.loads(package.read_text(encoding="utf-8"))
    for item in document["items"]:
        anchor = item["anchor"]
        assert anchor["end"] - anchor["start"] == len(item["text"]), (
            f"{package.name}: {item['item_id']} holds {len(item['text'])} characters "
            f"but its anchor covers {anchor['end'] - anchor['start']}"
        )


@pytest.mark.parametrize("package", fixtures(), ids=lambda p: p.name)
def test_no_fixture_carries_an_omitted_span_as_text(package: Path) -> None:
    """ADR-0012, asserted against the fixtures so that a future one cannot
    quietly add the field the whole decision rests on not existing."""
    document = json.loads(package.read_text(encoding="utf-8"))
    for omission in document.get("omissions", []):
        assert "text" not in omission, (
            f"{package.name}: an omission carries text. The contract says it does not, "
            f"and ADR-0012 follows from that."
        )


def test_the_vendored_schema_is_the_contract_akashi_claims_to_read(
    schema: dict[str, Any],
) -> None:
    """A copy that has been swapped for a different contract would make every
    other test here vacuous."""
    assert "context-package" in schema["$id"]
    assert set(schema["required"]) >= {"contract", "items", "omissions", "provenance"}
