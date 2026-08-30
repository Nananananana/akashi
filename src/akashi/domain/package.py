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
    ``False`` to match: ``reversible=True`` carries the meaning *this can be
    restored, so an unresolved citation may be reported as unsupported*, and
    when that is wrong the failure is silent -- honest quotations reported as
    fabrications. The cost of a wrong default is asymmetric, so the default sits
    on the side that cannot be restored. Do not flip it back because the
    optimistic value reads better.

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

    @property
    def is_protected(self) -> bool:
        return self.protection is not None
