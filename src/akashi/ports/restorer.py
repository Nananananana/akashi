"""Putting the real values back before anything is audited.

ADR-0008. The signature is the guarantee: a restorer is handed protected text
and returns the text with the real values in it. It cannot see the package, the
evidence or the verdicts, so it cannot influence what akashi finds -- only what
akashi is looking at.

A ``Protocol`` rather than a base class, so an implementer never imports this
module. ``mamori``'s ``PrivacySession`` already satisfies it without knowing
akashi exists, which is what makes the adapter in v0.5 four lines long.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["Restorer"]


@runtime_checkable
class Restorer(Protocol):
    """Something that can put real values back into pseudonymized text."""

    def restore(self, text: str) -> str:
        """Return ``text`` with its placeholders replaced by the real values.

        A placeholder this restorer does not know about is left as it is rather
        than removed. akashi checks for residue *after* restoration too: a
        restorer that silently dropped an unknown placeholder would produce
        text that looks restored and is not, which is the one outcome worse
        than refusing.
        """
        ...
