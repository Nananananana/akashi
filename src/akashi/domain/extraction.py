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


#: The longest run a single repetition in a rule may match.
#:
#: **This is a bound on the cost of an audit, and it is set the way a floor is**
#: (see `evaluation/floors.py`): deliberately far above what was measured, with
#: the gap stated. Over the whole corpus the longest particular is **21
#: characters**, the 99th percentile is 14, and the longest evidence item or
#: segment is 94. A run of 256 is an order of magnitude past all of them.
#:
#: Without it, akashi is quadratic in the length of a segment, and the input is
#: untrusted by construction -- auditing text a model produced is the whole job,
#: and `akashi mcp` lets the model choose the arguments. Measured before the
#: bound, end to end:
#:
#: ..  code-block:: text
#:
#:     16,000 characters of ordinary prose   0.09 s
#:     16,000 characters of digits          38.09 s      x4.0 per doubling
#:
#: The cause is the ordinary "long prefix matches, short suffix fails" shape:
#: ``\d[\d,.]*\d`` followed by a unit consumes the run, fails to find the unit,
#: and retries at every shorter length, at every start position. Nothing exotic,
#: nothing that reads as a mistake, and 32 of the 40 shipped rules have the
#: shape.
#:
#: A *time* limit was the obvious alternative and is not available: an audit is
#: reproducible (ADR-0003), and a run that gives up after a second gives a
#: different report on a slower machine.
MAX_RUN = 256


def _bounded(pattern: str, limit: int = MAX_RUN) -> str:
    """``pattern`` with every unbounded repetition capped at ``limit``.

    ``*`` becomes ``{0,limit}``, ``+`` becomes ``{1,limit}``, ``{n,}`` becomes
    ``{n,limit}``; a lazy or possessive modifier is carried across. Written as a
    scanner rather than a regular expression over a regular expression, because
    the two places this has to be exactly right -- inside a character class, and
    after a backslash -- are the two places that reading is hardest.

    A rewritten rule is not the rule as written, so this is checked rather than
    trusted: `tests/test_extraction.py` asserts every shipped pattern still
    compiles, that no compiled pattern contains an unbounded repeat, and that
    the whole corpus extracts **the same particulars, in the same order, at the
    same offsets** with the bound in place.
    """
    out: list[str] = []
    index = 0
    inside_class = False
    while index < len(pattern):
        character = pattern[index]

        if character == "\\" and index + 1 < len(pattern):
            out.append(pattern[index : index + 2])
            index += 2
            continue

        if inside_class:
            out.append(character)
            index += 1
            if character == "]":
                inside_class = False
            continue

        if character == "[":
            # `[]]` and `[^]]` hold a literal `]` first; consuming it here is
            # what keeps the class from ending on its own opening bracket.
            out.append(character)
            index += 1
            if index < len(pattern) and pattern[index] == "^":
                out.append("^")
                index += 1
            if index < len(pattern) and pattern[index] == "]":
                out.append("]")
                index += 1
            inside_class = True
            continue

        if character in "*+":
            out.append("{0," if character == "*" else "{1,")
            out.append(f"{limit}}}")
            index += 1
            if index < len(pattern) and pattern[index] in "?+":
                out.append(pattern[index])
                index += 1
            continue

        if character == "{":
            closing = pattern.find("}", index)
            body = pattern[index + 1 : closing] if closing != -1 else ""
            if closing != -1 and body.endswith(",") and body[:-1].isdigit():
                out.append(f"{{{body}{limit}}}")
                index = closing + 1
                continue

        out.append(character)
        index += 1
    return "".join(out)


@lru_cache(maxsize=512)
def _compiled(pattern: str) -> re.Pattern[str]:
    """Compiled once per pattern per process, with its repetitions bounded.

    The cache is keyed by the pattern text rather than by the rule object, so
    two packs that happen to share a pattern share the compilation and nothing
    depends on object identity.
    """
    return re.compile(_bounded(pattern))


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
