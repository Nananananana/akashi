"""A protection record handed over as a document (Sora R1), and what unit a span is in (R4).

Sora, the orchestration layer, does not import mamori. It gets a
`mamori.protection-scope/1` record back beside the protected text and hands it
to akashi as JSON. akashi already acted on the same three facts when they were
inside a package; this is the same decision reached through a second door.

The second door has one rule of its own that the first does not, and it is the
thing most worth a test: **a record with no `reversible` reads as false.** That
is mamori's ADR-0032, the opposite of what the package reader does for the same
field name, and the direction in which being wrong is loud rather than silent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from akashi import evaluate
from akashi.application import audit
from akashi.application.admit import effective_protection
from akashi.domain.coverage import IRREVERSIBLE_PROTECTION_LIMITS
from akashi.domain.package import Protection
from akashi.domain.verdict import Verdict
from akashi.errors import ContractError, ProtectedResponseError
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import read_protection_scope
from akashi.infrastructure.packages.plain import package_from_contexts
from conftest import mcp_call

RECORD: dict[str, Any] = {
    "contract": "mamori.protection-scope/1",
    "by": "mamori/0.31.0",
    "scope": "session-abc123def456",
    "reversible": False,
    "mode": "placeholder",
    "placeholders": [{"token": "<PERSON_001>", "kind": "PERSON"}],
    "protected": [],
    "masked": [{"kind": "PERSON", "count": 1}],
}

MASKED_ANSWER = "担当は <PERSON_001> です。重量は 2.4kg。"
CONTEXTS = ["重量は 2.4kg です。"]


def record(**changes: Any) -> dict[str, Any]:
    body = dict(RECORD)
    body.update(changes)
    return body


# --- the reader, and the one rule that is mamori's rather than akashi's ------


def test_the_three_fields_akashi_acts_on_are_read() -> None:
    found = read_protection_scope(RECORD)
    assert found == Protection(by="mamori/0.31.0", scope="session-abc123def456", reversible=False)


def test_a_missing_reversible_reads_as_false() -> None:
    """mamori's ADR-0032, and the opposite of the package reader's rule for the
    same word. A wrong `true` fails silently -- an honest quotation of a masked
    value is reported as a fabrication. A wrong `false` costs a segment being
    `unverifiable` that could have been checked, which a reader can see."""
    body = record()
    del body["reversible"]
    assert read_protection_scope(body).reversible is False


def test_reversible_is_read_as_a_boolean_and_not_through_bool() -> None:
    """`bool("false")` is True, and that is the unsafe direction."""
    with pytest.raises(ContractError, match="a boolean"):
        read_protection_scope(record(reversible="false"))


def test_a_surrogate_record_is_refused_by_its_identifier() -> None:
    """A surrogate is designed to be indistinguishable from a real value.
    Auditing that text would report invented names as grounded."""
    with pytest.raises(ContractError, match="surrogates"):
        read_protection_scope(
            record(
                contract="mamori.protection-scope/1+surrogate",
                protected=[{"kind": "PERSON", "count": 1}],
            )
        )


def test_a_surrogate_record_from_before_the_split_is_refused_by_its_contents() -> None:
    """The contract's own comment: the check that survives a version change is
    `protected` being non-empty, not the identifier. A record written before
    the identifier was split declared the plain contract while carrying
    surrogates -- and iriguchi's reader accepted eight of nine such records."""
    with pytest.raises(ContractError, match="before the contract split"):
        read_protection_scope(record(protected=[{"kind": "PERSON", "count": 2}]))


def test_an_unknown_contract_is_refused_rather_than_read_by_its_known_fields() -> None:
    with pytest.raises(ContractError, match="does not recognise"):
        read_protection_scope(record(contract="mamori.protection-scope/2"))


@pytest.mark.parametrize("missing", ["by", "scope"])
def test_a_record_without_a_producer_or_a_scope_is_refused(missing: str) -> None:
    body = record()
    del body[missing]
    with pytest.raises(ContractError, match=f"no '{missing}'"):
        read_protection_scope(body)


def test_a_record_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(ContractError, match="JSON object"):
        read_protection_scope(["not", "a", "record"])


# --- one protection, from either door, and never two -----------------------------


def test_the_record_is_the_protection_when_the_package_declares_none() -> None:
    """The case the package cannot know about: a redactor that ran after the
    package was built cannot appear in `provenance.protection`."""
    package = package_from_contexts(CONTEXTS)
    assert package.protection is None
    found = effective_protection(package, read_protection_scope(RECORD))
    assert found is not None
    assert found.by == "mamori/0.31.0"


