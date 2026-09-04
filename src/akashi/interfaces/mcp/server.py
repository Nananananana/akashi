"""The agent-facing surface. Same use cases as the CLI, no new decisions.

The thing that most wants an audit is not a person at a terminal. It is the
assistant that just produced the answer, holding the package it was given, able
to check itself before handing the answer on -- and it cannot pause to have
somebody run a CLI. That consumer needs to call, get structure back, and
continue.

Three constraints make this safe to run inside somebody else's agent loop, and
they are `tsumugi`'s ADR-0012 applied to akashi rather than re-derived:

**Read-only, and it takes no paths.** Every tool takes text and objects. akashi's
CLI happily reads a file the user named, because the user is the person holding
the files; here the *model* chooses the arguments. A tool that accepted a path
would be a file-read primitive with an audit report as the exfiltration channel,
since a report quotes the answer verbatim. Nothing here writes anything either.

**The whole report, including what was not checked.** An agent that cannot see
the edge of the audit has the same problem as a person who cannot (ADR-0005).
`structuredContent` carries the report as data; the text block carries the same
thing rendered, because a model reads text.

**The same application layer as the CLI.** Both are thin shells over
`akashi.application`. A behaviour available in one and not the other is a
defect, and nothing in this module decides anything an audit decides.
"""

from __future__ import annotations

import json
from typing import IO, Any, Final

from akashi.application import audit as run_audit
from akashi.application.recheck import recheck as run_recheck
from akashi.domain.matching import DEFAULT_MATCHER, Matcher, matcher_named
from akashi.errors import AkashiError
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import read_package
from akashi.infrastructure.packages.plain import package_from_contexts
from akashi.infrastructure.rendering import as_text, explain_segment
from akashi.infrastructure.reports import read_report
from akashi.version import __version__

from .protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    UNSUPPORTED_PROTOCOL_VERSION,
    Request,
    RpcError,
    read_requests,
    utf8_reader,
    utf8_writer,
    write_message,
)

__all__ = ["LEGACY_PROTOCOL_VERSION", "PROTOCOL_VERSION", "TOOLS", "McpServer", "serve"]

#: The revision this server speaks.
#:
#: 2026-07-28 retired the `initialize` handshake and the connection-scoped
#: session: the protocol is stateless, every request carries its own version and
#: capabilities in `_meta`, and every result names its `resultType`.
#:
#: <https://modelcontextprotocol.io/specification/2026-07-28>
PROTOCOL_VERSION: Final = "2026-07-28"

#: What a client from before that asks for, and still gets.
#:
#: The specification's own compatibility matrix says a legacy client against a
#: modern-only server **fails**, with no fall-forward: the client has no way to
#: learn what went wrong. Most clients shipped today are legacy, so refusing
#: them would make this surface correct and unusable. A dual-era server is
#: explicitly allowed, and for a stateless read-only server it costs one branch.
LEGACY_PROTOCOL_VERSION: Final = "2025-06-18"

META_SERVER_INFO: Final = "io.modelcontextprotocol/serverInfo"

SERVER_INFO: Final[dict[str, str]] = {"name": "akashi", "version": __version__}

INSTRUCTIONS: Final = (
    "Audit an answer against the ContextPackage it was generated from. akashi "
    "compares strings: it reports which load-bearing particulars of the answer "
    "are in the text that was sent, where each was found, and -- with equal "
    "prominence -- everything it did not check. It does not decide whether the "
    "answer is true, and a 'floating' particular means 'not in the text you "
    "sent', never 'false'. Read `unchecked`, `coverage` and `limits` before "
    "reading the score."
)

_PACKAGE_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "description": (
        "A tsumugi.context-package/1 document, inline. akashi reads no paths: "
        "pass the package itself."
    ),
}

