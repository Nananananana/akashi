"""A copy of somebody else's contract, and the two ways it goes wrong.

`tests/contracts/` holds schemas published by other projects. akashi imports
none of them ([ADR-0007](../docs/adr/0007-read-the-producer-through-its-contract.md)):
the reader checks the contract field in plain Python, and these copies exist for
the other direction — proving that the fixtures akashi tests against are
documents the producer would actually emit.

A vendored copy fails in two different ways and they need different checks.

**It can be edited here.** Someone loosens a `required` to make a fixture pass,
and akashi is now conformant to a contract nobody published. This is caught
offline, on every run, by `tests/contracts/upstream.json` carrying the sha256 of
what was actually vendored.

**It can go stale there.** The producer tightens the schema and the copy does
not move. Nothing local can see this, so the check has to ask upstream — which
means the network, which means it is not a check that can run on every machine.
It is marked `network`, deselected by default, and run by its own CI job.

The `no-network` import contract covers `source_modules = akashi`. Tests are not
part of that package (they are not a package at all), so `urllib` here breaks
nothing — but the reason akashi refuses the network is that an audit must run
inside networks that cannot reach out, and that argument is about the library.
A test that fetches is a test, and it says so in its marker.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

CONTRACTS = Path(__file__).parent / "contracts"
UPSTREAM = CONTRACTS / "upstream.json"


def vendored() -> list[dict[str, Any]]:
    body = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    return list(body["vendored"])


def digest(raw: bytes) -> str:
    """By content, not by line ending.

    A Windows checkout can rewrite `\\r\\n` and the schema would be a different
    file byte for byte while saying exactly the same thing. Normalising means
    the recorded hash is a statement about the contract rather than about
    somebody's git configuration.
    """
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def ids(entries: list[dict[str, Any]]) -> list[str]:
    return [str(entry["file"]) for entry in entries]


def is_drift(status: int) -> bool:
    """Whether an HTTP status means the record is wrong rather than the day is.

    The distinction that matters. A 404 is a *response*: the server answered,
    and what it said is that the path this record sends a refresher to does not
    exist. That is drift of the most consequential kind -- the producer
    reorganised -- and treating it as an outage is how it goes unnoticed until
    somebody happens to look.

    Everything else the server can say is about the server. Skipping on those is
    correct; a rate limit is not evidence about a contract.
    """
    return status in (404, 410)


# --- What can be checked without asking anybody ------------------------------


def test_every_vendored_file_is_accounted_for() -> None:
    """A schema dropped into this directory without provenance is a copy nobody
    can refresh, and the licence it arrived under is unrecorded."""
    present = {path.name for path in CONTRACTS.glob("*.json")} - {UPSTREAM.name}
    assert present == {str(entry["file"]) for entry in vendored()}, (
        "tests/contracts/upstream.json does not describe what is in tests/contracts/"
    )


@pytest.mark.parametrize("entry", vendored(), ids=ids(vendored()))
def test_the_copy_is_the_thing_that_was_vendored(entry: dict[str, Any]) -> None:
    """Catches an edit here, which is the failure mode that matters most.

    Loosening a `required` in a local copy to make a fixture pass would leave
    akashi conformant to a contract nobody published, and every conformance
    test in this repository green while saying nothing.
    """
    local = CONTRACTS / str(entry["file"])
    assert digest(local.read_bytes()) == entry["sha256"], (
        f"{entry['file']} has been edited since it was vendored from "
        f"{entry['repo']}@{entry['commit'][:7]}. Vendored contracts are copies, "
        f"not forks: change it upstream, then refresh."
    )


@pytest.mark.parametrize("entry", vendored(), ids=ids(vendored()))
def test_the_provenance_is_complete_enough_to_refresh_from(entry: dict[str, Any]) -> None:
    for field in ("file", "repo", "path", "branch", "commit", "sha256", "retrieved", "licence"):
        assert entry.get(field), f"{entry.get('file')} has no {field!r}"
    assert len(str(entry["commit"])) == 40, "pin a full commit sha, not an abbreviation"
    assert len(str(entry["sha256"])) == 64


def test_the_vendored_schema_is_the_one_the_fixtures_are_checked_against() -> None:
    """Ties this file to the thing it protects. If the conformance tests stopped
    reading the vendored copy, these checks would be guarding a file nobody
    uses."""
    conformance = (Path(__file__).parent / "test_contract_conformance.py").read_text(
        encoding="utf-8"
    )
    assert "contracts" in conformance
    assert "context-package-1.json" in conformance


@pytest.mark.parametrize(
    ("status", "drift"),
    [(404, True), (410, True), (500, False), (429, False), (503, False)],
)
def test_a_moved_file_is_drift_and_a_bad_day_is_not(status: int, drift: bool) -> None:
    """Written after the networked check *skipped* on the exact thing it exists
    to catch.

    ``tsumugi`` moved its schema into its package tree. The content did not
    change by a byte, so the offline hash stayed green -- and the networked
    check caught ``HTTPError`` under ``URLError``, which it is a subclass of,
    and reported "cannot reach". The producer had reorganised and akashi would
    have said nothing.

    This is the classification on its own, so that it can be checked without a
    network and without waiting for a producer to move something again.
    """
    assert is_drift(status) is drift


# --- What can only be checked by asking upstream -----------------------------


@pytest.mark.network
@pytest.mark.parametrize("entry", vendored(), ids=ids(vendored()))
def test_the_copy_has_not_gone_stale_upstream(entry: dict[str, Any]) -> None:
    """Fetches the producer's current schema and compares it to what is recorded.

    Failing means upstream moved, which is information rather than a defect in
    whatever change is being reviewed. That is why this runs in its own job and
    on a schedule instead of gating every pull request: a contract that
    legitimately changed would otherwise block work that has nothing to do with
    it, and a check that blocks unrelated work gets disabled.
    """
    from urllib.error import HTTPError, URLError
    from urllib.request import urlopen

    url = f"https://raw.githubusercontent.com/{entry['repo']}/{entry['branch']}/{entry['path']}"
    try:
        with urlopen(url, timeout=30) as response:
            current = response.read()
    except HTTPError as error:
        # A response, not a failure to get one. **404 is a drift, not an
        # outage:** the recorded path is where a refresher would look, and it
        # is not there any more. Skipping here is how a schema that moved
        # upstream goes unnoticed for as long as nobody happens to read it --
        # which is the whole thing this test exists to prevent, and is exactly
        # what happened the first time a producer reorganised its repository.
        if is_drift(error.code):
            pytest.fail(
                f"{entry['file']} is no longer at {entry['path']} in {entry['repo']} "
                f"(HTTP {error.code}). Find where it moved to, check the content is "
                f"still what was vendored, and update 'path' and 'commit' in "
                f"tests/contracts/upstream.json."
            )
        pytest.skip(f"{url} answered {error.code}; upstream trouble rather than drift")
    except (URLError, TimeoutError) as error:
        pytest.skip(f"cannot reach {url}: {error}")

    assert digest(current) == entry["sha256"], (
        f"{entry['file']} has changed in {entry['repo']} since it was vendored at "
        f"{entry['commit'][:7]} on {entry['retrieved']}.\n"
        f"Refresh the copy, update sha256 and commit in tests/contracts/upstream.json, "
        f"and read the diff before assuming akashi still conforms."
    )


def test_the_transcribed_field_names_still_match_the_contract() -> None:
    """`CONTRACT_FIELDS` is a hand transcription, and this is what keeps it one.

    akashi reports a field the contract does not list, which means it holds a
    list of the fields the contract *does*. Loading it from the vendored copy at
    runtime would make test material a runtime dependency (ADR-0007), so it is
    typed out -- and a transcription nothing compares is a second contract that
    drifts from the first in silence.

    The failure this catches is the expensive direction: a field tsumugi adds
    and akashi has not transcribed is reported to every reader as a field the
    contract does not list, on a package that conforms perfectly.
    """
    from akashi.infrastructure.packages.contextpackage import CONTRACT_FIELDS

    schema = json.loads((CONTRACTS / "context-package-1.json").read_text(encoding="utf-8"))
    defs = schema["$defs"]
    transcribed = {
        "": set(schema["properties"]),
        "items": set(defs["item"]["properties"]),
        "omissions": set(defs["omission"]["properties"]),
        "provenance": set(defs["provenance"]["properties"]),
    }
    assert {where: set(names) for where, names in CONTRACT_FIELDS.items()} == transcribed


def test_every_object_the_transcription_covers_is_closed() -> None:
    """The premise, checked rather than assumed.

    Reporting an unlisted field as non-conformance is only right while the
    contract refuses one. An object that allowed extras would make akashi's
    report say a conforming package does not conform.
    """
    schema = json.loads((CONTRACTS / "context-package-1.json").read_text(encoding="utf-8"))
    for name, node in [("<root>", schema), *schema["$defs"].items()]:
        if "properties" in node:
            assert node.get("additionalProperties") is False, f"{name} accepts extra fields"
