"""`akashi doctor` — facts about a machine, not a verdict about akashi.

Two of the defects this project shipped were invisible in development and
obvious on the machine that had them: prose that crashed a `cp932` console, and
a `--json` that wrote `cp932` bytes into a document contract that requires
UTF-8. Neither could be found by reading a declaration, and no amount of CI on
UTF-8 runners produces a machine that can fail that way.

`doctor` is the command that reports the machine. So the tests below are mostly
about two things: that it says what it found rather than what it assumes, and
that running it costs the machine nothing.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from akashi.infrastructure.installation import SIBLINGS, Finding, Installation, inspect
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.rendering import as_diagnosis
from akashi.interfaces.cli.main import AUDITED, REFUSED, main


def looked() -> Installation:
    return inspect(DEFAULT)


# --- what it found -----------------------------------------------------------


def test_it_finds_the_contract_akashi_promises_to_ship() -> None:
    """#57's payoff. The schema is inside the package tree, so one route --
    the one `docs/audit-report.md` sends a consumer down -- resolves here, in
    an editable install, and in a wheel."""
    contract = looked().contract
    assert contract.ok
    assert "audit-report-1" in contract.detail
    assert "sha256:" in contract.detail


def test_the_hash_it_prints_is_the_hash_of_the_file_it_shipped() -> None:
    """A digest nobody can reproduce is decoration. This is the check a
    consumer runs when they want to know whether the contract they validated
    against is the contract this installation has."""
    import hashlib
    from importlib.resources import files

    shipped = files("akashi") / "schemas" / "audit-report-1.json"
    digest = hashlib.sha256(shipped.read_bytes()).hexdigest()
    assert digest in looked().contract.detail


def test_it_names_the_language_packs_that_are_loaded() -> None:
    """Every count on a report has the pack set in its denominator (ADR-0009),
    so *which packs* is the first question about a report somebody cannot
    reproduce."""
    printed = as_diagnosis(looked())
    for code in ("und", "en", "ja", "zh"):
        assert f"  {code}  " in printed


def test_it_reports_the_console_rather_than_assuming_one() -> None:
    printed = as_diagnosis(looked())
    assert "This console" in printed
    assert str(sys.stdout.encoding or "unknown") in printed or "unknown" in printed


def test_a_narrow_console_gets_told_what_that_means_for_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The note that would have saved both encoding defects. It says the two
    halves separately, because they behave differently: prose degrades, a
    document does not."""
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp932"))
    notes = " ".join(looked().notes)
    assert "cp932" in notes
    assert "UTF-8 bytes" in notes


def test_a_utf8_console_is_not_lectured(monkeypatch: pytest.MonkeyPatch) -> None:
    """A note that appears on every machine is a note nobody reads on the
    machine it was written for."""
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="utf-8"))
    assert not [note for note in looked().notes if "console" in note]


# --- what it refuses to do ---------------------------------------------------


def test_it_does_not_import_a_sibling_to_report_on_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A diagnostic that imported five libraries in order to describe them
    would be running somebody else's code on a machine its user is already
    suspicious of. `find_spec` answers the question and runs none of it.
    """
    import builtins
    from typing import Any

    imported: list[str] = []
    real = builtins.__import__

    def watch(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".")[0] in SIBLINGS:
            imported.append(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", watch)
    inspect(DEFAULT)
    assert imported == []


def test_a_missing_sibling_is_not_a_fault() -> None:
    """akashi installs and runs without every one of them (ADR-0001), and the
    adapter that talks to `mamori` imports nothing. Reporting absence as a
    problem would teach a reader to install things akashi does not need."""
    installation = looked()
    assert {one.what for one in installation.siblings} == set(SIBLINGS)
    assert not any(one.what in SIBLINGS for one in installation.missing)
    assert "None of these is required" in as_diagnosis(installation)


def test_it_decides_nothing_about_whether_akashi_is_correct() -> None:
    printed = as_diagnosis(looked())
    assert "That akashi is correct. This is what is present, not what it computes." in printed
    assert "healthy" not in printed.lower()
    assert " ok\n" not in printed.lower()


# --- when something really is missing ----------------------------------------


def test_a_missing_contract_is_named_first_and_exits_nonzero() -> None:
    """A `doctor` that printed twenty sound lines and the broken one at the
    bottom would depend on somebody reading to the end, which is the one thing
    a person chasing a bug does not do."""
    broken = Installation(
        akashi_version="0.1.0.dev0",
        python_version="3.12.8",
        platform="win32",
        location="/somewhere",
        console_encoding="utf-8",
        stdout_errors="strict",
        contract=Finding(
            "contract",
            "schemas/audit-report-1.json is not in the installed package (FileNotFoundError).",
            ok=False,
        ),
    )
    printed = as_diagnosis(broken)
    assert printed.index("Missing") < printed.index("Installation")
    assert broken.missing


def test_the_command_exits_nonzero_when_something_promised_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A diagnostic that returns success whatever it found is a diagnostic no
    script can use, and this one is going to be run by people pasting its
    output into an issue."""
    from akashi.infrastructure import installation as module

    monkeypatch.setattr(module, "_contract", lambda: Finding("contract", "not here", ok=False))
    assert main(["doctor"]) == REFUSED


def test_a_sound_installation_exits_zero() -> None:
    assert main(["doctor"]) == AUDITED


# --- the command itself ------------------------------------------------------


def test_its_own_prose_is_ascii() -> None:
    """The one command most likely to be run *because* the console is the
    problem. It cannot be the command that crashes on it."""
    printed = as_diagnosis(looked())
    printed.encode("ascii")


def test_it_prints_on_a_japanese_console_even_when_the_path_is_not_ascii(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """akashi's own words are ASCII; the install path is not akashi's word.
    On a machine whose user name is Japanese, that path is what would crash a
    command written on the assumption that only prose is printed."""
    from akashi.infrastructure import installation as module

    monkeypatch.setattr(module, "_location", lambda: "C:/ユーザー/route/akashi")
    as_diagnosis(looked()).encode("cp932")


def test_the_report_it_produces_is_not_a_report(tmp_path: Path) -> None:
    """`doctor` is prose for a person. It is not a document, has no contract,
    and nothing should grow one for it by accident -- the moment it emits JSON
    somebody will parse it, and akashi will owe them stability it never
    promised."""
    printed = as_diagnosis(looked())
    with pytest.raises(json.JSONDecodeError):
        json.loads(printed)
