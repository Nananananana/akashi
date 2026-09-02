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
from akashi.domain.report import AuditReport
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
from conftest import published_schema

PACKAGES = Path(__file__).parent / "packages"
ANSWERS = Path(__file__).parent / "answers"
ANSWER = (ANSWERS / "gear-ja.txt").read_text(encoding="utf-8")


def report() -> AuditReport:
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
    for no reason.

    It named the major version and nothing else, and this used to assert
    `endswith("/v1")`. That was too tight in one direction: the *draft status*
    is part of what a selector has to say, and the test below this one is why.
    What still has to hold is that the two identifiers are different strings and
    that this one names the same major version — moving it when the contract has
    not moved is the failure the docstring is about."""
    from akashi.domain.report import CONTRACT

    assert PREDICATE_TYPE != CONTRACT
    assert "/v1" in PREDICATE_TYPE
    assert PREDICATE_TYPE.rsplit("/v", 1)[-1].removesuffix("-draft") == "1"


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


# --- The identifier lives in a namespace akashi holds -------------------------


def test_the_identifiers_are_not_in_a_namespace_somebody_could_buy() -> None:
    """in-toto's guarantee for a `predicateType` is the namespace itself:

        TypeURIs are not registered. The natural namespacing of URIs is
        sufficient to prevent collisions.

    A namespace only prevents collisions if it is yours. These were under
    `akashi.dev`, a domain anybody can register — and the failure is worse than
    a dead link. A `predicateType` is what a verifier keys on *before* it reads
    a field, attestations are made to travel and cannot be recalled, so whoever
    bought the domain after a missed renewal could publish a different
    definition at the exact URI already-issued statements name.

    Pinned as a property rather than as the string, so that reintroducing a
    rentable namespace fails here rather than in somebody's verifier years from
    now. The values are read from the code and the schema, never from prose.
    """
    import json

    from akashi.infrastructure.rendering.attestation import PREDICATE_TYPE

    held = "https://github.com/Nananananana/akashi/"
    schema = published_schema()
    identifier = json.loads(schema.read_text(encoding="utf-8"))["$id"]

    for name, value in (("predicateType", PREDICATE_TYPE), ("$id", identifier)):
        assert value.startswith(held), (
            f"{name} is {value!r}. It has to sit in a namespace held by an account "
            f"rather than by a renewal: a lapsed one becomes somebody else's, and "
            f"an identifier that becomes somebody else's is worse than one that "
            f"stops resolving."
        )


def test_the_route_the_contract_tells_a_consumer_to_take_actually_works() -> None:
    """The published instruction, executed rather than trusted.

    A sibling project found its `docs/contracts.md` telling consumers to reach
    the schema through `importlib.resources` — true after `pip install`, **false
    in every development checkout**, and nothing in the repository ran the
    sentence, so nobody noticed. The audience for that sentence is the one group
    the project has no other way to reach.

    akashi's contract document names one path, in one markdown link. This walks
    it: follow the link the way a reader would, and validate a real
    attestation's predicate against whatever is at the other end.

    The link target is parsed as a link — data — never matched out of the prose
    around it, so the sentence explaining this test cannot satisfy it.
    """
    import json
    import re
    from pathlib import Path

    jsonschema = pytest.importorskip("jsonschema")
    contract = Path(__file__).parents[1] / "docs" / "audit-report.md"
    links = re.findall(
        r"\]\((\.\./src/akashi/schemas/[^)]+)\)", contract.read_text(encoding="utf-8")
    )
    assert len(links) == 1, f"the contract names {len(links)} schema paths; it should name one"

    schema = (contract.parent / links[0]).resolve()
    assert schema.is_file(), (
        f"docs/audit-report.md sends a reader to {links[0]}, which is not there"
    )
    jsonschema.validate(as_statement(report())["predicate"], json.loads(schema.read_text("utf-8")))


def test_the_two_identifiers_agree_on_the_version_they_name() -> None:
    """`predicateType` and the schema `$id` are related by convention and by
    nothing mechanical: one says `audit-report/v1`, the other
    `audit-report-1.json`. A consumer selects on the first and validates against
    the second.

    So moving one and not the other is a silent divergence — the statement would
    announce a predicate type whose schema describes something else, and every
    test here would still pass, because each checks its own half. This is the
    only place the halves are compared.

    **It is not the weaker half of the test above it**, and that was measured
    rather than argued.

    The better general rule — pass a real document through both sides rather
    than comparing identifiers — proves the *shapes* agree and is blind to every
    field validation does not read. Four of them here, checked by swapping each
    and revalidating:

        $id           ignored — the document validates identically
        title         ignored
        description   ignored
        $schema       ignored, even swapped to a different dialect

    A consumer selects on a label *before* it validates anything (ADR-0014), so
    the fields a validator ignores are the ones a reader meets first.

    And the mechanical form of "not redundant": break something in a way no
    existing check catches, and see whether only the new one fires. Rewriting
    `$id` to name `audit-report-9.json`, with the namespace left alone so the
    test above it stays quiet:

        1 failed, everything else passed
        FAILED test_the_two_identifiers_agree_on_the_version_they_name

    A new check's worth is not that it can fail. It is that it fails on a break
    nothing else notices.
    """
    import json

    from akashi.infrastructure.rendering.attestation import PREDICATE_TYPE

    schema = published_schema()
    identifier = json.loads(schema.read_text(encoding="utf-8"))["$id"]

    predicate_major = PREDICATE_TYPE.rsplit("/v", 1)[-1].removesuffix("-draft")
    schema_major = identifier.rsplit("-", 1)[-1].removesuffix(".json")
    assert predicate_major == schema_major, (
        f"predicateType names v{predicate_major} and the schema names {schema_major}. "
        f"A consumer selects on the first and validates against the second."
    )


def test_the_selector_says_the_contract_is_still_a_draft() -> None:
    """The report says `1-draft` inside itself. `predicateType` has to say it
    too, because that is the field read *first*.

    An in-toto verifier selects on the predicate type before parsing anything,
    so one keying on a bare `/v1` would believe it had selected a frozen
    contract while holding a provisional one — and when a later akashi adds an
    optional field, all it receives is a `ValidationError`, indistinguishable
    from a corrupt document. `contradiction` was added to this contract exactly
    that way. The addition was legitimate under a draft; what was missing is
    that the selector never said "draft".

    The identifier changing at the freeze is the **signal**, not the cost:
    statements carrying `v1-draft` are precisely the ones that predate it.
    """
    from akashi.domain.report import CONTRACT
    from akashi.infrastructure.rendering.attestation import PREDICATE_TYPE

    assert CONTRACT.endswith("-draft") == PREDICATE_TYPE.endswith("-draft"), (
        f"the report says {CONTRACT!r} and the selector says {PREDICATE_TYPE!r}. "
        f"A verifier reads the second before it reads the first."
    )
