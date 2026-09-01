"""What was sent, as a value.

The *parsing* of a ContextPackage lives in ``infrastructure/packages`` -- JSON
is a format and formats are infrastructure's business. What is here is the
thing the parsing produces, because the audit is a function of it and the
domain may not reach upwards to find out what it is working on.

Deliberately smaller than the contract. The budget, the instructions and the
selection scores are real fields akashi has no use for, and a value object that
carried them would be a second place for somebody else's contract to drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evidence import Evidence

__all__ = ["ContextPackage", "Protection"]


@dataclass(frozen=True, slots=True)
class Protection:
    """What a redactor did to this package before it was sent.

    ``reversible`` is the field ADR-0008 turns on. A pseudonymized package can
    be restored and then audited; a masked one cannot, and the segments it
    touched are ``unverifiable`` rather than ``floating`` -- unknown and false
    are different, and an auditor that conflates them teaches its user to
    ignore it.

    **The default of ``False`` is agreed across the seam and is not an
    oversight.** ``tsumugi`` defaulted it to ``True`` and has settled on
    ``False`` to match (its ADR-0020): ``reversible=True`` carries the meaning
    *this can be restored, so an unresolved citation may be reported as
    unsupported*, and when that is wrong the failure is silent -- honest
    quotations reported as fabrications. The cost of a wrong default is
    asymmetric, so it sits on the side that cannot be restored.

    The optimistic default was not merely risky in principle. ``mamori``'s
    ``PrivacyPolicy`` defaults its action to ``BLOCK``, and a blocked value is
    gone -- so against the redactor this seam is actually pointed at,
    ``reversible=True`` was wrong rather than hopeful. Do not flip it back
    because the optimistic value reads better.

    Reaching this default at all means constructing a ``Protection`` rather than
    reading one: the reader requires all three fields and refuses a block that
    omits any (the contract requires them too).
    """

    by: str
    scope: str = ""
    reversible: bool = False


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """The document that says what a model was given for one question."""

    contract: str
    package_id: str = ""
    query: str = ""
    evidence: Evidence = field(default_factory=Evidence)
    protection: Protection | None = None
    #: False when the package said nothing about protection at all. Absent is
    #: not the same as ``null``: one is a package that did not tell akashi, and
    #: the other is a package that told akashi it was not protected. ADR-0008
    #: refuses on the first and proceeds on the second.
    declares_protection: bool = False
    producer_version: str = ""
    providers: tuple[str, ...] = ()
    corpus_state: str = ""
    #: Dotted paths to fields the contract does not list, in the order found.
    #:
    #: akashi reads the package anyway -- a field it does not know is unknown,
    #: not wrong, and the same distinction ADR-0008 draws between *unverifiable*
    #: and *floating* applies to the document as much as to a particular. But
    #: `tsumugi.context-package/1` is closed and every object in it sets
    #: ``additionalProperties: false``, so a package carrying one of these does
    #: not conform, and a reader who is told nothing cannot tell that the audit
    #: was performed on it. Carried here so the report can say so.
    unrecognised: tuple[str, ...] = ()

    @property
    def is_protected(self) -> bool:
        return self.protection is not None
