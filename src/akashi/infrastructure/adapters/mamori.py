"""The restorer akashi is handed when the answer came back pseudonymized.

ADR-0008: an answer generated from a protected prompt talks about
``<PERSON_001>``, and auditing it without putting the values back reports every
honest particular as fabricated. `mamori` is what puts them back, and this is
the four-line seam between them.

**It imports nothing.** `mamori`'s `PrivacySession.restore` returns a
`RestorationResult` rather than a string, and lifting `.text` off it needs no
knowledge of the class it came from. So this module is what the import-linter
contract permits to name `mamori` and does not need to: akashi installs and runs
without it, and a caller who has a session hands it over.

**And the port's own docstring was wrong about this.** It said `PrivacySession`
*"already satisfies it without knowing akashi exists, which is what makes the
adapter in v0.5 four lines long"*. It does not satisfy it -- the return type is
the whole difference, and it is the reason this file exists. The four lines were
right; the reason was not.

`Restorer` is `runtime_checkable`, which would not have caught it either:
`isinstance` on a `Protocol` checks that the method is *there*, not what it
returns, so a session passes and the call site gets an object where it expected
text. akashi then runs a regex over it and raises `TypeError: expected string or
bytes-like object` from inside `find_placeholders` -- a crash about a regular
expression, three layers from the mistake.

So the check is here, at the seam, where the message can name what went wrong.
"""

from __future__ import annotations

from typing import Protocol

from akashi.errors import ContractError

__all__ = ["MamoriRestorer", "RestoresText"]


class RestoresText(Protocol):
    """Anything whose ``restore`` hands back an object carrying ``.text``.

    Spelled as a shape rather than as `mamori.PrivacySession`, because that is
    all this adapter uses and requiring the class would make akashi need the
    package in order to describe the seam.
    """

    def restore(self, text: str) -> object: ...


class MamoriRestorer:
    """A `mamori` session, in the shape ADR-0008's port asks for.

    Handed protected text, returns the text with the real values in it. It
    cannot see the package, the evidence or the verdicts -- the port's signature
    is the guarantee, and this class does not widen it.
    """

    __slots__ = ("_session",)

    def __init__(self, session: RestoresText) -> None:
        self._session = session

    def restore(self, text: str) -> str:
        """``session.restore(text).text``, checked.

        A placeholder the session does not know is left in place rather than
        removed -- that is `mamori`'s behaviour and it is what the port asks
        for. akashi looks for residue again after restoration, so a restorer
        that silently dropped an unknown token would produce text that looks
        restored and is not, which is the one outcome worse than refusing.
        """
        result = self._session.restore(text)
        restored = getattr(result, "text", None)
        if not isinstance(restored, str):
            raise ContractError(
                f"the restorer returned {type(result).__name__} with no usable 'text'. "
                f"akashi's Restorer port hands back the restored string; a session that "
                f"returns a result object is wrapped by MamoriRestorer, and something "
                f"else needs its own adapter rather than being passed in raw."
            )
        return restored
