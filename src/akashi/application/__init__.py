"""The use cases. Thin, and deciding nothing a verdict depends on.

Everything a report asserts is decided in ``domain``. What lives here is the
order the stages run in, the refusals that stop them, and the joining of the
domain's assessment to the package it was made against.
"""

from __future__ import annotations

from .admit import Admission, admit
from .audit import audit

__all__ = ["Admission", "admit", "audit"]
