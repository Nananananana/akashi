"""The report, for a person, leading with what was not checked.

That order is a deliberate reversal of what every dashboard in this category
does, and it is the reason the output can be handed to a reviewer (ADR-0005).
A reader takes away the score whatever else is on the page, so what precedes
the score is what bounds it. Putting the caveats underneath would make them
footnotes to a number that had already been believed.

Nothing here computes anything. A renderer that produced a figure would be a
second place a verdict could come from, and there is exactly one.
"""

from __future__ import annotations

from akashi.domain.report import AuditReport
from akashi.domain.verdict import CheckedParticular, Standing

__all__ = ["as_text"]

_INDENT = "  "


def as_text(report: AuditReport, *, width: int = 78) -> str:
    """The whole report as plain text.

    No colour and no terminal detection: this is as likely to be redirected
    into a file that somebody attaches to a filing as it is to be read on a
    screen, and escape codes in that file are noise a reviewer has to explain.
    """
    lines: list[str] = [f"akashi — {report.summary()}", ""]
    lines += _not_checked(report)
    lines += _findings(report, width)
    lines += _traced(report)
    lines += _coverage(report)
    lines += _provenance(report)
    lines += _limits(report, width)
    return "\n".join(lines).rstrip() + "\n"


def _not_checked(report: AuditReport) -> list[str]:
    assessment = report.assessment
    coverage = assessment.coverage
    lines = ["Not checked"]

    by_rule: dict[str, int] = {}
    for skip in assessment.skipped:
        by_rule[skip.rule.value] = by_rule.get(skip.rule.value, 0) + 1
    for rule, count in sorted(by_rule.items()):
        lines.append(f"{_INDENT}{count} segment{_s(count)}: {rule}")

    if coverage.kinds_not_extracted:
        listed = ", ".join(coverage.kinds_not_extracted)
        lines.append(f"{_INDENT}no rule covers: {listed}")

    if len(lines) == 1:
        lines.append(f"{_INDENT}nothing; every segment was examined and bore something")
    return [*lines, ""]


def _findings(report: AuditReport, width: int) -> list[str]:
    findings = report.assessment.findings
    if not findings:
        return ["Findings", f"{_INDENT}none", ""]

    lines = ["Findings"]
    for segment in findings:
        lines.append(f"{_INDENT}{segment.segment.segment_id}  {segment.verdict.value}")
        lines.append(f"{_INDENT * 2}{_clip(segment.segment.text, width - 4)}")
        lines.extend(_particular(one) for one in segment.particulars)
        lines.append("")
    return lines


def _traced(report: AuditReport) -> list[str]:
    """Where every grounded particular came from.

    The README promises a reader this sentence: *this figure comes from your
    document, at this offset*. A report that only printed what went wrong would
    not deliver it -- and for a compliance artefact the traceable half is the
    half somebody is signing.

    Only the segments that are not already findings: a floating segment prints
    all of its particulars, grounded ones included, so listing them again would
    be the same line twice.
    """
    traced = [
        (segment, one)
        for segment in report.assessment.segments
        if not segment.verdict.is_finding
        for one in segment.grounded
    ]
    if not traced:
        return []

    lines = ["Traced"]
    for segment, one in traced:
        span = one.particular.span
        where = ", ".join(location.anchor.describe() for location in one.locations)
        note = " (an interpretation)" if one.in_an_interpretation else ""
        lines.append(
            f"{_INDENT}{segment.segment.segment_id}  {one.particular.text}  "
            f"[{span.start}:{span.end}]  -> {where}{note}"
        )
    return [*lines, ""]


def _particular(one: CheckedParticular) -> str:
    span = one.particular.span
    head = f"{_INDENT * 2}{one.particular.text}  [{span.start}:{span.end}]"
    if one.contradiction is not None:
        found = one.contradiction
        # Two lines. The source's own words go on their own line because that
        # is the part a reader acts on, and burying them at the end of a longer
        # line is how they get skimmed past.
        return "\n".join(
            [
                f"{head}  is in none of the text that was sent",
                f"{_INDENT * 3}the source says {found.found!r} at {found.anchor.describe()}",
            ]
        )
    if one.standing is Standing.FLOATING:
        return f"{head}  is in none of the text that was sent"
    where = ", ".join(location.anchor.describe() for location in one.locations)
    note = " (an interpretation)" if one.in_an_interpretation else ""
    return f"{head}  -> {where}{note}"


def _coverage(report: AuditReport) -> list[str]:
    assessment = report.assessment
    counts = assessment.particular_counts()
    share = assessment.grounded_share
    lines = ["Coverage", f"{_INDENT}{assessment.coverage.describe()}"]
    if share is None:
        # Not "0%" and not "100%". An answer with nothing to check has not
        # scored, and a number here would be read as though it had.
        lines.append(f"{_INDENT}nothing in this answer could be checked")
    else:
        lines.append(
            f"{_INDENT}{counts[Standing.GROUNDED.value]} of "
            f"{counts[Standing.GROUNDED.value] + counts[Standing.FLOATING.value]} "
            f"particulars grounded ({share:.0%})"
        )
    return [*lines, ""]


def _provenance(report: AuditReport) -> list[str]:
    provenance = report.provenance
    lines = ["Provenance"]
    lines.append(f"{_INDENT}report {report.report_id}")
    if report.audited.package_id:
        lines.append(f"{_INDENT}package {report.audited.package_id}")
    if provenance.protection_by:
        lines.append(f"{_INDENT}protected by {provenance.protection_by}")
    if provenance.restored_by:
        lines.append(f"{_INDENT}{provenance.describe_restoration()}")
    if provenance.withheld:
        # Context, and worded so it cannot be read as an explanation of any
        # finding (ADR-0012). The package did not send these; akashi has no way
        # to know whether the model saw them, and does not imply that it did.
        listed = ", ".join(f"{count} {rule}" for rule, count in provenance.withheld)
        lines.append(f"{_INDENT}the package withheld {listed}")
        lines.append(f"{_INDENT}akashi cannot check an answer against withheld text")
    return [*lines, ""]


def _limits(report: AuditReport, width: int) -> list[str]:
    lines = ["What this does not establish"]
    for limit in report.assessment.limits:
        lines.extend(_wrap(limit, width - len(_INDENT)))
    return lines


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(f"{_INDENT}{current}")
            current = word
        else:
            current = candidate
    if current:
        lines.append(f"{_INDENT}{current}")
    return lines


def _clip(text: str, width: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def _s(count: int) -> str:
    return "" if count == 1 else "s"
