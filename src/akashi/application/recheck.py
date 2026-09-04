"""Re-deriving a report from the inputs it names.

The command the whole design is for. A record nobody can re-derive is a record
on trust, and `proposals/0002` §4 is why that stopped being a nice-to-have: the
EU AI Act's record-keeping obligations for high-risk systems became enforceable
on 2 August 2026, and what they ask for is a record from which the functioning
of the system can be reconstructed.

**It refuses before it works.** A recheck against the wrong package or the wrong
answer would produce a mismatch, and that mismatch would be a *true statement
that misleads*: the report is fine and the caller brought the wrong file. So
the inputs are checked against the hashes the report names, by name, first.

**A mismatch says what differed.** "The ids differ" is not a finding anybody can
act on. Which counts moved, which verdicts changed, which fields disagree — that
is a finding.

**A version difference is not tampering** and must not read as it. akashi 0.3
auditing an answer that akashi 0.2 audited will legitimately differ; the report
carries the version that produced it, and a recheck under a different one says
so before it says anything else.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from akashi.domain.language import LanguagePack
from akashi.domain.matching import DEFAULT_MATCHER, matcher_named
from akashi.domain.package import ContextPackage
from akashi.domain.report import content_hash
from akashi.errors import ContractError
from akashi.ports import Restorer

from .audit import audit

__all__ = ["Recheck", "recheck"]

#: Fields whose difference is explained by the version and not by the inputs.
#: Reported, and reported first, so that a reader does not scroll past forty
#: count differences looking for the cause.
_VERSION_FIELDS = ("audited.akashi_version",)


@dataclass(frozen=True, slots=True)
class Recheck:
    """What became of a report when it was re-derived."""

    archived_id: str
    rederived_id: str
    #: Field paths that differ, in order, as ``path: was -> now``.
    differences: tuple[str, ...] = field(default_factory=tuple)
    #: True when the archived report was produced by a different akashi.
    version_differs: bool = False
    archived_version: str = ""
    rederived_version: str = ""

    @property
    def matches(self) -> bool:
        return self.archived_id == self.rederived_id and not self.differences

    def describe(self) -> str:
        if self.matches:
            return f"re-derived identically: {self.archived_id}"
        head = f"{len(self.differences)} difference{'' if len(self.differences) == 1 else 's'}"
        if self.version_differs:
            return (
                f"{head}, and the report was produced by akashi "
                f"{self.archived_version or 'unknown'} rather than "
                f"{self.rederived_version or 'unknown'} - a version difference is not "
                f"tampering, and these differences may be entirely explained by it"
            )
        return head


def _flatten(body: Any, prefix: str = "") -> dict[str, Any]:
    """Every leaf of a report, by path.

    Lists are indexed rather than compared whole, so a difference names the
    segment it is in rather than reporting that ``segments`` changed.
    """
    if isinstance(body, dict):
        found: dict[str, Any] = {}
        for key, value in body.items():
            found.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
        return found
    if isinstance(body, list):
        found = {}
        for index, value in enumerate(body):
            found.update(_flatten(value, f"{prefix}[{index}]"))
        return found or {prefix: []}
    return {prefix: body}


def _differences(archived: dict[str, Any], rederived: dict[str, Any]) -> tuple[str, ...]:
    was, now = _flatten(archived), _flatten(rederived)
    lines: list[str] = []
    for path in sorted(set(was) | set(now)):
        left, right = was.get(path, "<absent>"), now.get(path, "<absent>")
        if left != right:
            lines.append(f"{path}: {left!r} -> {right!r}")
    # The version first, because it may explain every line under it.
    lines.sort(key=lambda line: (line.split(":")[0] not in _VERSION_FIELDS, line))
    return tuple(lines)


def recheck(
    archived: dict[str, Any],
    answer: str,
    package: ContextPackage,
    packs: Sequence[LanguagePack],
    *,
    restorer: Restorer | None = None,
    restored_by: str = "",
    akashi_version: str = "",
) -> Recheck:
    """Re-derive ``archived`` from the inputs it names, and say what differs.

    Raises ``ContractError`` when the inputs are not the ones the report names.
    That is a refusal rather than a mismatch: the report may be perfectly good
    and the caller has brought the wrong file, and reporting a difference would
    be a true statement that misleads.
    """
    audited = archived["audited"]

    named_package = str(audited.get("package_id", ""))
    if named_package and named_package != package.package_id:
        raise ContractError(
            f"the report was made against package {named_package} and this package is "
            f"{package.package_id or 'unnamed'}. Rechecking against a different package "
            f"would report a mismatch that says nothing about the report."
        )

    named_hash = str(audited.get("response_hash", ""))
    if named_hash and named_hash != content_hash(answer):
        raise ContractError(
            f"the report was made over a response hashing to {named_hash} and this one "
            f"hashes to {content_hash(answer)}. One of the two is the wrong file."
        )

    # Re-derived with the matcher the report *names*, not with whatever this
    # process defaults to. Which strings count as the same string changes every
    # count, so re-deriving an `exact` report under `normalized` would report a
    # difference that is about this run rather than about that report.
    named_matcher = str(audited.get("matcher", "")) or DEFAULT_MATCHER.name
    try:
        chosen = matcher_named(named_matcher)
    except ValueError as error:
        raise ContractError(
            f"the report was made with a matcher called {named_matcher!r}, which this "
            f"akashi does not have. Re-deriving it with a different one would compare "
            f"two answers to two different questions."
        ) from error

    fresh = audit(
        answer,
        package,
        packs,
        restorer=restorer,
        restored_by=restored_by,
        akashi_version=akashi_version,
        matcher=chosen,
    ).to_dict()

    archived_version = str(audited.get("akashi_version", ""))
    return Recheck(
        archived_id=str(archived.get("report_id", "")),
        rederived_id=str(fresh["report_id"]),
        differences=_differences(archived, fresh),
        version_differs=archived_version != akashi_version,
        archived_version=archived_version,
        rederived_version=akashi_version,
    )
