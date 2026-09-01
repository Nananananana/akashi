"""Putting the real values back before anything is audited.

ADR-0008. The signature is the guarantee: a restorer is handed protected text
and returns the text with the real values in it. It cannot see the package, the
evidence or the verdicts, so it cannot influence what akashi finds -- only what
akashi is looking at.

A ``Protocol`` rather than a base class, so an implementer never imports this
module.

**It said ``mamori``'s ``PrivacySession`` already satisfies this, and it does
not.** That method returns a ``RestorationResult``, and the difference between
an object carrying ``.text`` and the text is the whole reason
``infrastructure/adapters/mamori.py`` exists. The adapter is four lines; the
claim about why was wrong.

``runtime_checkable`` would not have caught it. ``isinstance`` against a
``Protocol`` checks that the method is *present*, not what it returns, so a
session passes and the caller gets an object where it expected a string.
Nothing in akashi calls ``isinstance`` on this, which is the only reason the
marker has cost nothing so far -- the adapter checks the return value at the
seam instead, where the message can say what went wrong.
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
