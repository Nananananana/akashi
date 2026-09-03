"""A document shaped to break the parser is refused, not crashed on.

Every document akashi reads came from outside: a ContextPackage from a producer,
an archived report from a filing, a line of JSON-RPC from a client whose
arguments a model chose. `json.loads` recurses, and a deeply nested document
raised `RecursionError` -- which is not a `json.JSONDecodeError`, so it went past
every reader and reached the user as a traceback.

On the MCP surface it was worse: the exception left the request generator, left
the loop, and **ended the server**. One malformed message closed the session,
which is the one thing that loop exists not to allow.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from akashi.errors import ContractError
from akashi.infrastructure.documents import MAX_DEPTH, depth_of, parse

PACKAGES = Path(__file__).parent / "packages"


def nested(depth: int) -> str:
    return "[" * depth + "1" + "]" * depth


# --- counting rather than catching -------------------------------------------


def test_depth_is_counted_without_parsing() -> None:
    """Arithmetic, so it cannot exhaust anything and gives the same answer on
    every build. Catching `RecursionError` would depend on a process setting a
    caller can change and on a C stack that is not the same everywhere -- and
    where the stack runs out first, there is no exception to catch."""
    assert depth_of("1") == 0
    assert depth_of("[]") == 1
    assert depth_of(nested(5)) == 5
    assert depth_of('{"a": {"b": [1, 2]}}') == 3


def test_a_bracket_inside_a_string_is_text() -> None:
    """The one thing a counter can get wrong that a parser cannot."""
    assert depth_of('{"a": "[[[[[[[[[["}') == 1
    assert depth_of('{"a": "\\"[[["}') == 1
    assert depth_of('["]]]]"]') == 1


def test_it_stops_counting_once_the_limit_is_passed() -> None:
    """A document written to be expensive costs the prefix, not the file."""
    assert depth_of(nested(10_000), limit=8) > 8


def test_a_real_document_is_nowhere_near_the_limit() -> None:
    """The bound is set the way a floor is. The deepest JSON in this repository
    is 10 -- the two published schemas -- and a real package is 5."""
    package = (PACKAGES / "gear-ja.json").read_text(encoding="utf-8")
    assert depth_of(package) <= 8
    assert MAX_DEPTH >= 64


# --- what a reader does with one ---------------------------------------------


def test_a_document_that_is_too_deep_is_refused_by_name() -> None:
    with pytest.raises(ContractError, match="nests more than"):
        parse(nested(MAX_DEPTH + 1), what="package", where="somewhere")


def test_the_refusal_says_nothing_in_it_ran() -> None:
    """The sentence a reader needs from a refusal about a hostile document."""
    with pytest.raises(ContractError) as refusal:
        parse(nested(MAX_DEPTH + 1), what="package", where="somewhere")
    assert "Nothing was parsed" in str(refusal.value)


def test_ordinary_bad_json_is_still_an_ordinary_refusal() -> None:
    with pytest.raises(ContractError, match="is not JSON"):
        parse("{oops", what="report", where="somewhere")


def test_a_document_at_the_limit_is_read() -> None:
    """The bound is `more than`, not `at least`. A limit that refused the
    document it names would be a limit nobody could satisfy."""
    assert parse(nested(MAX_DEPTH), what="package", where="somewhere") is not None


# --- the two surfaces --------------------------------------------------------


def test_the_package_reader_refuses_rather_than_raising_a_traceback(tmp_path: Path) -> None:
    """It reached the user as `RecursionError: maximum recursion depth exceeded
    while decoding a JSON array` -- a traceback, which reads as a bug in the
    tool rather than as an answer about their file."""
    from akashi.infrastructure.packages import load_package

    document = tmp_path / "deep.json"
    document.write_text(
        '{"contract":"tsumugi.context-package/1","items":[],"x":' + nested(100_000) + "}",
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="nests more than"):
        load_package(document)


def test_one_malformed_message_does_not_end_the_mcp_session() -> None:
    """The loop is written so that a client sending one bad line is not a client
    that has stopped talking. A `RecursionError` from `json.loads` left the
    generator and ended the process instead: stdout empty, no reply, no reason.

    This asserts the behaviour rather than one mechanism: the depth count and
    the `RecursionError` catch each hold it on their own, and removing either
    alone leaves this green. Removing both fails it, which is the shape of the
    claim -- the session survives a hostile message, however that is arranged.
    """
    from akashi.interfaces.mcp import PROTOCOL_VERSION, serve

    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    opening = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"x":'
    hostile = opening + nested(100_000) + "}}"
    ordinary = json.dumps(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"_meta": meta}}
    )

    out = io.StringIO()
    assert serve(io.StringIO(hostile + "\n" + ordinary + "\n"), out) == 0

    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert replies[0]["error"]["code"] == -32700
    assert "tools" in replies[1]["result"], "the session carried on"
