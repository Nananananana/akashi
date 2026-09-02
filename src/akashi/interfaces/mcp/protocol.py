"""JSON-RPC 2.0 over stdio, on the standard library.

MCP's stdio transport is newline-delimited JSON: one object per line, requests
in on ``stdin``, responses out on ``stdout``. That is the whole framing, which
is why an agent-facing surface costs akashi no dependency -- and it could not
cost one: ADR-0001 says the domain depends on nothing, the import-linter
contract forbids `socket`, `http`, `urllib` and `asyncio`, and an MCP SDK would
bring all of it.

Three rules here are properties rather than style.

**Nothing on stdout that is not a response.** A stray ``print`` corrupts the
stream, and the client sees a parse error it cannot attribute to anything.
Diagnostics go to ``stderr``.

**The stream is UTF-8 in both directions, whatever the console is.** This is a
*document* channel, not prose for a reader: a `?` substituted for a character
the console cannot show is corruption in a protocol message, and akashi already
shipped that defect once on the report side. `utf8_reader` and `utf8_writer`
bind the encoding rather than trusting the locale.

**Strict parsing, and an unknown method is refused.** The input is JSON-RPC
from a client the user configured, and "the user configured it" is not a
security argument -- the *model* chooses the calls.
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import IO, Any, Final

__all__ = [
    "INTERNAL_ERROR",
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "MISSING_CLIENT_CAPABILITY",
    "PARSE_ERROR",
    "UNSUPPORTED_PROTOCOL_VERSION",
    "Request",
    "RpcError",
    "read_requests",
    "utf8_reader",
    "utf8_writer",
    "write_message",
]

#: JSON-RPC 2.0's own codes.
PARSE_ERROR: Final = -32700
INVALID_REQUEST: Final = -32600
METHOD_NOT_FOUND: Final = -32601
INVALID_PARAMS: Final = -32602
INTERNAL_ERROR: Final = -32603

#: MCP's, from the 2026-07-28 revision. The specification reserves -32020 to
#: -32099 for itself and says an implementation must not emit a code in that
#: range that the specification does not define, so these are copied rather
#: than chosen.
MISSING_CLIENT_CAPABILITY: Final = -32021
UNSUPPORTED_PROTOCOL_VERSION: Final = -32022


class RpcError(Exception):
    """An error with a JSON-RPC code, ready to be reported to the client."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True, slots=True)
class Request:
    """One incoming message."""

    method: str
    params: dict[str, Any]
    #: ``None`` for a notification, which takes no response.
    id: str | int | None = None

    @property
    def is_notification(self) -> bool:
        return self.id is None

    @property
    def meta(self) -> dict[str, Any]:
        """``params._meta``, which is where MCP puts protocol metadata now.

        The 2026-07-28 revision made the protocol stateless: there is no
        handshake and no session, so every request carries its own version and
        capabilities here. A client from before that sends none of it, which is
        how a server tells the two eras apart.
        """
        found = self.params.get("_meta")
        return found if isinstance(found, dict) else {}

    @property
    def protocol_version(self) -> str | None:
        """The revision this request says it speaks, or ``None``.

        ``None`` is not an error at this layer. It means a client from before
        the handshake was retired, and refusing it here would refuse most
        clients shipped today; the server decides what to do about that.
        """
        found = self.meta.get("io.modelcontextprotocol/protocolVersion")
        return found if isinstance(found, str) else None

    def text(self, name: str, *, required: bool = True) -> str:
        value = self.params.get(name)
        if value is None and not required:
            return ""
        if not isinstance(value, str):
            raise RpcError(
                INVALID_PARAMS,
                f"{name!r} must be a string"
                + ("" if name in self.params else "; it was not given at all"),
            )
        return value

    def mapping(self, name: str) -> dict[str, Any]:
        value = self.params.get(name)
        if not isinstance(value, dict):
            raise RpcError(INVALID_PARAMS, f"{name!r} must be a JSON object")
        return value


def utf8_reader(stream: IO[bytes] | None = None) -> IO[str]:
    """``stdin`` as UTF-8 text, whatever the console's encoding is."""
    return io.TextIOWrapper(stream or sys.stdin.buffer, encoding="utf-8", newline="")


def utf8_writer(stream: IO[bytes] | None = None) -> IO[str]:
    """``stdout`` as UTF-8 text, whatever the console's encoding is.

    ``errors`` is left strict on purpose. Everywhere else akashi prints, a
    character the console cannot show is replaced so that the audit survives
    (#75). Here the reader is a program: a `?` in a JSON-RPC message is
    corruption, and failing loudly beats handing a client a document that
    parses and says something else.
    """
    return io.TextIOWrapper(stream or sys.stdout.buffer, encoding="utf-8", newline="")


def read_requests(stream: IO[str]) -> Iterator[Request | RpcError]:
    """One request per line, until the stream ends.

    A line that is not a request comes back as an ``RpcError`` rather than
    raising, because the loop has to answer it and carry on: a client that
    sends one bad line is not a client that has stopped talking.
    """
    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as error:
            yield RpcError(PARSE_ERROR, f"not JSON: {error}")
            continue
        if not isinstance(message, dict):
            yield RpcError(INVALID_REQUEST, "a JSON-RPC message is an object")
            continue

        method = message.get("method")
        if not isinstance(method, str):
            yield RpcError(INVALID_REQUEST, "a request has a string 'method'")
            continue
        params = message.get("params")
        identifier = message.get("id")
        if identifier is not None and not isinstance(identifier, (str, int)):
            # `null` is a valid JSON-RPC id and MCP forbids it; anything other
            # than a string or a number is not an id at all.
            yield RpcError(INVALID_REQUEST, "an id is a string or a number, and never null")
            continue
        yield Request(
            method=method,
            params=params if isinstance(params, dict) else {},
            id=identifier,
        )


def write_message(stream: IO[str], message: dict[str, Any]) -> None:
    """One message, one line, flushed.

    ``ensure_ascii=False`` because the report carries the answer verbatim and
    escaping every Japanese character would triple the size of a message whose
    encoding is already settled. Flushed every time: a client is waiting on
    this line, and a buffer that holds it is a hang rather than a slow reply.
    """
    stream.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()
