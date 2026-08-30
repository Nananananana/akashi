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

from .marked import ExtractionScore
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


def extraction_text(score: ExtractionScore, by_language: dict[str, ExtractionScore]) -> list[str]:
    """Extraction against hand-marked answers, printed as two recalls.

    *Over everything marked* is coverage: how much of an answer akashi sees at
    all. *Over the kinds it claims* is whether it does what it says. Publishing
    only the second would score akashi against a boundary it drew for itself;
    publishing only the first would count a declared limit as a defect.
    """
    claimed_found = score.found - score.found_declared_absent
    claimed_total = score.marked - score.marked_declared_absent
    lines = [
        "Extraction, on hand-marked realistic answers",
        f"  recall over everything marked  {score.found:>5} of {score.marked:<5} "
        f"{_share(score.recall)}",
        f"  recall over the claimed kinds  {claimed_found:>5} of {claimed_total:<5} "
        f"{_share(score.recall_on_claimed_kinds)}",
        f"  spans exact rather than near   {score.exact:>5} of {score.found:<5}",
        f"  precision                      {score.extracted - score.unmarked_extractions:>5} "
        f"of {score.extracted:<5} {_share(score.precision)}",
        f"  unbearing segments             {score.unbearing:>5} of {score.segments:<5} "
        f"{_share(score.unbearing_share)}",
    ]
    for name, single in by_language.items():
        lines.append(
            f"  {name}  everything {_share(single.recall)}   "
            f"claimed {_share(single.recall_on_claimed_kinds)}"
        )
    return [*lines, ""]


def _share(value: float | None) -> str:
    return "  n/a" if value is None else f"{value:>5.0%}"


def as_text(
    breakdown: Breakdown,
    notes: list[str],
    *,
    cases: int,
    extraction: tuple[ExtractionScore, dict[str, ExtractionScore]] | None = None,
) -> str:
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

    if extraction is not None:
        lines += extraction_text(*extraction)

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
        "  The hand-marked answers are nine, written by one model in one sitting,",
        "  and marked by the person who wrote the extractor. That is the bias",
        "  ADR-0010 warns about, and the markings are in the files so anyone can",
        "  disagree with one.",
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


def as_dict(
    breakdown: Breakdown,
    notes: list[str],
    *,
    cases: int,
    extraction: tuple[ExtractionScore, dict[str, ExtractionScore]] | None = None,
) -> dict[str, Any]:
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
        "extraction": _extraction_body(extraction),
        "notes": notes,
    }


def _extraction_body(
    extraction: tuple[ExtractionScore, dict[str, ExtractionScore]] | None,
) -> dict[str, Any] | None:
    if extraction is None:
        return None
    score, by_language = extraction

    def body(one: ExtractionScore) -> dict[str, Any]:
        return {
            "marked": one.marked,
            "found": one.found,
            "exact": one.exact,
            "overlapping": one.overlapping,
            "recall": one.recall,
            "recall_on_claimed_kinds": one.recall_on_claimed_kinds,
            "precision": one.precision,
            "unbearing": one.unbearing,
            "segments": one.segments,
            "unbearing_share": one.unbearing_share,
        }

    return {
        "overall": body(score),
        "by_language": {name: body(one) for name, one in by_language.items()},
        "misses": list(score.misses),
        "surplus": list(score.surplus),
    }
