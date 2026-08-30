"""One finding, in full, from the report and nothing else.

`akashi audit` prints a report a reader skims. When one segment matters they
want all of it at once: the sentence, every particular in it, where each
resolved, what the source says instead, and what the verdict means.

**It reads the report and nothing else** -- no package, no response, no
re-audit. That is the point rather than a convenience. `docs/audit-report.md`
says *a report is a document*, something somebody keeps in order to show that an
answer was checked, and a document that needs its inputs beside it to be read is
not one. This command is where that claim is exercised: if `explain` had to
reach for the package, the claim would be false and this is where it would show.

So it renders the report as it was written, from the plain dictionary
`read_report` returns, without rebuilding the domain objects. A reader of an
archived report is holding the bytes; putting an interpretation between the
bytes and the screen would explain something else.

**And it says what a package-less reader cannot check.** A `locations[]` entry
names a document, a section and an offset -- and from the report alone none of
that can be verified. It is an assertion, and the difference between an
assertion and something a reader can confirm is the whole subject of #53. The
footer says which is which rather than leaving the reader to assume.
"""

from __future__ import annotations

from typing import Any

from akashi.domain.verdict import Verdict
from akashi.errors import ContractError

__all__ = ["explain_segment", "segments_with_findings"]

_INDENT = "  "


def _span(value: Any) -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"[{value[0]}:{value[1]}]"
    return "[?]"


def _where(entry: dict[str, Any]) -> str:
    """A location or a contradiction, in the words the text report uses."""
    path = entry.get("source_path") or entry.get("document_id") or "?"
    section = f" ({entry['section']})" if entry.get("section") else ""
    return f"{path}{section}{_span(entry.get('span'))}"


def segments_with_findings(report: dict[str, Any]) -> list[str]:
    """The ids worth explaining, for a reader who has not chosen one yet."""
    return [
        str(segment.get("segment_id"))
        for segment in report.get("segments", [])
        if Verdict(segment["verdict"]).is_finding
    ]


def _find(report: dict[str, Any], segment_id: str) -> dict[str, Any]:
    for segment in report.get("segments", []):
        if segment.get("segment_id") == segment_id:
            return dict(segment)
    known = [str(one.get("segment_id")) for one in report.get("segments", [])]
    raise ContractError(
        f"the report has no segment {segment_id!r}. It has {', '.join(known) if known else 'none'}."
    )


def _particular(one: dict[str, Any], lines: list[str]) -> None:
    kind = one.get("kind", "?")
    lines.append(f"{_INDENT}{kind} {one.get('text', '')!r} at {_span(one.get('span'))}")

    standing = one.get("standing")
    if standing == "grounded":
        for location in one.get("locations", []):
            lines.append(f"{_INDENT * 2}found in {_where(location)}")
            detail = [f"item {location.get('item_id')}", f"document {location.get('document_id')}"]
            if location.get("layer"):
                lines.append(f"{_INDENT * 3}{', '.join(detail)}, layer {location['layer']}")
            else:
                lines.append(f"{_INDENT * 3}{', '.join(detail)}")
        if len(one.get("locations", [])) > 1:
            # Information rather than an error, and a reader who does not know
            # that reads it as one.
            lines.append(f"{_INDENT * 2}more than one place: a short particular genuinely occurs")
            lines.append(f"{_INDENT * 3}in several, and picking one would imply a precision")
            lines.append(f"{_INDENT * 3}that is not there")
        if one.get("in_an_interpretation"):
            lines.append(f"{_INDENT * 2}every place it was found was already a judgement")
    else:
        lines.append(f"{_INDENT * 2}in none of the text that was sent")

    found = one.get("contradiction")
    if found:
        lines.append(f"{_INDENT * 2}the source says {found.get('found', '')!r} at {_where(found)}")
        lines.append(
            f"{_INDENT * 3}item {found.get('item_id')}, document {found.get('document_id')}"
        )
        if found.get("why"):
            lines.append(f"{_INDENT * 3}why: {found['why']}")


def explain_segment(
    report: dict[str, Any], segment_id: str, *, particular: str | None = None
) -> str:
    """One segment of ``report``, in full.

    ``particular`` narrows to the particulars whose text matches, for a segment
    carrying a dozen of them.
    """
    segment = _find(report, segment_id)
    verdict = Verdict(segment["verdict"])

    lines = [f"akashi explain — {segment_id}", ""]
    lines.append(f"{_INDENT}verdict   {verdict.value}")
    lines.append(f"{_INDENT}rule      {verdict.rule}")
    if segment.get("because"):
        lines.append(f"{_INDENT}because   {segment['because']}")
    lines.append(
        f"{_INDENT}segment   {segment.get('kind', '?')}, {segment.get('script', '?')}, "
        f"ended by {segment.get('boundary', '?')}"
    )
    lines.append(f"{_INDENT}at        {_span(segment.get('span'))} of the answer")
    lines += ["", f"{_INDENT}{segment.get('text', '')}", ""]

    found = list(segment.get("particulars", []))
    if particular is not None:
        found = [one for one in found if one.get("text") == particular]
        if not found:
            carried = [str(one.get("text")) for one in segment.get("particulars", [])]
            raise ContractError(
                f"{segment_id} carries no particular {particular!r}. It carries "
                f"{', '.join(repr(one) for one in carried) if carried else 'none'}."
            )

    lines.append("Particulars")
    if not found:
        lines.append(f"{_INDENT}none; akashi looked and there was nothing in this segment to check")
    for one in found:
        _particular(one, lines)
        lines.append("")

    lines += _footer(found)
    return "\n".join(lines).rstrip() + "\n"


def _footer(particulars: list[dict[str, Any]]) -> list[str]:
    """What a reader holding only this cannot confirm.

    Every offset into a source document is an assertion here. The reader has the
    report; they do not have the document it names, so nothing on this screen
    lets them check that the span contains the text akashi says it does.
    """
    outward = [one for one in particulars if one.get("locations") or one.get("contradiction")]
    if not outward:
        return []
    return [
        "What this screen does not let you check",
        f"{_INDENT}Offsets into the answer you can check: the answer is in the report.",
        f"{_INDENT}Offsets into a source document you cannot. akashi read those documents",
        f"{_INDENT}and you are reading what it wrote down. Opening them is what turns an",
        f"{_INDENT}assertion into something you have seen.",
    ]
