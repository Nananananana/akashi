"""Every way akashi refuses.

This module imports nothing -- not even from the rest of akashi. An error type
that depends on a layer cannot be raised from below it, and refusing is the one
thing every layer has to be able to do.

akashi fails closed. Where the alternative to raising is to produce a report
that is confidently wrong, it raises: a report is meant to be believed, and an
auditor that guesses teaches its user to ignore it.
"""

from __future__ import annotations

__all__ = [
    "AkashiError",
    "ContractError",
    "ProtectedResponseError",
    "SegmentationError",
]


class AkashiError(Exception):
    """Base class for everything akashi raises deliberately."""


class ContractError(AkashiError):
    """A document did not conform to a contract akashi recognises.

    Raised for an unknown ``contract`` value, a missing required field, or an
    audit report whose ``report_id`` does not re-derive. Guessing at an
    unrecognised version is how a consumer reads the wrong field and reports
    the wrong thing, so it is refused instead (ADR-0007).
    """


class ProtectedResponseError(AkashiError):
    """The response still carries placeholders, and nothing can restore them.

    Auditing pseudonymized text marks every honest particular as floating --
    an answer that quoted its sources perfectly, reported as fabricated in
    full. Unknown and false are different, so this refuses rather than reports
    (ADR-0008).
    """


class SegmentationError(AkashiError):
    """The answer could not be cut into segments that tile it exactly.

    Every count in a report has the segmenter in its denominator, and an
    offset that has drifted points a reader at the wrong sentence. A tiling
    that does not hold is a bug, and it stops the audit (ADR-0009).
    """
