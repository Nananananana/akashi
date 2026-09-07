"""A `mamori.protection-scope/1` record, read as a document.

Sora -- the orchestration layer -- does not import mamori. It gets a protection
record back beside the protected text, and it wants to hand that record to
akashi as JSON and have the audit treat it the way `provenance.protection`
inside a package is treated. That is the whole of what this reads.

**This is a second reader for a field name akashi already reads, and the two
disagree on purpose.** `tsumugi.context-package/1` requires ``reversible`` and a
block without it is malformed. `mamori.protection-scope/1` says the opposite:
*a consumer that does not find this property must read it as false* (its
ADR-0032), because there the value is computed rather than defaulted, and the
rule exists for readers of records mamori did not write. Same word, two
contracts, opposite rules for its absence -- which is why this is a module of
its own rather than a keyword on the package reader.

**akashi is a token-only consumer.** The contract splits itself so that a
reader written for tokens refuses a record holding surrogates through the check
it already has. That check is made here, and made twice: on the identifier, and
on ``protected`` being non-empty, because the contract's own comment says the
second is the one that survives a record written before the identifier was
split. A surrogate is designed to be indistinguishable from a real value, so
the only honest thing akashi can do with a record that carries one is refuse
to pretend it can audit the text.
"""

from __future__ import annotations

from akashi.domain.package import Protection
from akashi.errors import ContractError

__all__ = ["CONTRACT", "read_protection_scope"]

CONTRACT = "mamori.protection-scope/1"
_SURROGATE_CONTRACT = "mamori.protection-scope/1+surrogate"


def read_protection_scope(data: object, where: str = "protection") -> Protection:
    """The three fields akashi acts on, from a record it did not write.

    Everything else in the record -- ``placeholders``, ``masked``, ``mode``,
    ``policy_hash`` -- is read past. akashi does not need the enumeration to
    audit (it finds placeholder-shaped tokens itself), and reading fields it
    does not act on is how a consumer comes to depend on them.
    """
    if not isinstance(data, dict):
        raise ContractError(f"{where} is a JSON object, not {type(data).__name__}")

    contract = data.get("contract")
    if contract == _SURROGATE_CONTRACT:
        raise ContractError(
            f"{where} declares {_SURROGATE_CONTRACT!r}: the text carries surrogates, "
            f"which are designed to be indistinguishable from real values. akashi reads "
            f"tokens only, and auditing surrogate text would report invented names as "
            f"grounded. Restore it first, or audit the text mamori was given.",
            kind="SurrogateRecord",
        )
    if contract != CONTRACT:
        raise ContractError(
            f"{where} declares {contract!r}, and akashi reads {CONTRACT!r}. A consumer "
            f"that does not recognise a contract must refuse the record rather than read "
            f"the fields it happens to know."
        )
    # The check the contract says survives a version change: a record written
    # before the identifier was split declared the plain contract while carrying
    # surrogates, and only this catches it.
    protected = data.get("protected")
    if isinstance(protected, list) and protected:
        raise ContractError(
            f"{where} declares the plain contract and lists {len(protected)} "
            f"surrogate-protected kind{'s' if len(protected) > 1 else ''}. That is a record "
            f"from before the contract split, and it still means the text carries values "
            f"akashi cannot tell from real ones.",
            kind="SurrogateRecord",
        )

    by = data.get("by")
    scope = data.get("scope")
    if not isinstance(by, str) or not by:
        raise ContractError(f"{where} has no 'by', which the contract requires non-empty")
    if not isinstance(scope, str) or not scope:
        raise ContractError(f"{where} has no 'scope', which the contract requires non-empty")

    # ABSENT READS AS FALSE. Not akashi's rule -- mamori's ADR-0032, and the
    # opposite of what the package reader does for the same field name. A wrong
    # `true` fails silently: an honest quotation of a masked value is reported
    # as a fabrication. A wrong `false` costs a segment being `unverifiable`
    # that could have been checked, which a reader can see and dispute.
    reversible = data.get("reversible", False)
    if not isinstance(reversible, bool):
        raise ContractError(
            f"{where}.reversible is {reversible!r}, and the contract says a boolean. "
            f"Reading a string through bool() is how 'false' becomes True."
        )

    return Protection(by=by, scope=scope, reversible=reversible)
