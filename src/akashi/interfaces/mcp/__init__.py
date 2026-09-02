"""The agent-facing surface: MCP over stdio, on the standard library.

Beside `interfaces/cli/`, with the same permission to import everything below
it and nothing above. Both are thin shells over `akashi.application`; a
behaviour available in one and not the other is a defect.
"""

from __future__ import annotations

from .server import PROTOCOL_VERSION, TOOLS, McpServer, serve

__all__ = ["PROTOCOL_VERSION", "TOOLS", "McpServer", "serve"]
