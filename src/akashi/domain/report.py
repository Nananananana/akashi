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
from typing import Any

from .coverage import Assessment
from .verdict import CheckedParticular, CheckedSegment

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

    **The pack set and the matcher are in the hash, and that is the part that is
    easy to miss.**
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
            audited.matcher,
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
    #: Which strings count as the same string. In the id for the same reason
    #: the packs are: it changes every count on the report.
    matcher: str = "normalized"


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
    #: Dotted paths to fields the contract does not list. Version 1 is closed,
    #: so a package carrying one of these does not conform and akashi audited
    #: it anyway. Context, on the same footing as ``withheld``: it says
    #: something about the document, never about a finding in it.
    unrecognised: tuple[str, ...] = ()

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
    #: What a language model said about the claims akashi could not settle, each
    #: under the name of the model that said it (ADR-0017).
    #:
    #: **Not verdicts, and not in `report_id`.** akashi's verdicts are decided by
    #: comparing strings and are the same on every machine on every day; these
    #: are not, and keeping them out of the id is what lets the same audit carry
    #: judgements or not and still be re-derivable. Nothing merges the two, and
    #: they share no vocabulary.
    judged: tuple[Any, ...] = ()

    @property
    def report_id(self) -> str:
        """What this report is, by its inputs. See :func:`report_id`."""
        return report_id(self.audited)

    @property
    def has_findings(self) -> bool:
        return bool(self.assessment.findings)

    def to_dict(self) -> dict[str, Any]:
        """The report as plain data, in the order a reader skims it.

        Here rather than at the edge that happens to print it. A report is a
        document (ADR-0002) -- it is what somebody keeps to show that an answer
        was checked -- and a shape defined inside one CLI branch is a shape the
        next consumer writes again, slightly differently. ``recheck`` compares
        two of these, and it lives in a layer that cannot reach infrastructure.

        Field order is insertion order and it is deliberate. ``contract`` is
        first because a consumer reads it first and refuses what it does not
        recognise; ``unchecked``, ``coverage`` and ``limits`` come before
        ``segments`` for the same reason the text rendering does (ADR-0005).
        JSON objects are unordered by specification and ordered in practice, and
        a reader skimming the raw file is a real reader.
        """
        coverage = self.assessment.coverage
        return {
            "contract": self.contract,
            "report_id": self.report_id,
            "audited": {
                "package_id": self.audited.package_id,
                "response_hash": self.audited.response_hash,
                "response_length": self.audited.response_length,
                "segmenters": list(self.audited.segmenters),
                "extractors": list(self.audited.extractors),
                "packs": list(self.audited.packs),
                "akashi_version": self.audited.akashi_version,
                "matcher": self.audited.matcher,
            },
            "unchecked": [
                {
                    "segment_id": skip.segment_id,
                    "span": [skip.span.start, skip.span.end],
                    "rule": skip.rule.value,
                    "reason": skip.reason,
                }
                for skip in self.assessment.skipped
            ],
            "coverage": {
                "segments": coverage.segments,
                "bearing": coverage.bearing,
                "unbearing": coverage.unbearing,
                "unexamined": coverage.unexamined,
                "particulars": coverage.particulars,
                "checked": coverage.checked,
                "kinds_not_extracted": list(coverage.kinds_not_extracted),
            },
            "limits": [*self.assessment.limits, *_judgement_limits(self.judged)],
            "counts": {
                "segments": self.assessment.counts(),
                "particulars": self.assessment.particular_counts(),
                # ``null`` rather than 1.0 or 0.0 when nothing was checkable. A
                # number there would be read as a pass or a failure, and it is
                # neither.
                "grounded_share": self.assessment.grounded_share,
            },
            "segments": [_segment_dict(segment) for segment in self.assessment.segments],
            "provenance": {
                "restored_by": self.provenance.restored_by,
                "restoration_asserted": self.provenance.restoration_asserted,
                "protection_by": self.provenance.protection_by,
                "withheld": [
                    {"rule": rule, "count": count} for rule, count in self.provenance.withheld
                ],
                "unrecognised": list(self.provenance.unrecognised),
            },
            "judged": [
                {
                    "segment_id": one.segment_id,
                    "particular": one.particular,
                    "standing": one.standing.value,
                    "because": one.because,
                    "model": one.model,
                }
                for one in self.judged
            ],
            "answer": self.answer,
        }

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


def _segment_dict(segment: CheckedSegment) -> dict[str, Any]:
    body: dict[str, Any] = {
        "segment_id": segment.segment.segment_id,
        "span": [segment.span.start, segment.span.end],
        "text": segment.segment.text,
        "kind": segment.segment.kind.value,
        "script": segment.segment.script.value,
        "boundary": segment.segment.boundary.value,
        "verdict": segment.verdict.value,
    }
    if segment.because:
        body["because"] = segment.because
    if segment.particulars:
        body["particulars"] = [_particular_dict(one) for one in segment.particulars]
    return body


def _particular_dict(one: CheckedParticular) -> dict[str, Any]:
    span = one.particular.span
    body: dict[str, Any] = {
        "kind": one.particular.kind.value,
        "text": one.particular.text,
        "span": [span.start, span.end],
        "standing": one.standing.value,
    }
    if one.locations:
        body["locations"] = [
            {
                "item_id": location.item_id,
                "document_id": location.anchor.document_id,
                "source_path": location.anchor.source_path,
                "section": location.anchor.section,
                "span": [location.anchor.span.start, location.anchor.span.end],
                "layer": location.layer.value if location.layer else None,
            }
            for location in one.locations
        ]
        body["in_an_interpretation"] = one.in_an_interpretation
    if one.contradiction is not None:
        found = one.contradiction
        body["contradiction"] = {
            "found": found.found,
            "item_id": found.item_id,
            "document_id": found.anchor.document_id,
            "source_path": found.anchor.source_path,
            "section": found.anchor.section,
            "span": [found.anchor.span.start, found.anchor.span.end],
            "why": found.why,
        }
    return body


#: Said on the artefact when a judge ran, because the artefact travels and the
#: documentation does not (ADR-0005). Two runs of the same audit with the same
#: judge can disagree, and a reader holding one report has no way to know that
#: unless the report says it.
JUDGEMENT_LIMITS: tuple[str, ...] = (
    "A judgement in 'judged' is a language model's opinion, not an akashi verdict. "
    "It is not reproducible: the same claim asked again, or asked after the model "
    "changes, can come back differently, and the model that answered is named "
    "beside each one so that a reader can tell which run they are holding.",
    "'supported' means a model thought the evidence entails the claim. It does not "
    "mean the claim is in the text that was sent -- akashi already reported that, "
    "and reported it 'floating', which is why the claim was sent at all.",
    "Judgements do not change report_id, and rechecking this report re-derives the "
    "audit without them. What a judge adds is an annotation on an audit; it is not "
    "part of one.",
)


def _judgement_limits(judged: tuple[Any, ...]) -> tuple[str, ...]:
    return JUDGEMENT_LIMITS if judged else ()
