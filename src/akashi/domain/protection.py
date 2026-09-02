"""Recognising text that has been through a redactor.

ADR-0008. An answer generated while its prompt was pseudonymized talks about
``<PERSON_001>`` and ``<AMOUNT_003>``. Audit that text and every particular
akashi extracts is a placeholder, no placeholder is in the source documents,
and the report comes back with everything floating -- a perfect score for a
fabrication detector, and complete nonsense. The user is being told that an
honest answer is a pack of lies, by the component whose whole job is to be
believed.

So this module exists to make that unreachable rather than unlikely.

**akashi knows what a placeholder looks like without importing `mamori`.** That
is a small amount of duplicated knowledge, and it is the price of the sibling
being optional (ADR-0008). A seam test against the real redactor is what keeps
the pattern from rotting.

**And the pattern is not the main signal.** `mamori` can also substitute
*surrogates* -- realistic fake values rather than obvious tokens -- and a
surrogate is by design indistinguishable from a real name. Nothing here will
ever see one. The reliable signal is ``provenance.protection`` on the package,
which exists precisely so a downstream consumer can tell; the pattern below
catches the case where the package says nothing and the answer says everything.

**What this cannot decide, and why it stays that way (#52).**
``<PERSON_001>`` is a string a person can type. Seeing one, akashi cannot tell a
token `mamori` minted from one an author wrote in a quotation, and both ways of
being wrong are silent: an honest quotation reported as unrestored residue, or
a real placeholder audited against as ordinary text.

`mamori.protection-scope/1` carries a ``placeholders`` enumeration that would
settle it -- every token it minted, by design recoverable from the protected
text with one regular expression, so listing them discloses nothing. **It
cannot reach akashi.** akashi reads one document, and `tsumugi`'s
``provenance.protection`` carries ``by``, ``scope`` and ``reversible`` with
``additionalProperties: false``. Version 1 of that contract is now closed
(ADR-0016), so the field cannot be added to it. The enumeration exists, in a
record akashi is never handed.

So akashi says it cannot tell, rather than guessing, and the refusal in
``application/admit.py`` names what would settle it. That is the honest shape
and not a placeholder for a better one: taking `mamori`'s record as a second
input would make akashi read a second foreign contract -- a vendored copy, a
drift job, a conformance suite, a seam test (ADR-0007) -- to decide a question
whose answer would still be somebody's word.

**And when somebody does build it, the branch is on the contract identifier.**
#52 proposed branching on ``mode``, because ``placeholders`` was said to be
absent under ``surrogate``. `mamori`'s contract now says the opposite twice:
``placeholders`` is **required**, and ``mode`` is *"a summary of how values were
substituted, **not a switch selecting which array to read**"* -- one document
routinely carries both. The signal is
``mamori.protection-scope/1`` versus ``mamori.protection-scope/1+surrogate``,
which a token-only consumer refuses through the check it already has. Reading
``mode`` as a switch is the exact misreading that contract is worded to prevent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .span import Span

__all__ = ["PlaceholderResidue", "find_placeholders"]

#: ``<PERSON_001>``, ``[PERSON_001]``, ``{PERSON_001}``. All three brackets,
#: because `mamori` emits angle brackets by default and the other two for
#: payloads that would eat them -- and akashi is reading whatever came back,
#: not choosing what went out.
#:
#: The shape is distinctive: a screaming-snake type name, an underscore, digits,
#: inside brackets. A genuine answer can contain one, and the cost of that is a
#: refusal on an unprotected package -- recoverable, unlike the opposite error.
_PLACEHOLDER = re.compile(r"[<\[{]([A-Z][A-Z0-9_]{0,62})_(\d{1,6})[>\]}]")


@dataclass(frozen=True, slots=True)
class PlaceholderResidue:
    """One placeholder-shaped token left in a text, and where."""

    token: str
    entity_type: str
    span: Span

    def describe(self) -> str:
        return f"{self.token} at {self.span.describe()}"


def find_placeholders(text: str) -> tuple[PlaceholderResidue, ...]:
    """Every placeholder-shaped token in ``text``, in order.

    Ordered by position and deduplicated by nothing: a placeholder appearing
    three times is three pieces of evidence that this text was not restored,
    and collapsing them would understate how much of the answer is affected.
    """
    return tuple(
        PlaceholderResidue(
            token=match.group(0),
            entity_type=match.group(1),
            span=Span(*match.span()),
        )
        for match in _PLACEHOLDER.finditer(text)
    )
