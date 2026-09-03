"""Reading an audit report back.

akashi's own contract, read the way it reads somebody else's: contract field
first, refuse what is not recognised, and never guess. A consumer that is
lenient about its own documents is a consumer that will be lenient about a
tampered one.

What comes back is a plain dictionary rather than an ``AuditReport``. That is
deliberate: ``recheck`` compares an archived report against a freshly derived
one, and reconstructing the dataclasses first would put an interpretation
between the file and the comparison. The bytes somebody archived are what is
being checked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from akashi.domain.report import CONTRACT
from akashi.errors import ContractError
from akashi.infrastructure.documents import parse

__all__ = ["ACCEPTED_REPORT", "load_report", "load_report_or_statement", "read_report"]

ACCEPTED_REPORT = "akashi.audit-report"
ACCEPTED_MAJOR = "1"

#: Everything ``recheck`` needs to know it is looking at the right inputs.
_REQUIRED = ("contract", "report_id", "audited", "answer")
_REQUIRED_AUDITED = ("package_id", "response_hash", "packs", "akashi_version")


def _check_contract(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"the report has no readable 'contract' field: {value!r}")
    name, _, version = value.partition("/")
    if name != ACCEPTED_REPORT or version.partition("-")[0] != ACCEPTED_MAJOR:
        raise ContractError(
            f"akashi does not read {value!r}. It reads {CONTRACT} and "
            f"{ACCEPTED_REPORT}/{ACCEPTED_MAJOR}."
        )
    return value


def read_report(data: object) -> dict[str, Any]:
    """An audit report from already-parsed JSON, checked far enough to use."""
    if not isinstance(data, dict):
        raise ContractError(f"a report is a JSON object, not {type(data).__name__}")
    _check_contract(data.get("contract"))

    for key in _REQUIRED:
        if key not in data:
            raise ContractError(f"the report has no {key!r}, which the contract requires")
    audited = data["audited"]
    if not isinstance(audited, dict):
        raise ContractError("the report has an 'audited' that is not an object")
    for key in _REQUIRED_AUDITED:
        if key not in audited:
            raise ContractError(f"the report has no 'audited.{key}'")
    return data


def load_report(path: Path | str) -> dict[str, Any]:
    """An audit report from a file, read as UTF-8."""
    location = Path(path)
    try:
        raw = location.read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError(f"cannot read the report at {location}: {error}") from error
    except UnicodeDecodeError as error:
        raise ContractError(f"the report at {location} is not UTF-8: {error}") from error
    return read_report(parse(raw, what="report", where=str(location)))


def load_report_or_statement(path: Path | str) -> dict[str, Any]:
    """A report, whether it was archived bare or inside an in-toto Statement.

    They are one shape: `as_statement` puts the report in `predicate`
    unchanged. A reader who kept the signed artefact rather than the bare
    report is holding the same document one envelope down, and asking them to
    unwrap it by hand before they can read it would be asking them to know
    something the envelope already says.

    The envelope is recognised by `_type` rather than by the presence of
    `predicate`: a bare report has no `_type`, and keying on a field a future
    report might legitimately gain is how a reader starts unwrapping documents
    that are not envelopes.
    """
    location = Path(path)
    try:
        data = parse(location.read_text(encoding="utf-8"), what="report", where=str(location))
    except OSError as error:
        raise ContractError(f"cannot read the report at {location}: {error}") from error
    except UnicodeDecodeError as error:
        raise ContractError(f"the report at {location} is not UTF-8: {error}") from error

    if isinstance(data, dict) and str(data.get("_type", "")).startswith("https://in-toto.io/"):
        if "predicate" not in data:
            raise ContractError(f"{location} is an in-toto statement with no 'predicate' to read")
        return read_report(data["predicate"])
    return read_report(data)
