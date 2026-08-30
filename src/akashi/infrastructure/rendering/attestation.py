"""The report in a shape somebody else's signature can cover.

ADR-0014. An in-toto Statement names a *subject* by digest and carries a
*predicate* about it. An audit report is precisely a predicate about a subject:
the answer, by its hash. That is not an analogy -- it is the same structure, and
the tooling around it (in-toto, SLSA, Sigstore, ``cosign``) is tooling security
teams already run.

**akashi signs nothing.** The Statement is a JSON shape; keys, trust roots and
revocation are the caller's. Taking a crypto dependency to do what ``cosign``
does better would cost ADR-0001 for the worst reason available.

This lives in ``infrastructure`` and not in ``domain`` because it is a shape
akashi did not choose. The report's own shape is the contract and belongs to the
domain; this is an envelope somebody else specified.
"""

from __future__ import annotations

from typing import Any

from akashi.domain.report import AuditReport

__all__ = ["PREDICATE_TYPE", "STATEMENT_TYPE", "as_statement"]

#: in-toto Attestation Framework v1.
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"

#: What the predicate is. Versioned separately from the report contract on
#: purpose: a consumer selects on this URI before it reads a single field, and a
#: URI that moved when the report contract did not would break that selection
#: for no reason.
PREDICATE_TYPE = "https://akashi.dev/audit-report/v1"

#: The subject when the caller named none. Not an empty string: a subject with
#: no name is harder to read in a log than one that says it was unnamed.
DEFAULT_SUBJECT = "response"


def _digest(content_hash: str) -> dict[str, str]:
    """``sha256:abcd…`` as in-toto wants it: the algorithm is the key.

    akashi's own hashes name their algorithm inside the string, so that a reader
    holding one alone can still check it. in-toto puts the algorithm in the key
    instead. Both are right for what they are, and this is where they meet.
    """
    algorithm, _, value = content_hash.partition(":")
    if not value:
        raise ValueError(
            f"{content_hash!r} does not name its algorithm, so it cannot become an in-toto digest"
        )
    return {algorithm: value}


def as_statement(report: AuditReport, *, subject: str = DEFAULT_SUBJECT) -> dict[str, Any]:
    """The report as an unsigned in-toto Statement.

    The subject digest is taken from the report's own ``response_hash``, from
    the same field, so the envelope and the predicate cannot disagree about
    what was audited.

    **Unsigned.** A caller who does not sign it has exactly what they had
    before, in a different wrapper — and a reader who sees ``_type: in-toto``
    may assume otherwise, which is the hazard ADR-0014 creates and names.
    """
    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": subject or DEFAULT_SUBJECT,
                "digest": _digest(report.audited.response_hash),
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": report.to_dict(),
    }
