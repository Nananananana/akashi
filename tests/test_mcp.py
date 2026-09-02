"""The agent-facing surface, exercised as a client exercises it.

Every test here drives `serve` over streams rather than calling handlers, for
the same reason the CLI tests run `main`: the framing, the encoding and the
"nothing on stdout that is not a response" rule are the parts that break, and a
test that calls the handler directly checks none of them.

The protocol facts below were read from the specification at
<https://modelcontextprotocol.io/specification/2026-07-28>, not inferred from a
client that happened to work. `resultType`, the reserved `_meta` key names and
the error codes are somebody else's contract, and akashi's whole discipline
about reading a contract as a document (ADR-0007) applies to this one too.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from akashi import __version__
from akashi.interfaces.mcp import PROTOCOL_VERSION, TOOLS, serve
from akashi.interfaces.mcp.protocol import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    UNSUPPORTED_PROTOCOL_VERSION,
)
from akashi.interfaces.mcp.server import LEGACY_PROTOCOL_VERSION

PACKAGES = Path(__file__).parent / "packages"
ANSWER = "テントは 2.4kg、ガスは 250mg カートリッジ。"

#: What every modern request must carry. The specification makes
#: `protocolVersion` and `clientCapabilities` required and says a request
#: missing either is malformed.
META: dict[str, Any] = {
    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
}


def package() -> dict[str, Any]:
    body = json.loads((PACKAGES / "gear-ja.json").read_text(encoding="utf-8"))
    assert isinstance(body, dict)
    return body


def talk(*messages: dict[str, Any]) -> list[dict[str, Any]]:
    """Send lines, read lines. The transport is the subject."""
    stream_in = io.StringIO("".join(json.dumps(one, ensure_ascii=False) + "\n" for one in messages))
    stream_out = io.StringIO()
    assert serve(stream_in, stream_out) == 0
    return [json.loads(line) for line in stream_out.getvalue().splitlines() if line]


def call(name: str, arguments: dict[str, Any], identifier: int = 1) -> dict[str, Any]:
    replies = talk(
        {
            "jsonrpc": "2.0",
            "id": identifier,
            "method": "tools/call",
            "params": {"_meta": META, "name": name, "arguments": arguments},
        }
    )
    assert len(replies) == 1
    return replies[0]


# --- the protocol ------------------------------------------------------------


def test_discover_names_the_versions_and_the_server() -> None:
    """`server/discover` is the one method the specification says a server
    **MUST** implement, and on stdio it is what a dual-era client probes with
    to find out which era it is talking to."""
    reply = talk(
        {"jsonrpc": "2.0", "id": "d1", "method": "server/discover", "params": {"_meta": META}}
    )[0]
    result = reply["result"]
    assert result["resultType"] == "complete"
    assert PROTOCOL_VERSION in result["supportedVersions"]
    assert result["capabilities"] == {"tools": {}}
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"] == {
        "name": "akashi",
        "version": __version__,
    }


def test_every_result_names_its_type() -> None:
    """Required by this revision, and a client reading an older server treats
    an absent one as `complete` -- so sending it costs nothing either way."""
    for reply in talk(
        {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": META}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": META}},
    ):
        assert reply["result"]["resultType"] == "complete"


def test_a_version_this_server_does_not_speak_is_refused_by_the_reserved_code() -> None:
    """-32022, with the list of what is supported. The specification reserves
    -32020 to -32099 for itself and forbids an implementation from emitting a
    code in that range that the specification does not define, so this one is
    copied rather than chosen."""
    reply = talk(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {"_meta": {**META, "io.modelcontextprotocol/protocolVersion": "1900-01-01"}},
        }
    )[0]
    assert reply["error"]["code"] == UNSUPPORTED_PROTOCOL_VERSION
    assert reply["error"]["data"]["requested"] == "1900-01-01"
    assert PROTOCOL_VERSION in reply["error"]["data"]["supported"]


def test_a_client_from_before_the_handshake_was_retired_still_works() -> None:
    """The specification's own compatibility matrix says a legacy client
    against a modern-only server **fails**, with no fall-forward: it has no way
    to learn what went wrong. Most clients shipped today are legacy, so
    refusing them would make this surface correct and unusable.
    """
    replies = talk(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": LEGACY_PROTOCOL_VERSION, "capabilities": {}},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    )
    assert replies[0]["result"]["protocolVersion"] == LEGACY_PROTOCOL_VERSION
    assert replies[0]["result"]["serverInfo"]["name"] == "akashi"
    assert [tool["name"] for tool in replies[1]["result"]["tools"]] == [
        tool["name"] for tool in TOOLS
    ]
    assert len(replies) == 2, "a notification takes no response"


def test_a_notification_is_not_answered() -> None:
    assert talk({"jsonrpc": "2.0", "method": "notifications/initialized"}) == []


def test_a_bad_line_is_answered_and_the_loop_carries_on() -> None:
    """A client that sends one unparseable line has not stopped talking, and a
    server that died there would take the whole session with it."""
    stream_in = io.StringIO(
        "not json\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": META}})
        + "\n"
    )
    stream_out = io.StringIO()
    serve(stream_in, stream_out)
    replies = [json.loads(line) for line in stream_out.getvalue().splitlines()]
    assert replies[0]["error"]["code"] == PARSE_ERROR
    assert "tools" in replies[1]["result"]


def test_an_unknown_method_is_refused() -> None:
    reply = talk({"jsonrpc": "2.0", "id": 1, "method": "corpus/delete", "params": {"_meta": META}})[
        0
    ]
    assert reply["error"]["code"] == METHOD_NOT_FOUND


def test_nothing_reaches_the_stream_that_is_not_a_message() -> None:
    """A stray `print` corrupts the transport, and the client reports a parse
    error it cannot attribute to anything. Every line out must parse."""
    stream_in = io.StringIO(
        "\n".join(
            json.dumps(one, ensure_ascii=False)
            for one in (
                {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": META}},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "_meta": META,
                        "name": "audit",
                        "arguments": {"answer": ANSWER, "package": package()},
                    },
                },
            )
        )
        + "\n"
    )
    stream_out = io.StringIO()
    serve(stream_in, stream_out)
    for line in stream_out.getvalue().splitlines():
        assert json.loads(line)["jsonrpc"] == "2.0"


# --- the tools ---------------------------------------------------------------


def test_the_tool_list_is_deterministic_and_every_schema_is_closed() -> None:
    """Deterministic because clients cache it. Closed because an argument
    akashi does not know is an argument a model invented, and accepting it
    silently would audit something other than what was asked for."""
    assert [tool["name"] for tool in TOOLS] == ["audit", "recheck", "explain"]
    for tool in TOOLS:
        assert tool["inputSchema"]["additionalProperties"] is False
        assert tool["inputSchema"]["type"] == "object"
        assert tool["description"]


def test_audit_returns_the_report_as_data_and_as_text() -> None:
    """`structuredContent` for the client, which can validate and index it. The
    text block for the model, which reads text -- and it is the *rendered*
    report, because the rendering leads with what was not checked (ADR-0005)
    and the raw document does not read in that order."""
    result = call("audit", {"answer": ANSWER, "package": package()})["result"]
    assert result["isError"] is False
    body = result["structuredContent"]
    assert body["contract"].startswith("akashi.audit-report/")
    assert body["answer"] == ANSWER
    assert result["content"][0]["text"].startswith("akashi - ")


def test_what_was_not_checked_reaches_the_agent() -> None:
    """An agent that cannot see the edge of the audit has the same problem as a
    person who cannot. `unchecked`, `coverage` and `limits` are on the
    structured result, not summarised away."""
    body = call("audit", {"answer": ANSWER, "package": package()})["result"]["structuredContent"]
    for key in ("unchecked", "coverage", "limits", "counts"):
        assert key in body
    assert body["limits"], "the method's limits travel with the artefact (ADR-0005)"


def test_the_instructions_say_what_floating_means() -> None:
    """The one misreading that matters, told to the model where it will see it.
    An agent that reads 'floating' as 'false' will rewrite an honest answer."""
    result = talk(
        {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": META}}
    )[0]["result"]
    assert "never 'false'" in result["instructions"]


def test_recheck_re_derives_and_compares() -> None:
    report = call("audit", {"answer": ANSWER, "package": package()})["result"]["structuredContent"]
    result = call(
        "recheck", {"report": report, "answer": ANSWER, "package": package()}, identifier=2
    )["result"]
    assert result["structuredContent"]["matches"] is True
    assert result["structuredContent"]["archived_id"] == report["report_id"]


def test_explain_reads_the_report_and_nothing_else() -> None:
    report = call("audit", {"answer": ANSWER, "package": package()})["result"]["structuredContent"]
    result = call("explain", {"report": report, "segment_id": "seg_001"}, identifier=2)["result"]
    assert "seg_001" in result["content"][0]["text"]
    assert "structuredContent" not in result


# --- what it will not do -----------------------------------------------------


def test_no_tool_takes_a_path() -> None:
    """akashi's CLI reads a file the user named, because the user is the person
    holding the files. Here the **model** chooses the arguments, and a tool that
    opened a path would be a file-read primitive with the report as the channel
    out -- a report quotes the answer verbatim.

    Asserted over the schemas rather than in prose, because a fourth tool
    written later is exactly when this gets forgotten.
    """
    for tool in TOOLS:
        for name, field in tool["inputSchema"]["properties"].items():
            assert "path" not in name.lower(), f"{tool['name']}.{name} looks like a path"
            assert "file" not in name.lower(), f"{tool['name']}.{name} looks like a path"
            assert "path" not in str(field.get("description", "")).lower() or "no paths" in str(
                field.get("description", "")
            ), f"{tool['name']}.{name} describes a path"


def test_no_tool_writes_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read-only, checked by taking the ability away. A tool an agent can call
    must not be able to change the machine it is called on."""

    body = package()  # read before the ability is taken away, not after

    def refuse(*args: object, **kwargs: object) -> object:
        raise AssertionError("an MCP tool touched the filesystem")

    monkeypatch.setattr("builtins.open", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    monkeypatch.setattr(Path, "write_text", refuse)
    monkeypatch.setattr(Path, "write_bytes", refuse)

    result = call("audit", {"answer": ANSWER, "package": body})["result"]
    assert result["isError"] is False


def test_a_refusal_reaches_the_model_rather_than_the_client() -> None:
    """A refusal is an answer a model can act on -- *the package declares no
    protection and the answer is full of placeholders* says what to fix. The
    specification calls that a tool execution error and asks for `isError`
    rather than a JSON-RPC error, because clients pass the first to the model
    and often not the second.
    """
    body = package()
    body["provenance"].pop("protection", None)
    result = call("audit", {"answer": "担当は <PERSON_001> です。", "package": body})["result"]
    assert result["isError"] is True
    assert "akashi refused" in result["content"][0]["text"]
    assert "placeholder-shaped" in result["content"][0]["text"]


def test_a_malformed_argument_is_a_protocol_error() -> None:
    """Different from a refusal: the request itself is wrong, and a model is
    less likely to recover from it than from an audit that said no."""
    reply = call("audit", {"answer": 42, "package": package()})
    assert reply["error"]["code"] == INVALID_PARAMS


def test_an_unknown_tool_is_a_protocol_error() -> None:
    assert call("ingest", {})["error"]["code"] == METHOD_NOT_FOUND


# --- the encoding, again -----------------------------------------------------


def test_the_transport_is_utf8_whatever_the_console_is() -> None:
    """A document channel, not prose. Everywhere else akashi prints, a
    character the console cannot show is replaced so the audit survives (#75);
    here the reader is a program and a `?` in a protocol message is corruption.

    The writer binds UTF-8 and leaves `errors` strict, so this fails loudly
    rather than handing a client something that parses and says otherwise.
    """
    from akashi.interfaces.mcp.protocol import utf8_writer, write_message

    raw = io.BytesIO()
    writer = utf8_writer(raw)
    assert getattr(writer, "encoding", "").lower().replace("-", "") == "utf8"
    assert getattr(writer, "errors", "") == "strict", (
        "a `?` substituted into a protocol message is corruption, not a concession"
    )
    write_message(writer, {"jsonrpc": "2.0", "id": 1, "result": {"text": "重量为2.4千克 — café"}})
    assert json.loads(raw.getvalue().decode("utf-8"))["result"]["text"] == "重量为2.4千克 — café"


def test_the_answer_survives_the_round_trip_verbatim() -> None:
    """Every span in the report indexes this string. A transport that altered
    one character would move every offset the agent is about to act on."""
    answer = "重量为2.4千克 — café • ✓ the tent is 2.4kg."
    body = call("audit", {"answer": answer, "package": package()})["result"]
    assert body["structuredContent"]["answer"] == answer
