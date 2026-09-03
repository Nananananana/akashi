"""The shape everybody else already has.

akashi reads `tsumugi.context-package/1`, and almost nobody outside this family
holds one. What people hold is a question, an answer, and a list of retrieved
strings — the shape every RAG evaluation library takes, under three sets of
names. Asking somebody to build a package before they can try akashi is the
barrier, not the audit.

The hard part is not reading the names. It is **not inventing provenance while
doing it**: a ContextPackage carries a document, a path and an offset into a
file, a list of strings carries none of that, and a report that implied
otherwise would send a reader to open a file that does not exist.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from akashi import evaluate, evaluate_sample
from akashi.domain.package import PLAIN_CONTRACT
from akashi.errors import ContractError
from akashi.infrastructure.packages.plain import FIELDS, package_from_contexts, read_sample

ANSWER = "The tent weighs 2.4kg and the gas is 9.9kg."
CONTEXTS = ["The tent weighs 2.4kg.", "Gas cartridge, 250mg."]


# --- the three vocabularies --------------------------------------------------


@pytest.mark.parametrize(
    ("name", "sample"),
    [
        (
            "ragas",
            {"user_input": "How heavy?", "response": ANSWER, "retrieved_contexts": CONTEXTS},
        ),
        (
            "deepeval",
            {"input": "How heavy?", "actual_output": ANSWER, "retrieval_context": CONTEXTS},
        ),
        ("plain", {"question": "How heavy?", "answer": ANSWER, "contexts": CONTEXTS}),
    ],
)
def test_a_sample_from_any_of_them_reads(name: str, sample: dict[str, object]) -> None:
    """A person with a dataset should point akashi at it, not port it."""
    answer, package = read_sample(sample)
    assert answer == ANSWER
    assert [item.text for item in package.evidence.items] == CONTEXTS
    assert package.query == "How heavy?"


def test_the_three_give_the_same_answer() -> None:
    """They are the same three values under different names, so they had better
    be the same audit."""
    shares = {
        evaluate_sample(sample).grounded_share
        for sample in (
            {"user_input": "q", "response": ANSWER, "retrieved_contexts": CONTEXTS},
            {"input": "q", "actual_output": ANSWER, "retrieval_context": CONTEXTS},
            {"question": "q", "answer": ANSWER, "contexts": CONTEXTS},
        )
    }
    assert len(shares) == 1


def test_a_sample_with_none_of_the_names_is_refused_and_lists_them() -> None:
    """A caller whose field is spelled differently needs to see the ones that
    would have worked, not that theirs did not."""
    with pytest.raises(ContractError) as refusal:
        read_sample({"prompt": "q", "completion": ANSWER, "docs": CONTEXTS})
    message = str(refusal.value)
    assert all(name in message for name in FIELDS["answer"])


# --- no provenance is invented -----------------------------------------------


def test_the_package_does_not_claim_to_be_a_context_package() -> None:
    """`tsumugi.context-package/1` promises a document id, a source path and an
    offset into a file that exists. A consumer recognising that contract would
    be entitled to open the paths, and there are none."""
    package = package_from_contexts(CONTEXTS)
    assert package.contract == PLAIN_CONTRACT
    assert package.contract != "tsumugi.context-package/1"


def test_no_anchor_names_a_file() -> None:
    """A reader who sees `notes/gear.md[1209:1214]` goes and opens that file."""
    result = evaluate(answer=ANSWER, contexts=CONTEXTS)
    located = [
        location
        for segment in result.report.assessment.segments
        for one in segment.particulars
        for location in one.locations
    ]
    assert located, "nothing grounded, so this checks nothing"
    for location in located:
        assert location.anchor.source_path == ""
        assert location.anchor.document_id.startswith("context ")


def test_the_offsets_index_the_strings_that_were_passed() -> None:
    """Which is the only honest thing they can index, and the reason the limit
    below exists rather than a note in a README."""
    result = evaluate(answer=ANSWER, contexts=CONTEXTS)
    for segment in result.report.assessment.segments:
        for one in segment.particulars:
            for location in one.locations:
                span = location.anchor.span
                index = int(location.anchor.document_id.split()[-1]) - 1
                assert CONTEXTS[index][span.start : span.end] == one.particular.text


def test_the_report_says_the_evidence_was_plain_strings() -> None:
    """The artefact travels and the documentation does not (ADR-0005)."""
    body = evaluate(answer=ANSWER, contexts=CONTEXTS).to_dict()
    assert any("plain strings" in line for line in body["limits"])
    assert any("not a document" in line for line in body["limits"])


def test_a_package_read_from_a_file_does_not_gain_that_limit() -> None:
    """The line is about this evidence, not about akashi."""
    from akashi.application import audit
    from akashi.infrastructure.languages import DEFAULT
    from akashi.infrastructure.packages import load_package

    package = load_package(Path(__file__).parent / "packages" / "gear-ja.json")
    body = audit("テントは 2.4kg。", package, DEFAULT).to_dict()
    assert not any("plain strings" in line for line in body["limits"])


# --- what the one-call API is, and is not ------------------------------------


def test_the_shortest_way_in_is_three_values() -> None:
    result = evaluate(answer=ANSWER, contexts=CONTEXTS)
    assert result.grounded_share == 0.5
    assert result.grounded == ("2.4kg",)
    assert result.floating == ("9.9kg",)


def test_the_result_carries_the_whole_report() -> None:
    """A shell, not a shortcut: the number this returns is the number the
    artefact carries, because it is the same report."""
    result = evaluate(answer=ANSWER, contexts=CONTEXTS)
    body = result.to_dict()
    assert body["contract"].startswith("akashi.audit-report/")
    assert body["counts"]["grounded_share"] == result.grounded_share


def test_the_limits_travel_on_the_object_too() -> None:
    """`grounded_share` is not a faithfulness score, and the object a caller
    holds in a notebook has to say so as loudly as the artefact does."""
    result = evaluate(answer=ANSWER, contexts=CONTEXTS)
    assert result.limits
    assert any("statement about strings" in line for line in result.limits)


def test_nothing_to_check_is_not_a_score_of_zero() -> None:
    """An answer with nothing checkable has not scored, and a number there
    would be read as though it had."""
    result = evaluate(answer="It depends on the weather.", contexts=CONTEXTS)
    assert result.grounded_share is None


def test_no_context_is_refused_rather_than_scored_zero() -> None:
    """Every particular would float correctly and uselessly, and a 0.0 would
    read as a finding about the answer."""
    with pytest.raises(ContractError, match="no context"):
        evaluate(answer=ANSWER, contexts=[])


def test_one_string_is_not_read_as_a_list_of_letters() -> None:
    """The easiest mistake to make with this signature, and it would produce a
    package of one letter per item and an audit that means nothing."""
    with pytest.raises(ContractError, match="list of strings"):
        package_from_contexts("The tent weighs 2.4kg.")


# --- the same door on every surface ------------------------------------------


def test_the_command_line_takes_a_sample_file(tmp_path: Path) -> None:
    from akashi.interfaces.cli.main import AUDITED, main

    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps({"user_input": "q", "response": ANSWER, "retrieved_contexts": CONTEXTS}),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    import contextlib

    with out.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
        code = main(["audit", "--contexts", str(sample), "--json"])
    assert code == AUDITED
    assert json.loads(out.read_text(encoding="utf-8"))["counts"]["grounded_share"] == 0.5


def test_a_package_still_needs_a_response(tmp_path: Path) -> None:
    """The two flags are not interchangeable: a package carries no answer, and a
    sample object may. A missing `--response` is a wrong command line and exits
    2 like every other misuse, not 1 like a refusal about an input."""
    from akashi.interfaces.cli.main import main

    package = Path(__file__).parent / "packages" / "gear-ja.json"
    with pytest.raises(SystemExit) as exit_code:
        main(["audit", "--package", str(package)])
    assert exit_code.value.code == 2


def test_the_mcp_tool_takes_contexts() -> None:
    from akashi.interfaces.mcp import PROTOCOL_VERSION, serve

    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    request = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "_meta": meta,
                "name": "audit",
                "arguments": {"answer": ANSWER, "contexts": CONTEXTS},
            },
        },
        ensure_ascii=False,
    )
    out = io.StringIO()
    serve(io.StringIO(request + "\n"), out)
    body = json.loads(out.getvalue())["result"]["structuredContent"]
    assert body["counts"]["grounded_share"] == 0.5
    assert any("plain strings" in line for line in body["limits"])


def test_the_mcp_tool_still_takes_a_package() -> None:
    """Adding a door does not close one."""
    from akashi.interfaces.mcp import TOOLS

    audit_tool = next(tool for tool in TOOLS if tool["name"] == "audit")
    properties = audit_tool["inputSchema"]["properties"]
    assert "package" in properties
    assert "contexts" in properties
    assert audit_tool["inputSchema"]["required"] == ["answer"]
