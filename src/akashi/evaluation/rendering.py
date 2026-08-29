"""The evaluation result, for a person and for a machine.

Grouped so that the three groups cannot be read as one number. *Detection* is
what akashi caught; *attribution* is what it could say about what it caught;
*integrity* is whether it behaved the same way twice. A single figure averaging
those would hide that they trade against each other.

Every rate prints its counts and its note. A share on its own is a number a
reader supplies their own denominator for, and they supply a generous one.
"""

from __future__ import annotations

from typing import Any

from .metrics import Breakdown, Rate

__all__ = ["as_dict", "as_text"]

_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Detection",
        (
            "fabrication recall",
            "false positives",
            "acknowledged false positives",
            "declared misses passed",
        ),
    ),
    ("Attribution", ("verdict correctness", "source localisation")),
    ("Integrity", ("refusals", "reproducibility")),
    ("Coverage", ("unbearing segments",)),
)


def _line(rate: Rate) -> str:
    if rate.share is None:
        return f"  {rate.name:<30} nothing to measure"
    return f"  {rate.name:<30} {rate.hit:>5} of {rate.total:<5} {rate.share:>5.0%}"


def as_text(breakdown: Breakdown, notes: list[str], *, cases: int) -> str:
    tally = breakdown.overall.tally
    rates = breakdown.overall.by_name()
    lines = [
        f"akashi eval — {cases} cases, {tally.particulars} particulars, {tally.segments} segments",
        "",
    ]

    for group, names in _GROUPS:
        lines.append(group)
        for name in names:
            lines.append(_line(rates[name]))
        lines.append("")

    lines += [
        "Not attributable to any plant",
        f"  floating particulars overlapping no plant   {tally.unattributed_floats}",
        f"  plants the segmenter cut in two             {tally.plants_split}",
        "",
    ]

    lines.append("By language")
    for name, score in breakdown.by_language.items():
        recall = score.fabrication_recall
        wrong = score.false_positive_rate
        lines.append(f"  {name}  recall {_short(recall)}   false positives {_short(wrong)}")
    lines.append("")

    lines.append("By plant kind")
    for name, score in breakdown.by_kind.items():
        lines.append(f"  {name:<24} {_kind_line(score.by_name())}")
    lines.append("")

    if notes:
        lines.append(f"Notes ({len(notes)})")
        lines.extend(f"  {note}" for note in notes[:25])
        if len(notes) > 25:
            lines.append(f"  ... and {len(notes) - 25} more")
        lines.append("")

    lines += [
        "What these numbers do not say",
        "  The corpus is generated. The prose was authored for it, the mix of",
        "  hallucinations was chosen rather than observed, and a score here is not",
        "  a score on production traffic.",
        "  Source localisation is structurally zero until v0.4: a floating",
        "  particular resolves nowhere, so it carries no location to check.",
        "  Declared misses passed is not a score to improve. It is the count of",
        "  hallucinations ADR-0004 says akashi cannot see, published rather than",
        "  hidden.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _short(rate: Rate) -> str:
    if rate.share is None:
        return "  n/a "
    return f"{rate.hit}/{rate.total} ({rate.share:.0%})"


def _kind_line(rates: dict[str, Rate]) -> str:
    for name in (
        "fabrication recall",
        "false positives",
        "acknowledged false positives",
        "declared misses passed",
        "refusals",
    ):
        rate = rates[name]
        if rate.total:
            return f"{name}: {_short(rate)}"
    return "nothing to measure"


def as_dict(breakdown: Breakdown, notes: list[str], *, cases: int) -> dict[str, Any]:
    def body(score_rates: dict[str, Rate]) -> dict[str, Any]:
        return {
            rate.name: {"hit": rate.hit, "total": rate.total, "share": rate.share}
            for rate in score_rates.values()
        }

    tally = breakdown.overall.tally
    return {
        "cases": cases,
        "segments": tally.segments,
        "particulars": tally.particulars,
        "overall": body(breakdown.overall.by_name()),
        "by_language": {
            name: body(score.by_name()) for name, score in breakdown.by_language.items()
        },
        "by_kind": {name: body(score.by_name()) for name, score in breakdown.by_kind.items()},
        "unattributed_floats": tally.unattributed_floats,
        "plants_split": tally.plants_split,
        "notes": notes,
    }
