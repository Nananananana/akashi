"""The report in a shape somebody else's signature can cover.

ADR-0014. akashi emits an in-toto Statement and signs nothing — the shape is
free and the keys are the caller's. What is checked here is that the envelope is
really the shape it claims, that it cannot disagree with the report inside it,
and that nothing anywhere implies it is signed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from akashi import __version__
from akashi.application import audit, recheck
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import as_statement
from akashi.infrastructure.rendering.attestation import (
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    _digest,
)
from akashi.infrastructure.reports import read_report
from akashi.interfaces.cli.main import AUDITED, main

PACKAGES = Path(__file__).parent / "packages"
ANSWERS = Path(__file__).parent / "answers"
ANSWER = (ANSWERS / "gear-ja.txt").read_text(encoding="utf-8")


def report():  # type: ignore[no-untyped-def]
    return audit(
        ANSWER, load_package(PACKAGES / "gear-ja.json"), DEFAULT, akashi_version=__version__
    )


# --- The envelope ------------------------------------------------------------


def test_it_is_an_in_toto_statement() -> None:
    statement = as_statement(report())
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE
    assert isinstance(statement["subject"], list)
    assert set(statement) == {"_type", "subject", "predicateType", "predicate"}


def test_the_subject_names_the_answer_by_digest() -> None:
    statement = as_statement(report(), subject="answer.txt")
    subject = statement["subject"][0]
    assert subject["name"] == "answer.txt"
    assert set(subject["digest"]) == {"sha256"}
    assert len(subject["digest"]["sha256"]) == 64


def test_the_digest_puts_the_algorithm_in_the_key() -> None:
    """akashi's own hashes name their algorithm inside the string, so a reader
    holding one alone can still check it. in-toto puts it in the key. Both are
    right for what they are, and this is where they meet."""
    assert _digest("sha256:abcd") == {"sha256": "abcd"}


def test_a_hash_that_does_not_name_its_algorithm_is_refused() -> None:
    with pytest.raises(ValueError, match="does not name its algorithm"):
        _digest("abcdef")


def test_the_envelope_and_the_predicate_cannot_disagree() -> None:
    """The subject digest is taken from the report's own ``response_hash``,
    from the same field. Two places holding the same fact is two places for it
    to drift."""
    statement = as_statement(report())
    inside = statement["predicate"]["audited"]["response_hash"]
    assert statement["subject"][0]["digest"]["sha256"] == inside.partition(":")[2]


def test_the_predicate_is_the_report_unchanged() -> None:
    """One shape, wrapped or not. Anything that transformed the report on the
    way into the envelope would be a second contract."""
    assert as_statement(report())["predicate"] == report().to_dict()


def test_a_statements_predicate_reads_back_as_a_report() -> None:
    """So ``recheck`` works on the predicate exactly as on a bare report."""
    statement = as_statement(report())
    archived = read_report(statement["predicate"])
    result = recheck(
        archived,
        ANSWER,
        load_package(PACKAGES / "gear-ja.json"),
        DEFAULT,
        akashi_version=__version__,
    )
    assert result.matches


def test_an_unnamed_subject_says_it_was_unnamed() -> None:
    """Not an empty string: a subject with no name is harder to read in a log
    than one that says it was unnamed."""
    assert as_statement(report(), subject="")["subject"][0]["name"] == "response"


# --- What it is not ----------------------------------------------------------


def test_nothing_in_the_statement_claims_to_be_signed() -> None:
    """An envelope read as an attestation is worse than no envelope. That
    hazard is created by ADR-0014 and named in it, and the mitigation is that
    no field here invites the reading."""
    body = json.dumps(as_statement(report()))
    for word in ("signature", "signed", "sig", "cert", "verified"):
        assert word not in body.lower()


def test_the_help_says_akashi_signs_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["audit", "--help"])
    printed = capsys.readouterr().out
    assert "unsigned" in printed
    assert "akashi signs nothing" in printed


def test_the_predicate_type_is_versioned_apart_from_the_report_contract() -> None:
    """A consumer selects on the predicate type before it reads a field, and a
    URI that moved when the report contract did not would break that selection
    for no reason."""
    from akashi.domain.report import CONTRACT

    assert PREDICATE_TYPE != CONTRACT
    assert PREDICATE_TYPE.endswith("/v1")


# --- Through the command line ------------------------------------------------


def test_the_cli_emits_a_statement(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(ANSWERS / "gear-ja.txt"),
            "--attestation",
        ]
    )
    assert code == AUDITED
    statement = json.loads(capsys.readouterr().out)
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["subject"][0]["name"] == "gear-ja.txt"


def test_the_subject_defaults_to_the_response_file_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(ANSWERS / "gear-ja.txt"),
            "--attestation",
        ]
    )
    assert json.loads(capsys.readouterr().out)["subject"][0]["name"] == "gear-ja.txt"


def test_the_subject_can_be_named(capsys: pytest.CaptureFixture[str]) -> None:
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(ANSWERS / "gear-ja.txt"),
            "--attestation",
            "--subject",
            "matter-4021/answer",
        ]
    )
    assert json.loads(capsys.readouterr().out)["subject"][0]["name"] == "matter-4021/answer"


def test_a_streamed_response_is_named_rather_than_left_blank(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import sys

    monkeypatch.setattr(
        sys, "stdin", io.TextIOWrapper(io.BytesIO(ANSWER.encode("utf-8")), encoding="utf-8")
    )
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            "-",
            "--attestation",
        ]
    )
    assert json.loads(capsys.readouterr().out)["subject"][0]["name"] == "response"


def test_the_statement_is_not_escaped_into_unreadability(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(ANSWERS / "gear-ja.txt"),
            "--attestation",
        ]
    )
    printed = capsys.readouterr().out
    assert "テント" in printed
    assert "\\u30c6" not in printed
