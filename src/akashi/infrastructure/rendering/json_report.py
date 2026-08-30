"""The report as JSON.

ADR-0002: the report is a document, complete on its own, readable by a program
that has never heard of Python. This is the shape v0.2 will freeze and publish
a schema for; until then the contract string says ``1-draft`` and a consumer
should expect fields to move.

Field order is insertion order and it is deliberate. ``contract`` is first
because a consumer reads it first and refuses what it does not recognise;
``unchecked``, ``coverage`` and ``limits`` come before ``findings`` for the same
reason the text rendering does (ADR-0005). JSON objects are unordered by
specification and ordered in practice, and a reader skimming the raw file is a
real reader.
"""

from __future__ import annotations

import json
from typing import Any

from akashi.domain.report import AuditReport
from akashi.domain.verdict import CheckedParticular, CheckedSegment

__all__ = ["as_dict", "as_json"]


def as_dict(report: AuditReport) -> dict[str, Any]:
    """The report as plain data.

    Here rather than at the edge that happens to print it. A shape defined
    inside one CLI branch is a shape the next consumer writes again, slightly
    differently.
    """
    assessment = report.assessment
    coverage = assessment.coverage
    return {
        "contract": report.contract,
        "report_id": report.report_id,
        "audited": {
            "package_id": report.audited.package_id,
            "response_hash": report.audited.response_hash,
            "response_length": report.audited.response_length,
            "segmenters": list(report.audited.segmenters),
            "extractors": list(report.audited.extractors),
            "packs": list(report.audited.packs),
            "akashi_version": report.audited.akashi_version,
        },
        "unchecked": [
            {
                "segment_id": skip.segment_id,
                "span": [skip.span.start, skip.span.end],
                "rule": skip.rule.value,
                "reason": skip.reason,
            }
            for skip in assessment.skipped
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
        "limits": list(assessment.limits),
        "counts": {
            "segments": assessment.counts(),
            "particulars": assessment.particular_counts(),
            # ``null`` rather than 1.0 or 0.0 when nothing was checkable. A
            # number there would be read as a pass or a failure, and it is
            # neither.
            "grounded_share": assessment.grounded_share,
        },
        "segments": [_segment(segment) for segment in assessment.segments],
        "provenance": {
            "restored_by": report.provenance.restored_by,
            "restoration_asserted": report.provenance.restoration_asserted,
            "protection_by": report.provenance.protection_by,
            "withheld": [
                {"rule": rule, "count": count} for rule, count in report.provenance.withheld
            ],
        },
        "answer": report.answer,
    }


def _segment(segment: CheckedSegment) -> dict[str, Any]:
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
        body["particulars"] = [_particular(one) for one in segment.particulars]
    return body


def _particular(one: CheckedParticular) -> dict[str, Any]:
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
    return body


def as_json(report: AuditReport, *, indent: int = 2) -> str:
    """The report as a JSON string, in UTF-8 and not in escapes.

    ``ensure_ascii=False``: half of what akashi audits is CJK, and a report
    full of ``\\u30c6`` is a report nobody reads. The file is written as UTF-8
    and says so nowhere, because JSON is UTF-8 by specification.
    """
    return json.dumps(as_dict(report), ensure_ascii=False, indent=indent) + "\n"
