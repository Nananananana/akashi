"""The ContextPackage reader. Fail closed, and say what was refused.

Reading somebody else's contract is a second implementation of it, and the two
can drift. That is the price ADR-0007 accepts for not importing `tsumugi`, and
these are the rules that keep the price bounded:

**The contract field is read first and an unrecognised value is refused.** Not
guessed at, not partially honoured. Guessing at a version is how a consumer
reads a field that has changed meaning and reports the wrong thing with
complete confidence.

**A field akashi does not know is read past and written down; a *value* akashi
does not know is refused.** An unfamiliar ``layer`` is a category akashi has no
handling for, and treating it as an ordinary fact would launder it. An
unfamiliar *field* is not wrong, only unknown -- the distinction ADR-0008 draws
between *unverifiable* and *floating*, applied to the document.

That used to be the whole of it, on the strength of a promise the contract has
since withdrawn. Version 1 said *"a field may be added; none will be removed or
change meaning"*, and ignoring an unfamiliar key was what conformance required.
It now says v1 is **closed** and that every object sets
``additionalProperties: false``, which makes an extension indistinguishable from
corruption -- deliberately (tsumugi ADR-0022). So an unrecognised field means
this is not a conforming package, and akashi reading it in silence is akashi
auditing a document whose reader is never told which document it was. They are
collected in ``ContextPackage.unrecognised`` and the report prints them.

Refusing instead would be the wrong trade twice over: akashi would break on any
producer that is not tsumugi, and on tsumugi's own version 2 -- and it would
throw away an audit it is perfectly able to perform in order to report a fact it
can simply state.

**A missing field is not the same as a field that says nothing.** A package
with no ``provenance`` has not told akashi that it was unprotected; it has told
akashi nothing, and ``declares_protection`` keeps those apart so that ADR-0008
can refuse rather than assume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from akashi.domain.anchor import Anchor, Layer
from akashi.domain.evidence import Evidence, EvidenceItem, Withheld
from akashi.domain.package import ContextPackage, Protection
from akashi.domain.span import Span
from akashi.errors import ContractError
from akashi.infrastructure.documents import parse

__all__ = [
    "ACCEPTED_CONTRACT",
    "ContextPackage",
    "Protection",
    "load_package",
    "read_package",
]

#: The one contract akashi reads, and the one major version of it. ``1-draft``
#: is accepted too: packages written before the freeze carry it, and refusing
#: evidence over a version string would be the wrong trade.
ACCEPTED_CONTRACT = "tsumugi.context-package"
ACCEPTED_MAJOR = "1"

#: Every field `tsumugi.context-package/1` lists, per object.
#:
#: **Not the fields akashi uses.** ``budget``, ``constraints`` and
#: ``output_schema`` are named here and read nowhere -- akashi has no use for
#: them and their presence is not a finding. A list of what akashi consumes
#: would report the contract's own fields as unrecognised, which is the failure
#: this is here to prevent rather than cause.
#:
#: Transcribed from the schema in ``tests/contracts/`` rather than loaded from
#: it: that copy is test material, and a released akashi that read it would
#: turn a vendored file into a runtime dependency (ADR-0007). The transcription
#: drifting from the copy is itself a test.
CONTRACT_FIELDS: dict[str, frozenset[str]] = {
    "": frozenset(
        {
            "budget",
            "constraints",
            "contract",
            "created_at",
            "instructions",
            "items",
            "omissions",
            "output_schema",
            "package_id",
            "provenance",
            "query",
        }
    ),
    "items": frozenset({"anchor", "cost", "item_id", "kind", "provenance", "selection", "text"}),
    "omissions": frozenset({"anchor", "cost", "reason", "rule", "score"}),
    "provenance": frozenset(
        {"corpus_state", "protection", "providers", "settings_hash", "tsumugi_version"}
    ),
}


def _unrecognised(data: dict[str, Any]) -> tuple[str, ...]:
    """Dotted paths to fields the contract does not list, in the order found.

    Only the objects the contract names are walked. Going deeper would need
    akashi to hold a second copy of the whole schema, and the value of the
    check does not rise with the depth: a package carrying an invented field
    anywhere carries one here, and one path is enough to say so.
    """
    found: list[str] = []

    def scan(obj: object, known: frozenset[str], where: str) -> None:
        if not isinstance(obj, dict):
            return
        found.extend(f"{where}{key}" for key in obj if key not in known)

    scan(data, CONTRACT_FIELDS[""], "")
    for key in ("items", "omissions"):
        raw = data.get(key)
        if isinstance(raw, list):
            for index, entry in enumerate(raw):
                scan(entry, CONTRACT_FIELDS[key], f"{key}[{index}].")
    scan(data.get("provenance"), CONTRACT_FIELDS["provenance"], "provenance.")
    return tuple(found)


def _require(data: dict[str, Any], key: str, where: str) -> Any:
    if key not in data:
        raise ContractError(f"{where} has no {key!r}, which the contract requires")
    return data[key]


def _text(
    data: dict[str, Any], key: str, where: str, *, required: bool = True, least: int = 0
) -> str:
    """A string field. ``least`` mirrors the schema's ``minLength``.

    Empty is a legal value for most fields here and the default reflects that.
    Where the contract says ``minLength: 1`` it means the field carries
    information, and a producer that sends ``""`` has said nothing while
    appearing to have answered.
    """
    if key not in data:
        if required:
            raise ContractError(f"{where} has no {key!r}, which the contract requires")
        return ""
    value = data[key]
    if not isinstance(value, str):
        raise ContractError(f"{where} has a {key!r} that is not a string: {value!r}")
    if len(value) < least:
        raise ContractError(
            f"{where} has an empty {key!r}, and the contract requires it to say something"
        )
    return value


def _flag(data: dict[str, Any], key: str, where: str) -> bool:
    """A boolean field, and *only* a boolean.

    ``bool(raw.get(key))`` would be shorter and is what this replaced. It reads
    the string ``"false"`` as ``True``, which is the unsafe direction for
    ``reversible``: a package nobody can restore would be audited as though it
    could be.
    """
    value = _require(data, key, where)
    if not isinstance(value, bool):
        raise ContractError(f"{where} has a {key!r} that is not a boolean: {value!r}")
    return value


def _offset(data: dict[str, Any], key: str, where: str) -> int:
    value = _require(data, key, where)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError(f"{where} has a {key!r} that is not an offset: {value!r}")
    return value


def _check_contract(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(
            f"the package has no readable 'contract' field: {value!r}. It is read first "
            f"and it is refused when it is not recognised, because guessing at a version "
            f"is how a consumer reports the wrong thing with confidence."
        )
    name, _, version = value.partition("/")
    major = version.partition("-")[0]
    if name != ACCEPTED_CONTRACT or major != ACCEPTED_MAJOR:
        raise ContractError(
            f"akashi does not read {value!r}. It reads "
            f"{ACCEPTED_CONTRACT}/{ACCEPTED_MAJOR}, including the pre-freeze "
            f"{ACCEPTED_CONTRACT}/1-draft."
        )
    return value


def _layer(provenance: object, where: str) -> Layer | None:
    """The item's layer, or ``None`` when it declared none.

    An unfamiliar value is refused. ``kiseki``'s three layers are a closed set
    and a fourth would be a category akashi has no handling for -- treating it
    as an ordinary fact is exactly the laundering the distinction exists to
    stop.
    """
    if not isinstance(provenance, dict) or "layer" not in provenance:
        return None
    value = provenance["layer"]
    try:
        return Layer(value)
    except ValueError:
        raise ContractError(
            f"{where} declares the layer {value!r}, which akashi does not know. "
            f"It knows {sorted(layer.value for layer in Layer)}."
        ) from None


def _item(raw: object, index: int) -> EvidenceItem:
    where = f"items[{index}]"
    if not isinstance(raw, dict):
        raise ContractError(f"{where} is not an object: {raw!r}")

    item_id = _text(raw, "item_id", where)
    text = _text(raw, "text", where)
    raw_anchor = _require(raw, "anchor", where)
    if not isinstance(raw_anchor, dict):
        raise ContractError(f"{where} has an anchor that is not an object")

    anchor_where = f"{where}.anchor"
    start = _offset(raw_anchor, "start", anchor_where)
    end = _offset(raw_anchor, "end", anchor_where)
    # **This one is not in the schema and cannot be.** JSON Schema 2020-12
    # cannot compare two properties of the same object, so a reversed anchor
    # validates cleanly. tsumugi refuses to construct one, so no real package
    # carries it -- but a producer's invariant is not a consumer's guarantee,
    # and this is the consumer's copy of it. Do not remove it on the grounds
    # that the fixtures validate; that is exactly what it is here for.
    if end < start:
        raise ContractError(f"{anchor_where} ends at {end}, before it starts at {start}")

    provenance = raw.get("provenance")
    producer = ""
    if isinstance(provenance, dict):
        producer = _text(provenance, "producer", f"{where}.provenance", required=False)

    try:
        return EvidenceItem(
            item_id=item_id,
            text=text,
            anchor=Anchor(
                document_id=_text(raw_anchor, "document_id", anchor_where),
                span=Span(start, end),
                source_path=_text(raw_anchor, "source_path", anchor_where, required=False),
                section=_text(raw_anchor, "section", anchor_where, required=False),
                text_hash=_text(raw_anchor, "text_hash", anchor_where, required=False),
                document_hash=_text(raw_anchor, "document_hash", anchor_where, required=False),
            ),
            layer=_layer(provenance, where),
            producer=producer,
        )
    except ValueError as error:
        # The domain's invariants are the contract's invariants, restated where
        # they can be checked. A package that breaks one is a package akashi
        # refuses, not one it repairs.
        raise ContractError(f"{where} is not a usable evidence item: {error}") from error


def _omission(raw: object, index: int) -> Withheld:
    where = f"omissions[{index}]"
    if not isinstance(raw, dict):
        raise ContractError(f"{where} is not an object: {raw!r}")

    anchor: Anchor | None = None
    raw_anchor = raw.get("anchor")
    if isinstance(raw_anchor, dict) and "document_id" in raw_anchor:
        start = _offset(raw_anchor, "start", f"{where}.anchor")
        end = _offset(raw_anchor, "end", f"{where}.anchor")
        anchor = Anchor(
            document_id=_text(raw_anchor, "document_id", f"{where}.anchor"),
            span=Span(start, max(start, end)),
            source_path=_text(raw_anchor, "source_path", f"{where}.anchor", required=False),
        )

    try:
        return Withheld(
            rule=_text(raw, "rule", where),
            reason=_text(raw, "reason", where),
            anchor=anchor,
        )
    except ValueError as error:
        raise ContractError(f"{where} is not a usable omission: {error}") from error


def _protection(raw: object, where: str) -> Protection | None:
    """A protection block, read exactly as strictly as the contract writes it.

    The contract requires all three fields, and ``by`` and ``scope`` with
    ``minLength: 1``. This used to read ``scope`` as optional and ``reversible``
    through ``bool()``, so a malformed block became "irreversible, scope
    unstated" and was audited.

    That is the *safe* direction and it was still wrong, because it was reached
    by accident rather than decided. ADR-0008 turns on ``reversible``: a package
    that cannot say whether it can be restored has not told akashi the one thing
    the decision needs, and the house rule everywhere else here is to refuse
    rather than to guess. ``null`` still means "nothing redacted this"; absent
    still means "this package did not say", which ``declares_protection``
    carries and which ADR-0008 already refuses on.

    **This strictness belongs to *this* contract and must not be carried to the
    next one.** ``tsumugi.context-package/1`` requires ``reversible``, so a
    block without it is malformed. ``mamori.protection-scope/1`` says the
    opposite for a field of the same name: a consumer that cannot find
    ``reversible`` reads it as ``false``, because there the value is computed
    rather than defaulted and the rule exists for readers of records mamori did
    not write (its ADR-0032). Two contracts, one field name, opposite rules for
    its absence. Whoever writes the protection-scope reader should read that ADR
    before reusing anything here.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ContractError(f"{where} is neither null nor an object: {raw!r}")
    return Protection(
        by=_text(raw, "by", where, least=1),
        scope=_text(raw, "scope", where, least=1),
        reversible=_flag(raw, "reversible", where),
    )


