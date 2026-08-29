"""The interfaces akashi asks the outside world to satisfy.

There is exactly one, and it is optional. akashi audits plain text with nothing
installed; a caller whose answer still carries placeholders either restores it
themselves or hands akashi something that can (ADR-0008).

An implementer never imports the port. It is a ``Protocol``, structurally
checked, so that satisfying it costs a matching method and not a dependency.
"""

from __future__ import annotations

from .restorer import Restorer

__all__ = ["Restorer"]
