"""The audit report, as a value.

ADR-0002 says the report is a document, and it will be: a versioned JSON
contract with a published schema, frozen once a second program has produced and
consumed one. That is v0.2. What is here is the value the serializer will
render, and it lives in the domain for the same reason ``ContextPackage`` does
-- the audit is a function of it, and the *format* is infrastructure's business.

The contract string says ``1-draft`` and will keep saying it until the freeze.
A consumer that sees ``1-draft`` should expect fields to move.

Three things on it are not negotiable, and they are ADR-0005:

``assessment.skipped``   what was not checked, each with the rule for it
``assessment.coverage``  the denominators, so a reader cannot assume a generous one
``assessment.limits``    what the method cannot do, on the artefact rather than in the docs

The artefact travels and the documentation does not, which is the whole reason
the third one is a field rather than a paragraph in a README.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .coverage import Assessment

__all__ = [
    "CONTRACT",
    "AuditReport",
    "Audited",
    "ReportProvenance",
    "content_hash",
    "report_id",
]

#: Not frozen. ADR-0002: the freeze happens once a second program has produced
#: and consumed a report, not once the calendar says v0.2.
CONTRACT = "akashi.audit-report/1-draft"


def content_hash(text: str) -> str:
    """``sha256:`` over the UTF-8 bytes of ``text``.

    Names the algorithm in the value rather than in a field beside it, so a
    reader holding the string alone can still check it.
    """
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


#: The separator between fields of the canonical form. A newline, because no
#: field may contain one -- a hash, a version and a pack name are all single
#: tokens -- and because a serialization somebody has to reimplement should be
#: readable when printed.
_FIELD = "\n"


def report_id(audited: Audited) -> str:
    """The id of a report, over exactly what determined it.

    Two runs over the same answer, the same package and the same akashi give one
    id. That is what makes ``recheck`` a check rather than a re-print, and it is
    why the canonical form is written out here rather than derived from a
    dataclass: anyone reimplementing it needs the field order and the separator,
    and ``dataclasses.astuple`` would silently change the answer the next time a
    field is added.

    **The pack set is in the hash and this is the part that is easy to miss.**
    Narrowing the packs changes the segmentation and therefore every count on
    the report; two audits that hashed the same either way could claim one id
    for different findings.

    **``created_at`` is not in it**, and neither is anything else that moves
    without the inputs moving. A hash that changes when nothing changed is a
    hash nobody can compare, which is the whole use.
    """
    canonical = _FIELD.join(
        [
            "akashi.audit-report/1",
            audited.response_hash,
            audited.package_id,
            audited.akashi_version,
            ",".join(audited.segmenters),
            ",".join(audited.extractors),
            ",".join(audited.packs),
        ]
    )
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True, slots=True)
class Audited:
    """What was audited, and by what.

    The segmenter and extractor names are here because every count on the
    report has them in its denominator (ADR-0009). A ``recheck`` that produced
    different numbers can then attribute the difference to something.
    """

    package_id: str = ""
    response_hash: str = ""
    response_length: int = 0
    segmenters: tuple[str, ...] = ()
    extractors: tuple[str, ...] = ()
    #: Every language pack that was loaded, by code. In the id because it
    #: decides the segmentation and therefore every count on the report.
    packs: tuple[str, ...] = ()
    akashi_version: str = ""


@dataclass(frozen=True, slots=True)
class ReportProvenance:
    """How the answer reached the auditor."""

    #: Who put the real values back. Empty when nobody did.
    restored_by: str = ""
    #: True when ``restored_by`` is the caller's word rather than something
    #: akashi watched happen (ADR-0013). The rendering says which.
    restoration_asserted: bool = False
    #: Who protected the package, from ``provenance.protection``.
    protection_by: str = ""
    #: How many candidates the package withheld, per rule. Context for the
    #: reader and never an explanation of a finding (ADR-0012).
    withheld: tuple[tuple[str, int], ...] = ()

    def describe_restoration(self) -> str:
        if not self.restored_by:
            return "not restored"
        if self.restoration_asserted:
            return f"asserted restored by {self.restored_by}; akashi did not verify it"
        return f"restored by {self.restored_by}"


@dataclass(frozen=True, slots=True)
class AuditReport:
    """One answer, audited against one package."""

    answer: str
    assessment: Assessment
    audited: Audited = field(default_factory=Audited)
    provenance: ReportProvenance = field(default_factory=ReportProvenance)
    contract: str = CONTRACT

    @property
    def report_id(self) -> str:
        """What this report is, by its inputs. See :func:`report_id`."""
        return report_id(self.audited)

    @property
    def has_findings(self) -> bool:
        return bool(self.assessment.findings)

    def summary(self) -> str:
        """One line, and it does not lead with the score.

        The score is the part a reader will take away whatever else is on the
        page, so what precedes it is what bounds it.
        """
        coverage = self.assessment.coverage
        share = self.assessment.grounded_share
        scored = "nothing checkable" if share is None else f"{share:.0%} grounded"
        return (
            f"{coverage.segments} segments, "
            f"{coverage.unbearing + coverage.unexamined} not checked, "
            f"{coverage.checked} particulars checked, {scored}"
        )
