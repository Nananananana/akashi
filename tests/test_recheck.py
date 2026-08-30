"""Re-deriving a report from the inputs it names.

The command the whole design is for. A record nobody can re-derive is a record
on trust, and what is checked here is mostly the refusals: a recheck against
the wrong file would produce a mismatch, and that mismatch would be a **true
statement that misleads**.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from akashi import __version__
from akashi.application import audit, recheck
from akashi.errors import ContractError
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.reports import load_report, read_report
from akashi.interfaces.cli.main import AUDITED, DIFFERED, REFUSED, main

PACKAGES = Path(__file__).parent / "packages"
ANSWERS = Path(__file__).parent / "answers"
ANSWER = (ANSWERS / "gear-ja.txt").read_text(encoding="utf-8")


def report_of(answer: str = ANSWER, package: str = "gear-ja") -> dict[str, Any]:
    return audit(
        answer, load_package(PACKAGES / f"{package}.json"), DEFAULT, akashi_version=__version__
    ).to_dict()


# --- The happy path ----------------------------------------------------------


def test_a_report_re_derives_identically() -> None:
    archived = report_of()
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert result.matches
    assert result.archived_id == result.rederived_id
    assert result.differences == ()
    assert "re-derived identically" in result.describe()


def test_it_re_derives_a_report_it_did_not_produce(tmp_path: Path) -> None:
    """A third party holding the report and the inputs can check it, which is
    the property the whole design is for."""
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report_of(), ensure_ascii=False), encoding="utf-8")
    archived = load_report(path)
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert result.matches


# --- The refusals, which come before the work --------------------------------


def test_the_wrong_package_is_refused_rather_than_reported_as_a_mismatch() -> None:
    """The report may be perfectly good and the caller has brought the wrong
    file. Reporting a difference would be a true statement that misleads."""
    with pytest.raises(ContractError, match="says nothing about the report"):
        recheck(
            report_of(),
            ANSWER,
            load_package(PACKAGES / "contract-en.json"),
            DEFAULT,
            akashi_version=__version__,
        )


def test_the_wrong_response_is_refused() -> None:
    with pytest.raises(ContractError, match="the wrong file"):
        recheck(
            report_of(),
            "A completely different answer.",
            load_package(PACKAGES / "gear-ja.json"),
            DEFAULT,
            akashi_version=__version__,
        )


def test_a_one_character_change_to_the_response_is_refused_not_diffed() -> None:
    with pytest.raises(ContractError, match="hashes to"):
        recheck(
            report_of(),
            ANSWER.replace("2.6kg", "2.7kg"),
            load_package(PACKAGES / "gear-ja.json"),
            DEFAULT,
            akashi_version=__version__,
        )


# --- What a mismatch says ----------------------------------------------------


def test_a_mismatch_says_what_differed_and_not_only_that_something_did() -> None:
    """ "The ids differ" is not a finding anybody can act on."""
    archived = report_of()
    archived["counts"]["particulars"]["floating"] = 99
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert not result.matches
    assert any("counts.particulars.floating" in line for line in result.differences)
    assert "99" in " ".join(result.differences)


def test_a_difference_names_the_segment_it_is_in() -> None:
    """Lists are indexed rather than compared whole, so a reader is not told
    that ``segments`` changed."""
    archived = report_of()
    archived["segments"][0]["verdict"] = "unbearing"
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert any(line.startswith("segments[0].verdict") for line in result.differences)


def test_a_version_difference_is_named_and_is_not_tampering() -> None:
    """akashi 0.3 auditing what 0.2 audited will legitimately differ, and a
    recheck that read as tampering would be worse than no recheck."""
    archived = report_of()
    archived["audited"]["akashi_version"] = "0.0.1"
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert result.version_differs
    assert "version difference is not tampering" in result.describe()
    assert result.archived_version == "0.0.1"


def test_the_version_difference_is_reported_first() -> None:
    """It may explain every line under it, and a reader should not scroll past
    forty count differences looking for the cause."""
    archived = report_of()
    archived["audited"]["akashi_version"] = "0.0.1"
    archived["counts"]["particulars"]["floating"] = 99
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert result.differences[0].startswith("audited.akashi_version")


def test_re_deriving_with_different_packs_differs_and_says_so() -> None:
    """Narrowing the packs changes the segmentation and therefore every count.
    The CLI uses the packs the report names for exactly this reason."""
    archived = report_of()
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        packs("ja"),
        akashi_version=__version__,
    )
    assert not result.matches
    assert any("audited.packs" in line for line in result.differences)


# --- Reading a report back ---------------------------------------------------


def test_an_unknown_report_contract_is_refused() -> None:
    body = report_of()
    body["contract"] = "somebody.else/1"
    with pytest.raises(ContractError, match="does not read"):
        read_report(body)


def test_a_future_major_version_is_refused() -> None:
    body = report_of()
    body["contract"] = "akashi.audit-report/2"
    with pytest.raises(ContractError, match="does not read"):
        read_report(body)


@pytest.mark.parametrize("field", ["contract", "report_id", "audited", "answer"])
def test_a_report_missing_a_required_field_is_refused(field: str) -> None:
    body = report_of()
    del body[field]
    with pytest.raises(ContractError):
        read_report(body)


@pytest.mark.parametrize("field", ["package_id", "response_hash", "packs", "akashi_version"])
def test_a_report_missing_what_recheck_needs_is_refused(field: str) -> None:
    body = report_of()
    del body["audited"][field]
    with pytest.raises(ContractError, match=f"audited.{field}"):
        read_report(body)


def test_a_report_that_is_not_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="is not JSON"):
        load_report(path)


def test_a_missing_report_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="cannot read the report"):
        load_report(tmp_path / "nowhere.json")


# --- Through the command line ------------------------------------------------


@pytest.fixture
def archived(isolated: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    import shutil

    shutil.copy(PACKAGES / "gear-ja.json", isolated / "package.json")
    (isolated / "answer.txt").write_text(ANSWER, encoding="utf-8")
    main(["audit", "--package", "package.json", "--response", "answer.txt", "--json"])
    path = isolated / "report.json"
    path.write_text(capsys.readouterr().out, encoding="utf-8")
    return path


def test_recheck_exits_zero_when_it_re_derives(
    archived: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["recheck", "report.json", "--package", "package.json", "--response", "answer.txt"])
    assert code == AUDITED
    assert "re-derived identically" in capsys.readouterr().out


def test_recheck_exits_five_when_it_does_not(
    archived: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A caller archiving reports needs to tell "re-derived and different" from
    "could not run"."""
    body = json.loads(archived.read_text(encoding="utf-8"))
    body["coverage"]["unbearing"] = 99
    archived.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    code = main(["recheck", "report.json", "--package", "package.json", "--response", "answer.txt"])
    assert code == DIFFERED
    printed = capsys.readouterr().out
    assert "coverage.unbearing" in printed
    assert "archived   sha256:" in printed


