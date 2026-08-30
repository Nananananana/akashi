"""The report as JSON text.

The *shape* is the contract and lives in ``domain/report.py`` -- a report is a
document (ADR-0002), and what a document contains is not a formatting decision.
What is here is the last step: turning that shape into bytes.

Separating the two is not tidiness. ``akashi recheck`` compares a report it read
against one it re-derived, and it lives in ``application``, which may not import
infrastructure. A shape defined at the edge that happens to print it is a shape
the next consumer writes again, slightly differently.
"""

from __future__ import annotations

import json

from akashi.domain.report import AuditReport

__all__ = ["as_dict", "as_json"]


def as_dict(report: AuditReport) -> dict[str, object]:
    """The report as plain data. Kept as a name here for callers that had it."""
    return report.to_dict()


def as_json(report: AuditReport, *, indent: int = 2) -> str:
    """The report as a JSON string, in UTF-8 and not in escapes.

    ``ensure_ascii=False``: half of what akashi audits is CJK, and a report full
    of ``\\u30c6`` escapes is a report nobody reads. The file is written as
    UTF-8 and says so nowhere, because JSON is UTF-8 by specification.
    """
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent) + "\n"
