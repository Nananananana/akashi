"""The version, alone in a module.

Read by `akashi/__init__.py`, by the CLI and by `doctor`. Alone because
`__init__` re-exports the one-call API, which reaches the application layer:
anything importing `akashi` for the version would then pull the whole stack --
and `infrastructure` importing `akashi` for it made a cycle that the layer
contract caught.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0.dev0"