def read_package(data: object) -> ContextPackage:
    """A ContextPackage from already-parsed JSON.

    Separate from ``load_package`` so that a caller holding a package from
    somewhere other than a file -- an MCP request, a pipe, a test fixture --
    does not have to write it to disk first.
    """
    if not isinstance(data, dict):
        raise ContractError(f"a package is a JSON object, not {type(data).__name__}")

    contract = _check_contract(data.get("contract"))

    raw_items = _require(data, "items", "the package")
    if not isinstance(raw_items, list):
        raise ContractError("the package has an 'items' that is not a list")
    items = tuple(_item(raw, index) for index, raw in enumerate(raw_items))

    raw_omissions = data.get("omissions", [])
    if not isinstance(raw_omissions, list):
        raise ContractError("the package has an 'omissions' that is not a list")
    withheld = tuple(_omission(raw, index) for index, raw in enumerate(raw_omissions))

    provenance = data.get("provenance")
    declares_protection = isinstance(provenance, dict) and "protection" in provenance
    protection = (
        _protection(provenance["protection"], "provenance.protection")
        if declares_protection and isinstance(provenance, dict)
        else None
    )

    providers: tuple[str, ...] = ()
    producer_version = corpus_state = ""
    if isinstance(provenance, dict):
        raw_providers = provenance.get("providers", [])
        if isinstance(raw_providers, list):
            providers = tuple(str(name) for name in raw_providers)
        producer_version = _text(provenance, "tsumugi_version", "provenance", required=False)
        corpus_state = _text(provenance, "corpus_state", "provenance", required=False)

    try:
        evidence = Evidence(items=items, withheld=withheld)
    except ValueError as error:
        raise ContractError(f"the package is not a usable evidence set: {error}") from error

    return ContextPackage(
        contract=contract,
        package_id=_text(data, "package_id", "the package", required=False),
        query=_text(data, "query", "the package", required=False),
        evidence=evidence,
        protection=protection,
        declares_protection=declares_protection,
        producer_version=producer_version,
        providers=providers,
        corpus_state=corpus_state,
        unrecognised=_unrecognised(data),
    )


def load_package(path: Path | str) -> ContextPackage:
    """A ContextPackage from a file, read as UTF-8.

    Not as bytes with a guessed encoding: half of what akashi audits is CJK,
    and a mojibake package would produce an answer full of floating particulars
    with no indication of why.
    """
    location = Path(path)
    try:
        raw = location.read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError(f"cannot read the package at {location}: {error}") from error
    except UnicodeDecodeError as error:
        raise ContractError(
            f"the package at {location} is not UTF-8: {error}. A package read with the "
            f"wrong encoding audits as fabricated in full."
        ) from error

    return read_package(parse(raw, what="package", where=str(location)))