def test_the_package_is_the_protection_when_no_record_is_given() -> None:
    package = package_from_contexts(CONTEXTS)
    assert effective_protection(package, None) is package.protection


def test_a_package_and_a_record_that_disagree_are_refused() -> None:
    """Two answers to "who protected this" is one too many, and picking either
    would put a name on the report that the other source contradicts."""
    import dataclasses

    package = dataclasses.replace(
        package_from_contexts(CONTEXTS),
        protection=Protection(by="mamori/0.30.0", scope="session-other", reversible=True),
        declares_protection=True,
    )
    with pytest.raises(ProtectedResponseError, match="will not guess which"):
        effective_protection(package, read_protection_scope(RECORD))


def test_a_package_and_a_record_that_agree_are_one_protection() -> None:
    import dataclasses

    same = read_protection_scope(RECORD)
    package = dataclasses.replace(
        package_from_contexts(CONTEXTS), protection=same, declares_protection=True
    )
    assert effective_protection(package, same) == same


# --- what the audit says when the record says irreversible ------------------------


def audited(answer: str = MASKED_ANSWER, **changes: Any) -> Any:
    return audit(
        answer,
        package_from_contexts(CONTEXTS),
        DEFAULT,
        protection=read_protection_scope(record(**changes)),
    )


def test_a_masked_segment_is_unverifiable_and_the_rest_is_still_audited() -> None:
    """ADR-0008's third path, reached through the document door. Unknown and
    false are different, and the segment carrying the mask is the first."""
    report = audited()
    verdicts = [segment.verdict for segment in report.assessment.segments]
    assert verdicts == [Verdict.UNVERIFIABLE, Verdict.GROUNDED]


def test_the_report_says_why_in_limits() -> None:
    """The reason travels with the report. A reader who sees `unverifiable`
    without this line reads it as akashi giving up."""
    body = audited().to_dict()
    assert IRREVERSIBLE_PROTECTION_LIMITS[0] in body["limits"]


def test_the_records_producer_is_copied_to_provenance() -> None:
    """Sora's acceptance criterion, verbatim: `provenance.protection_by` carries
    the record's `by`."""
    assert audited().to_dict()["provenance"]["protection_by"] == "mamori/0.31.0"


def test_the_limit_is_not_said_when_nothing_was_masked() -> None:
    """A line about masked values on a report with no masked value is a warning
    about nothing, and a reader learns to skip the section it lives in."""
    body = audited(answer="重量は 2.4kg。").to_dict()
    assert IRREVERSIBLE_PROTECTION_LIMITS[0] not in body["limits"]
    assert body["provenance"]["protection_by"] == "mamori/0.31.0"


def test_a_reversible_record_with_no_restorer_is_a_refusal_that_says_so() -> None:
    """Sora R3: a refusal reaches it as a result carrying the word `refused`,
    which it maps to `refused` rather than `failed`. Over the API it is the
    exception; the MCP test below checks the wire."""
    with pytest.raises(ProtectedResponseError, match="no restorer was given"):
        audited(reversible=True, masked=[])


# --- the same door on every surface --------------------------------------------------


def test_the_mcp_audit_tool_takes_the_record_as_sora_sends_it() -> None:
    """R2 confirmed too: the argument names are `answer` and `package`/`contexts`,
    and `protection` sits beside them."""
    result = mcp_call(
        "audit", {"answer": MASKED_ANSWER, "contexts": CONTEXTS, "protection": RECORD}
    )
    assert result.get("isError") is not True
    body = result["structuredContent"]
    assert [segment["verdict"] for segment in body["segments"]] == ["unverifiable", "grounded"]
    assert body["provenance"]["protection_by"] == "mamori/0.31.0"
    assert IRREVERSIBLE_PROTECTION_LIMITS[0] in body["limits"]


def test_the_mcp_refusal_carries_the_word_refused() -> None:
    """R3. `isError: true` alone cannot be told from `failed`; the word is what
    Sora keys on."""
    result = mcp_call(
        "audit",
        {
            "answer": MASKED_ANSWER,
            "contexts": CONTEXTS,
            "protection": record(reversible=True, masked=[]),
        },
    )
    assert result.get("isError") is True
    assert result["content"][0]["text"].startswith("akashi refused:")


def test_the_mcp_tool_refuses_a_surrogate_record_as_a_tool_error() -> None:
    result = mcp_call(
        "audit",
        {
            "answer": "x",
            "contexts": ["x"],
            "protection": record(
                contract="mamori.protection-scope/1+surrogate",
                protected=[{"kind": "PERSON", "count": 1}],
            ),
        },
    )
    assert result.get("isError") is True
    assert "surrogates" in result["content"][0]["text"]


