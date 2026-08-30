"""Finding the particulars in a segment.

The algorithm; the rules it runs are data in ``infrastructure/languages/``
(ADR-0009). Nothing here knows which languages exist, which is what makes a
fourth language a data change.

**Every rule runs, and the overlaps are resolved afterwards.** The alternative
-- first rule to match at a position wins -- makes the answer depend on the
order the packs happened to load, and an audit that depends on an import order
is not reproducible (ADR-0003). So all candidates are collected and then
resolved by a total order: earliest start, then longest, then highest priority,
then kind name. ``第30条`` yields one reference rather than a reference and a
stray ``30``, and ``2026年8月30日`` yields one date rather than three numbers.

**A miss is silent and a false find is loud, and the first is worse.** A
particular that is not extracted is never checked, and the segment holding it
can still come back grounded -- which reads as "akashi looked at this" when it
did not. That asymmetry is why ``coverage`` publishes what was extracted and
``kinds_not_extracted`` names what no loaded rule covers (ADR-0005), and why
extraction recall is the number that can falsify ADR-0004 in v0.3.

Code is not extracted from at all. A number in a fenced block is as likely to
be a line number, an index or a hash as a claim about the world, and checking
it against prose sources would produce floating particulars that mean nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from functools import lru_cache

from .language import LanguagePack
from .particular import ExtractionRule, Particular, ParticularKind
from .segment import Segment, Segmentation
from .span import Span

__all__ = [
    "extract_from_answer",
    "extract_from_segment",
    "kinds_not_extracted",
    "rules_of",
]


@lru_cache(maxsize=512)
def _compiled(pattern: str) -> re.Pattern[str]:
    """Compiled once per pattern per process.

    The cache is keyed by the pattern text rather than by the rule object, so
    two packs that happen to share a pattern share the compilation and nothing
    depends on object identity.
    """
    return re.compile(pattern)


def rules_of(packs: Sequence[LanguagePack]) -> tuple[ExtractionRule, ...]:
    """Every rule the packs contribute, in a fixed order.

    Sorted by pack code and then by the rule's own pattern, so that the order
    is a property of the rules rather than of how they were passed in. Nothing
    in the algorithm depends on the order -- that is the point of resolving
    overlaps afterwards -- but a report that named them would, and a duplicate
    would be invisible without it.
    """
    found: list[tuple[str, ExtractionRule]] = []
    for pack in packs:
        found.extend((pack.code, rule) for rule in pack.rules)
    found.sort(key=lambda pair: (pair[0], pair[1].kind.value, pair[1].pattern, pair[1].group))
    return tuple(rule for _, rule in found)


def kinds_not_extracted(packs: Sequence[LanguagePack]) -> tuple[ParticularKind, ...]:
    """Kinds no loaded rule covers, sorted.

    Goes on every report. A kind that exists in the vocabulary and is found by
    nothing is a blind spot, and a blind spot that is not named reads as an
    absence of findings (ADR-0005).
    """
    covered = {rule.kind for rule in rules_of(packs)}
    return tuple(sorted(set(ParticularKind) - covered, key=lambda kind: kind.value))


def _candidates(text: str, rules: Iterable[ExtractionRule]) -> list[tuple[Span, ExtractionRule]]:
    found: list[tuple[Span, ExtractionRule]] = []
    for rule in rules:
        for match in _compiled(rule.pattern).finditer(text):
            # ``rule.group`` is how a rule matches its evidence without
            # capturing it: the honorific in ``田中医師`` is what makes ``田中``
            # a name and is not part of the name.
            start, end = match.span(rule.group)
            if start < 0 or end <= start:
                continue
            body = text[start:end]
            if not body.strip() or body in rule.reject:
                continue
            found.append((Span(start, end), rule))
    return found


def _resolve(candidates: list[tuple[Span, ExtractionRule]]) -> list[tuple[Span, ExtractionRule]]:
    """Greedily keep non-overlapping candidates under a total order.

    Earliest start wins, then the longest match, then the highest priority,
    then the kind's name. The last two are there only to make the order total:
    two rules that produce exactly the same span must not be separated by
    whichever was tried first.
    """
    candidates.sort(
        key=lambda pair: (pair[0].start, -len(pair[0]), -pair[1].priority, pair[1].kind.value)
    )
    kept: list[tuple[Span, ExtractionRule]] = []
    reach = 0
    for span, rule in candidates:
        if span.start < reach:
            continue
        kept.append((span, rule))
        reach = span.end
    return kept


def extract_from_segment(segment: Segment, packs: Sequence[LanguagePack]) -> tuple[Particular, ...]:
    """The particulars of one segment, in answer coordinates.

    Empty for a code segment, and empty for a segment that simply has no
    load-bearing token in it. The two are different -- one was skipped and one
    was looked at -- and telling them apart is the caller's job, because that
    distinction is what ``unbearing`` and ``unchecked`` are for.
    """
    if segment.is_code:
        return ()
    rules = rules_of(packs)
    kept = _resolve(_candidates(segment.text, rules))
    return tuple(
        Particular(
            kind=rule.kind,
            span=span.shifted(segment.span.start),
            text=segment.text[span.start : span.end],
            segment_id=segment.segment_id,
        )
        for span, rule in kept
    )


def extract_from_answer(
    segmentation: Segmentation, packs: Sequence[LanguagePack]
) -> tuple[Particular, ...]:
    """Every particular in a segmented answer, in order."""
    found: list[Particular] = []
    for segment in segmentation.segments:
        found.extend(extract_from_segment(segment, packs))
    return tuple(found)
