"""Reading a JSON document somebody else wrote.

Every document akashi reads -- a ContextPackage, an archived report, an in-toto
Statement, a line of JSON-RPC -- came from outside. So the parser is a surface,
and this is the one place that says what akashi does when a document is shaped
to break it rather than to be read.

**Depth is checked before parsing, not after.** `json.loads` recurses, and a
deeply nested document raises `RecursionError` -- which is not a
`json.JSONDecodeError`, so it went past every reader here and reached the user
as a traceback. On the MCP surface it was worse: the exception left the request
loop and **killed the server**, which is exactly what that loop is written not
to do.

Catching `RecursionError` would fix both and is not enough. The limit it depends
on is a process setting somebody can change, the C stack underneath it is not
the same on every build, and where the stack runs out first the process does not
raise at all. A count of brackets is arithmetic: it cannot exhaust anything, it
gives the same answer everywhere, and an audit is reproducible (ADR-0003).
"""

from __future__ import annotations

import json
from typing import Any

from akashi.errors import ContractError

__all__ = ["MAX_DEPTH", "depth_of", "parse"]

#: How deeply a document akashi reads may nest.
#:
#: Set the way a floor is: measured, then left far above the measurement. The
#: deepest JSON in this repository is **10** -- the two published schemas -- and
#: a real ContextPackage or report is **5**. A document at 64 is six times the
#: deepest thing akashi has ever written and thirteen times anything it reads.
#:
#: It is a bound on the *document*, not on the parser. Refusing at 64 says
#: "this is not a package"; catching a `RecursionError` would say "this machine
#: ran out of stack", which is a different sentence and true in fewer places.
MAX_DEPTH = 64


def depth_of(raw: str, limit: int | None = None) -> int:
    """The deepest nesting in ``raw``, counted rather than parsed.

    One pass over the characters, tracking whether it is inside a string and
    whether the last character was a backslash -- brackets inside a string are
    text. Stops early at ``limit``, so a document written to be expensive costs
    the prefix and not the whole file.
    """
    depth = deepest = 0
    inside_string = escaped = False
    for character in raw:
        if inside_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                inside_string = False
            continue
        if character == '"':
            inside_string = True
        elif character in "[{":
            depth += 1
            deepest = max(deepest, depth)
            if limit is not None and deepest > limit:
                return deepest
        elif character in "]}":
            depth -= 1
    return deepest


def parse(raw: str, *, what: str, where: str) -> Any:
    """``raw`` as JSON, or a refusal that names the document and the reason.

    ``what`` is the kind of document ("package", "report") and ``where`` is
    where it came from, because a caller holding three files needs to know
    which one this is about.
    """
    deepest = depth_of(raw, limit=MAX_DEPTH)
    if deepest > MAX_DEPTH:
        raise ContractError(
            f"the {what} at {where} nests more than {MAX_DEPTH} deep. akashi reads "
            f"documents, and a document shaped to exhaust a parser is not one -- the "
            f"deepest real package is 5 and the published schemas are 10. Nothing was "
            f"parsed, so nothing in it ran."
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ContractError(f"the {what} at {where} is not JSON: {error}") from error
    except RecursionError as error:
        # Reachable when the interpreter's own limit is lower than MAX_DEPTH --
        # a caller may have set one. Named rather than left as a traceback, for
        # the same reason as everything else here.
        raise ContractError(
            f"the {what} at {where} is nested deeper than this interpreter's recursion "
            f"limit, which is below akashi's own limit of {MAX_DEPTH}."
        ) from error