def test_the_mcp_tool_schema_offers_it_on_audit_and_on_recheck() -> None:
    from akashi.interfaces.mcp import TOOLS

    for name in ("audit", "recheck"):
        tool = next(tool for tool in TOOLS if tool["name"] == name)
        assert "protection" in tool["inputSchema"]["properties"], name
        assert "protection" not in tool["inputSchema"]["required"], name


def test_the_mcp_recheck_re_derives_with_the_record(tmp_path: Path) -> None:
    """A recheck without the record would re-derive a different report --
    every masked segment floating instead of unverifiable -- and report a
    mismatch that is about the inputs, not the audit."""
    # A real package rather than one built from strings: `recheck` takes the
    # package as the document it was audited over, and a ContextPackage built
    # from strings has no document form to hand back.
    from akashi import __version__
    from akashi.infrastructure.packages import load_package

    package_file = Path(__file__).parent / "packages" / "gear-ja.json"
    # The version is part of `report_id`, and the MCP server stamps its own.
    # An archive made without one re-derives to a different id for a reason
    # that is about the test and not about the record.
    original = audit(
        MASKED_ANSWER,
        load_package(package_file),
        DEFAULT,
        akashi_version=__version__,
        protection=read_protection_scope(RECORD),
    )
    first = next(segment.verdict for segment in original.assessment.segments)
    assert first is Verdict.UNVERIFIABLE, "the archive does not exercise the record"
    result = mcp_call(
        "recheck",
        {
            "report": original.to_dict(),
            "answer": MASKED_ANSWER,
            "package": json.loads(package_file.read_text(encoding="utf-8")),
            "protection": RECORD,
        },
    )
    assert result.get("isError") is not True, result["content"][0]["text"]
    assert result["structuredContent"]["matches"] is True


def test_the_command_line_takes_a_record_file(tmp_path: Path) -> None:
    import contextlib

    from akashi.interfaces.cli.main import AUDITED, main

    record_file = tmp_path / "protection.json"
    record_file.write_text(json.dumps(RECORD), encoding="utf-8")
    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps({"answer": MASKED_ANSWER, "contexts": CONTEXTS}, ensure_ascii=False),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    with out.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
        code = main(
            ["audit", "--contexts", str(sample), "--protection", str(record_file), "--json"]
        )
    assert code == AUDITED
    body = json.loads(out.read_text(encoding="utf-8"))
    assert [segment["verdict"] for segment in body["segments"]] == ["unverifiable", "grounded"]
    assert body["provenance"]["protection_by"] == "mamori/0.31.0"


# --- R4: a span is in code points, and the contract says so where it is read -----


def test_every_span_into_the_answer_slices_to_its_text_on_cjk() -> None:
    """The property Sora's highlight rests on. In this answer the byte offset
    and the code-point offset of every particular differ, so a consumer that
    indexed by byte would highlight a different word."""
    answer = "テントは２.４kg、参加者は12人。"
    assert len(answer.encode("utf-8")) != len(answer), "this answer does not separate the units"
    report = evaluate(answer=answer, contexts=["テントは2.4kg。参加者は12人。"]).report

    checked = 0
    for segment in report.assessment.segments:
        start, end = segment.segment.span.start, segment.segment.span.end
        assert answer[start:end] == segment.segment.text
        for one in segment.particulars:
            start, end = one.particular.span.start, one.particular.span.end
            assert answer[start:end] == one.particular.text
            assert len(answer[:start].encode("utf-8")) != start, "byte and code point agree here"
            checked += 1
    assert checked >= 2, "nothing bearing a particular was checked"


def test_response_length_is_in_code_points_like_every_span() -> None:
    answer = "テントは２.４kg、参加者は12人。"
    body = evaluate(answer=answer, contexts=["x"]).to_dict()
    assert body["audited"]["response_length"] == len(answer)
    assert body["audited"]["response_length"] != len(answer.encode("utf-8"))


def test_the_contract_says_the_unit_beside_every_field_that_carries_a_span() -> None:
    """The definition was on the `span` type and a consumer could not find it.
    It now sits on each field, and says which string it indexes."""
    schema = json.loads(Path("src/akashi/schemas/audit-report-1.json").read_text(encoding="utf-8"))
    defs = schema["$defs"]
    particular = defs["particular"]["properties"]["span"]["description"]
    assert "Code-point offsets into `answer`" in particular
    assert "not bytes" in particular
    location = defs["location"]["properties"]["span"]["description"]
    assert "SOURCE document" in location
    assert "not into `answer`" in location
    length = schema["properties"]["audited"]["properties"]["response_length"]["description"]
    assert "code points" in length
    assert "NOT the byte length" in length
