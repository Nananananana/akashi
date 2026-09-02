"""Turning a report into something a person, a program or a verifier reads.

Three renderings, and the difference between them is only format. None decides
anything: a renderer that computed a number would be a second place a verdict
could come from.

The report's own *shape* is the contract and lives in ``domain/report.py``. What
is here is the last step -- text for a reader, JSON for a program, and an
in-toto Statement for a signature that is not akashi's (ADR-0014).

``explanation`` and ``certificate`` read the other way: they take an archived
report back and render it from the report alone -- one segment in full, or the
whole thing as a single HTML file for somebody who will sign it.
"""

from __future__ import annotations

from .attestation import as_statement
from .certificate import certificate
from .diagnosis import as_text as as_diagnosis
from .explanation import explain_segment, segments_with_findings
from .json_report import as_dict, as_json
from .text import as_text

__all__ = [
    "as_diagnosis",
    "as_dict",
    "as_json",
    "as_statement",
    "as_text",
    "certificate",
    "explain_segment",
    "segments_with_findings",
]