def test_recheck_exits_one_when_it_cannot_run(
    archived: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["recheck", "report.json", "--package", "package.json", "--response", "nothing.txt"]
    )
    assert code == REFUSED
    assert capsys.readouterr().err.startswith("akashi: ")


def test_recheck_uses_the_packs_the_report_names(
    archived: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not this machine's default. Re-deriving with a different pack set would
    change the segmentation, and the difference would be the recheck's rather
    than the report's."""
    body = json.loads(archived.read_text(encoding="utf-8"))
    assert body["audited"]["packs"] == ["en", "ja", "und", "zh"]
    assert (
        main(["recheck", "report.json", "--package", "package.json", "--response", "answer.txt"])
        == AUDITED
    )


def test_a_report_naming_a_pack_this_akashi_lacks_is_refused(
    archived: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A recheck under a different set of packs is not a recheck."""
    body = json.loads(archived.read_text(encoding="utf-8"))
    body["audited"]["packs"] = ["ko", "und"]
    archived.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    code = main(["recheck", "report.json", "--package", "package.json", "--response", "answer.txt"])
    assert code == REFUSED
    assert "does not have" in capsys.readouterr().err


def test_recheck_emits_json(archived: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(
        [
            "recheck",
            "report.json",
            "--package",
            "package.json",
            "--response",
            "answer.txt",
            "--json",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert body["matches"] is True
    assert body["archived_id"] == body["rederived_id"]
    assert body["differences"] == []


def test_recheck_reads_the_response_from_standard_input(
    archived: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import sys

    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(ANSWER.encode("utf-8")), encoding="utf-8")
    )
    code = main(["recheck", "report.json", "--package", "package.json", "--response", "-"])
    assert code == AUDITED
