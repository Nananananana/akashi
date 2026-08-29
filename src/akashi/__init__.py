"""akashi -- local-first response auditing for generative AI.

Take the answer a model gave you and the context it was given, and separate what
the answer took from its evidence from what it produced on its own. No model
runs inside an audit, so the same inputs give the same report forever.

Nothing is built yet. See ``docs/proposals/0001-the-design.md`` for the design
and ``docs/adr/`` for the decisions behind it.
"""

from __future__ import annotations

from .errors import (
    AkashiError,
    ContractError,
    ProtectedResponseError,
    SegmentationError,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "AkashiError",
    "ContractError",
    "ProtectedResponseError",
    "SegmentationError",
    "__version__",
]