TOOLS: Final[list[dict[str, Any]]] = [
    {
        "name": "audit",
        "title": "Audit an answer against the context it was given",
        "description": (
            "Returns an akashi.audit-report/1-draft: every particular of the answer "
            "with where it was found or that it was found nowhere, what was not "
            "checked and why, the denominators, and what the method does not "
            "establish. A particular reported 'floating' is not in the text that was "
            "sent; that is a statement about strings, not about truth."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "The answer to audit."},
                "package": _PACKAGE_SCHEMA,
                "contexts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "The retrieved passages, as plain strings, for a caller with no "
                        "ContextPackage -- the shape every RAG evaluation library uses. "
                        "Give this or 'package'. No provenance is invented: offsets "
                        "index the strings you passed, and the report says so."
                    ),
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Language pack codes to restrict to, e.g. ['ja']. Omitted, all "
                        "shipped packs are used. The pack set is in the report's id, "
                        "because it decides every count."
                    ),
                },
                "restored_by": {
                    "type": "string",
                    "description": (
                        "Assert that you restored a pseudonymized answer yourself, "
                        "naming who did. akashi cannot verify it and the report says "
                        "so."
                    ),
                },
                "matcher": {
                    "type": "string",
                    "description": (
                        "Which strings count as the same string: 'normalized' (the "
                        "default, and what every published measurement used) folds the "
                        "text and lets a particular's internal spacing vary; 'exact' "
                        "applies the same boundary rules with no spacing tolerance. The "
                        "name is on the report and in its id, because it changes every "
                        "count."
                    ),
                },
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    },
    {
        "name": "recheck",
        "title": "Re-derive a report and say whether it still holds",
        "description": (
            "Takes a report somebody produced, re-derives it from the inputs the "
            "report names, and reports whether the report_id matches. This is the "
            "difference between an audit and an opinion: a report that cannot be "
            "re-derived is a claim about a run nobody can repeat."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "report": {
                    "type": "object",
                    "description": "The archived report, inline. An in-toto statement is "
                    "read through its predicate.",
                },
                "answer": {"type": "string", "description": "The answer it was made over."},
                "package": _PACKAGE_SCHEMA,
                "restored_by": {"type": "string"},
            },
            "required": ["report", "answer", "package"],
            "additionalProperties": False,
        },
    },
    {
        "name": "explain",
        "title": "One finding, in full, from the report alone",
        "description": (
            "Everything about one segment: the sentence, every particular, where each "
            "resolved, what the source says instead, and what the verdict means. It "
            "reads the report and nothing else -- no package and no re-audit -- and "
            "says which offsets a reader holding only the report can check."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "report": {"type": "object"},
                "segment_id": {"type": "string", "description": "e.g. 'seg_004'."},
                "particular": {
                    "type": "string",
                    "description": "Narrow to one particular by its text.",
                },
            },
            "required": ["report", "segment_id"],
            "additionalProperties": False,
        },
    },
]


