"""The first stage: decide whether this answer can be audited at all.

ADR-0008. It runs before segmentation, on both the answer and the package, and
nothing past it has to think about redaction again.

Three outcomes, and the middle one is the whole reason the stage exists.

**Audit it.** Nothing was protected, or something was and a restorer put the
real values back. The rest of the pipeline gets plain text.

**Refuse.** The answer still carries placeholders and nothing can restore them.
Auditing it would mark every honest particular as floating -- an answer that
quoted its sources perfectly, reported as fabricated in full, by the component
whose whole job is to be believed. A refusal is recoverable; that is not.

**Audit it, and mark what cannot be checked.** The protection was
*irreversible*: a value was masked or blocked rather than pseudonymized, and no
restorer can bring it back. Those segments are ``unverifiable`` and never
``floating``. Unknown and false are different, and an auditor that conflates
them teaches its user to ignore it.

There is a fourth path and it is the caller's, not akashi's: ``restored_by``
lets a caller who has already put the values back say so. akashi cannot check
that claim -- ``mamori`` can substitute realistic surrogates, so restored text
and unrestored text look identical -- and it does not pretend to. The claim
goes on the report as a claim, attributed to whoever made it (ADR-0013).
"""

from __future__ import annotations

from dataclasses import dataclass

from akashi.domain.package import ContextPackage
from akashi.domain.protection import PlaceholderResidue, find_placeholders
from akashi.errors import ProtectedResponseError
from akashi.ports import Restorer

__all__ = ["Admission", "admit"]


@dataclass(frozen=True, slots=True)
class Admission:
    """A response cleared for audit, and what had to happen to clear it."""

    #: What the rest of the pipeline reads. The restored text when a restorer
    #: ran, and the original otherwise.
    answer: str
    #: Who restored it, for the report's provenance. Empty when nobody did.
    restored_by: str = ""
    #: True when ``restored_by`` is the caller's word rather than something
    #: akashi watched happen. The report says which (ADR-0013).
    asserted: bool = False
    #: Placeholder-shaped tokens still present after restoration. Non-empty
    #: only on the irreversible path, where they are what makes the affected
    #: segments ``unverifiable`` rather than floating.
    residue: tuple[PlaceholderResidue, ...] = ()

    @property
    def was_restored(self) -> bool:
        return bool(self.restored_by)

    def describe_restoration(self) -> str:
        if not self.restored_by:
            return "not restored"
        if self.asserted:
            return f"asserted restored by {self.restored_by}; akashi did not verify it"
        return f"restored by {self.restored_by}"

    @property
    def is_partly_unverifiable(self) -> bool:
        return bool(self.residue)


def admit(
    answer: str,
    package: ContextPackage,
    restorer: Restorer | None = None,
    *,
    restored_by: str = "",
) -> Admission:
    """Clear ``answer`` for audit, restore it, or refuse.

    ``restored_by`` is the caller asserting that they put the values back
    themselves, and naming who did. akashi cannot verify it and records it as
    an assertion (ADR-0013). It is recorded whatever the package says about
    protection, because the package does not always know: a redactor that ran
    *after* the package was built cannot have been declared in it, and that is
    exactly when the caller's word is the only record there is. Passing it
    *and* a restorer is refused, because two answers
    to "who restored this" is one too many.

    Raises ``ProtectedResponseError`` when the answer cannot be audited
    honestly. The message names what was found and what would be needed, so
    that a caller can act on it rather than only know that something is wrong.
    """
    if restorer is not None and restored_by:
        raise ValueError(
            "admit() was given both a restorer and a restored_by assertion. One of the "
            "two is wrong, and guessing which would put the wrong name on the report."
        )
    residue = find_placeholders(answer)
    protection = package.protection

    if protection is None and not residue:
        # Nothing to restore and nothing to refuse -- but the caller's word is
        # still the caller's word. This used to drop `restored_by` on the
        # floor, on the reasoning that an assertion about an unprotected
        # package is pointless. It is not: a redactor that ran after the
        # package was built cannot appear in `provenance.protection`, so this
        # branch is where a real restoration claim arrives, and the report came
        # back byte-identical to one made with no claim at all.
        #
        # Recording it costs nothing and hiding it cost the reader everything
        # the flag was for. akashi does not check the claim either way -- a
        # surrogate is designed to be indistinguishable from a real value -- so
        # it goes on the report attributed to whoever made it.
        return Admission(
            answer=answer,
            restored_by=restored_by,
            asserted=bool(restored_by),
        )

    if protection is None:
        # The package said nothing about a redactor, and the answer is full of
        # its output. Something in the pipeline protected the prompt without
        # recording it, and continuing would report honest particulars as
        # fabricated. This is the case ``provenance.protection`` exists to make
        # unnecessary, and it stays a refusal for the pipelines that do not
        # set it.
        raise ProtectedResponseError(
            f"the answer carries {len(residue)} placeholder-shaped token"
            f"{'' if len(residue) == 1 else 's'} "
            f"({_examples(residue)}) and the package declares no protection"
            f"{' at all' if not package.declares_protection else ''}. "
            f"Auditing it would report every honest particular as floating. "
            f"Restore the answer before auditing it, or pass a restorer."
        )

    if not protection.reversible:
        # Masked or blocked rather than pseudonymized. No restorer can help,
        # and akashi audits what it can while saying what it cannot.
        return Admission(answer=answer, residue=residue)

    if restored_by:
        # The caller's word. akashi cannot check it -- a surrogate is designed
        # to be indistinguishable from a real value -- so it goes on the report
        # attributed to them rather than being quietly absorbed (ADR-0013).
        return Admission(answer=answer, restored_by=restored_by, asserted=True, residue=residue)

    if restorer is None:
        raise ProtectedResponseError(
            f"the package was protected by {protection.by} and no restorer was given. "
            f"akashi does not audit pseudonymized text: every honest particular would "
            f"be reported floating. An answer with no placeholders in it is not evidence "
            f"of restoration -- a surrogate is designed to look like a real value. Pass a "
            f"restorer for scope {protection.scope!r}, or pass restored_by=... to assert "
            f"that you restored it yourself."
        )

    restored = restorer.restore(answer)
    remaining = find_placeholders(restored)
    if len(remaining) == len(residue) and residue:
        raise ProtectedResponseError(
            f"the restorer for {protection.by} put nothing back: "
            f"{_examples(remaining)} are still there. A restorer for the wrong scope "
            f"returns its input unchanged, and auditing that is the failure this check "
            f"exists to stop."
        )
    return Admission(answer=restored, restored_by=protection.by, residue=remaining)


def _examples(residue: tuple[PlaceholderResidue, ...], limit: int = 3) -> str:
    shown = ", ".join(entry.token for entry in residue[:limit])
    return f"{shown}, ..." if len(residue) > limit else shown