class McpServer:
    """One request in, one response out. Holds nothing between them.

    Deliberately stateless beyond the streams, which is what the 2026-07-28
    revision requires anyway: a stdio process is not a session, and a client may
    interleave unrelated requests on it.
    """

    __slots__ = ("_out",)

    def __init__(self, out: IO[str]) -> None:
        self._out = out

    # --- dispatch ------------------------------------------------------------

    def handle(self, request: Request) -> dict[str, Any] | None:
        """The result for one request, or ``None`` for a notification."""
        if request.is_notification:
            # Legacy clients send `notifications/initialized`, and the modern
            # protocol has no handshake to acknowledge. Either way a
            # notification takes no response, and answering one is a protocol
            # error rather than a courtesy.
            return None

        version = request.protocol_version
        if version is not None and version not in {PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION}:
            raise RpcError(
                UNSUPPORTED_PROTOCOL_VERSION,
                "Unsupported protocol version",
                {"supported": [PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION], "requested": version},
            )

        if request.method == "server/discover":
            return self._discover()
        if request.method == "initialize":
            return self._initialize(request)
        if request.method == "tools/list":
            return self._complete({"tools": TOOLS})
        if request.method == "tools/call":
            return self._call(request)
        raise RpcError(METHOD_NOT_FOUND, f"unknown method {request.method!r}")

    def _discover(self) -> dict[str, Any]:
        return self._complete(
            {
                "supportedVersions": [PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION],
                "capabilities": {"tools": {}},
                "instructions": INSTRUCTIONS,
            }
        )

    def _initialize(self, request: Request) -> dict[str, Any]:
        """A client from before the handshake was retired.

        It is answered with the version it asked for when that is one this
        server speaks, because the legacy handshake *is* a negotiation and
        telling a client it is speaking a revision it does not know is worse
        than agreeing to the one it named.
        """
        asked = request.params.get("protocolVersion")
        agreed = (
            asked
            if asked in {PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION}
            else (LEGACY_PROTOCOL_VERSION)
        )
        return self._complete(
            {
                "protocolVersion": agreed,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            }
        )

    def _call(self, request: Request) -> dict[str, Any]:
        name = request.params.get("name")
        arguments = request.params.get("arguments")
        if not isinstance(name, str):
            raise RpcError(INVALID_PARAMS, "'name' must be the name of a tool")
        if not isinstance(arguments, dict):
            arguments = {}

        tool = Request(method=name, params=arguments, id=request.id)
        try:
            if name == "audit":
                return self._tool(*self._audit(tool))
            if name == "recheck":
                return self._tool(*self._recheck(tool))
            if name == "explain":
                text = self._explain(tool)
                return self._tool(text, None)
        except AkashiError as refusal:
            # A refusal is an answer akashi can give, and a model can act on it:
            # "the package declares no protection and the answer is full of
            # placeholders" tells it what to fix. `isError` reports it to the
            # model rather than to the client's error handling, which is what
            # the specification asks for (tool execution error, not protocol
            # error).
            return self._tool(f"akashi refused: {refusal}", None, is_error=True)
        raise RpcError(METHOD_NOT_FOUND, f"unknown tool {name!r}")

    # --- the tools -----------------------------------------------------------

    def _audit(self, tool: Request) -> tuple[str, dict[str, Any]]:
        report = run_audit(
            tool.text("answer"),
            self._package(tool),
            self._packs(tool),
            restored_by=tool.text("restored_by", required=False),
            akashi_version=__version__,
            matcher=self._matcher(tool),
        )
        return as_text(report), report.to_dict()

    def _recheck(self, tool: Request) -> tuple[str, dict[str, Any]]:
        result = run_recheck(
            read_report(tool.mapping("report")),
            tool.text("answer"),
            read_package(tool.mapping("package")),
            self._packs(tool),
            restored_by=tool.text("restored_by", required=False),
            akashi_version=__version__,
        )
        body = {
            "archived_id": result.archived_id,
            "rederived_id": result.rederived_id,
            "matches": result.matches,
            "version_differs": result.version_differs,
            "archived_version": result.archived_version,
            "rederived_version": result.rederived_version,
            "differences": list(result.differences),
        }
        return result.describe(), body

    def _explain(self, tool: Request) -> str:
        return explain_segment(
            read_report(tool.mapping("report")),
            tool.text("segment_id"),
            particular=tool.text("particular", required=False) or None,
        )

    def _package(self, tool: Request) -> Any:
        """A ContextPackage, or one built from the strings a caller has.

        Almost nobody outside this family holds a ContextPackage, and asking
        them to build one before they can try akashi is the barrier rather than
        the audit.
        """
        contexts = tool.params.get("contexts")
        if contexts is not None:
            if not isinstance(contexts, list) or not all(isinstance(x, str) for x in contexts):
                raise RpcError(INVALID_PARAMS, "'contexts' is a list of strings")
            try:
                return package_from_contexts(contexts, tool.text("question", required=False))
            except AkashiError as refusal:
                raise RpcError(INVALID_PARAMS, str(refusal)) from refusal
        if "package" not in tool.params:
            raise RpcError(INVALID_PARAMS, "give either 'package' or 'contexts'")
        return read_package(tool.mapping("package"))

    def _matcher(self, tool: Request) -> Matcher:
        name = tool.text("matcher", required=False)
        if not name:
            return DEFAULT_MATCHER
        try:
            return matcher_named(name)
        except ValueError as error:
            raise RpcError(INVALID_PARAMS, str(error)) from error

    def _packs(self, tool: Request) -> tuple[Any, ...]:
        codes = tool.params.get("languages")
        if not codes:
            return DEFAULT
        if not isinstance(codes, list) or not all(isinstance(one, str) for one in codes):
            raise RpcError(INVALID_PARAMS, "'languages' is a list of pack codes")
        return packs(*codes)

    # --- shaping a reply -----------------------------------------------------

    def _complete(self, body: dict[str, Any]) -> dict[str, Any]:
        """Every result names its type and identifies the server.

        `resultType` is required by 2026-07-28 and absent means `complete` to a
        client reading an older server, so sending it is free in both
        directions.
        """
        return {"resultType": "complete", **body, "_meta": {META_SERVER_INFO: SERVER_INFO}}

    def _tool(
        self, text: str, structured: dict[str, Any] | None, *, is_error: bool = False
    ) -> dict[str, Any]:
        """A tool result, with the same thing twice on purpose.

        `structuredContent` is for the client, which can validate and index it.
        The text block is for the model, which reads text -- and the
        specification asks a tool returning structured content to include the
        serialized JSON as text anyway, for clients that predate the field.

        The text is the *rendered* report rather than the JSON, because the
        rendering leads with what was not checked (ADR-0005) and the raw
        document does not read in that order to a model skimming it.
        """
        body: dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": is_error}
        if structured is not None:
            body["structuredContent"] = structured
            body["content"].append(
                {"type": "text", "text": json.dumps(structured, ensure_ascii=False)}
            )
        return self._complete(body)


def serve(stream_in: IO[str] | None = None, stream_out: IO[str] | None = None) -> int:
    """Read requests until the stream ends. Returns an exit code.

    Nothing is printed that is not a response. A traceback on stdout would
    corrupt the stream and the client would report a parse error it cannot
    attribute to anything, so an unexpected exception becomes an internal error
    with the same id the request had.
    """
    reader = stream_in if stream_in is not None else utf8_reader()
    writer = stream_out if stream_out is not None else utf8_writer()
    server = McpServer(writer)

    for message in read_requests(reader):
        if isinstance(message, RpcError):
            write_message(writer, _error(None, message))
            continue
        try:
            result = server.handle(message)
        except RpcError as error:
            write_message(writer, _error(message.id, error))
            continue
        except Exception as error:
            write_message(
                writer,
                _error(message.id, RpcError(INTERNAL_ERROR, f"{type(error).__name__}: {error}")),
            )
            continue
        if result is not None:
            write_message(writer, {"jsonrpc": "2.0", "id": message.id, "result": result})
    return 0


def _error(identifier: str | int | None, error: RpcError) -> dict[str, Any]:
    body: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        body["data"] = error.data
    return {"jsonrpc": "2.0", "id": identifier, "error": body}
