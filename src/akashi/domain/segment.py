"""Cutting an answer into the pieces a verdict is reported about.

Every count on a report has the segmenter in its denominator, which makes this
the component least allowed to drift, and the reason a report names the packs
that produced it (ADR-0009).

Two passes, and the split matters.

**Structure first.** A model answering a question about figures replies with a
table as often as with a paragraph, and flattening a table into one sentence
would lose every particular's position. Headings, list items, table rows,
block quotes and fenced code are recognised as themselves, before any sentence
rule runs.

**Then sentences, inside prose only.** Boundaries are decided per character by
whichever pack claims that character (ADR-0011), so a Japanese paragraph with
one English sentence in it splits correctly at both kinds of terminator.

The invariant is weaker than "the segments tile the answer" and is the strongest
one that is true: segments are ordered, they do not overlap, and **everything
between them is whitespace.** Manufacturing empty segments to cover the blank
lines would tile it literally, at the price of a denominator full of segments
that assert nothing.

**Where a rule is unsure, it merges rather than splits.** An ellipsis is not a
boundary, and neither is a terminator inside brackets -- so ``「軽い。」と続く。``
is one segment rather than two. Both are deliberate under-segmentation and the
reasoning is the same: merging two sentences moves a denominator, splitting one
invents a segment, and only the second can invent a finding. The cost is a
longer span on a report, and ADR-0009's measurement is where it shows up.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from .language import LanguagePack, Script, script_of
from .span import Span

__all__ = ["Boundary", "Segment", "SegmentKind", "Segmentation", "segment_answer"]

#: Brackets a sentence may not end inside. Unambiguous pairs only: an ASCII
#: quote is both an opening and a closing one, so counting it would leave the
#: depth wrong for the rest of the block after any apostrophe.
_BRACKETS = {
    "「": "」",
    "『": "』",
    "（": "）",
    "(": ")",
    "【": "】",
    "《": "》",
    "〈": "〉",
    "[": "]",
}
_CLOSERS = frozenset(_BRACKETS.values())

#: Absorbed into the sentence that ends before them, so that ``軽い。」`` keeps
#: its closing bracket rather than starting the next segment with it.
_TRAILING = _CLOSERS | frozenset("\"'”’)")

_LIST_MARKERS = ("- ", "* ", "+ ", "・", "‐ ", "— ")
_FENCES = ("```", "~~~")


class SegmentKind(Enum):
    """What a segment is, structurally."""

    PROSE = "prose"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    TABLE_ROW = "table_row"
    QUOTE = "quote"
    CODE = "code"


class Boundary(Enum):
    """Why a segment ended where it did.

    ``LINE`` is the fallback ADR-0009 owes an account of: a prose block with no
    terminator anywhere in it, split by line because the alternative is one
    segment for a whole answer. A report can say how much of an answer was cut
    by the weaker rule, and that number is worth watching.
    """

    TERMINATOR = "terminator"
    STRUCTURE = "structure"
    LINE = "line"
    END = "end"


@dataclass(frozen=True, slots=True)
class Segment:
    """One piece of the answer, and where it sits in it."""

    segment_id: str
    span: Span
    text: str
    kind: SegmentKind
    script: Script
    boundary: Boundary

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError(f"{self.segment_id} is empty; a segment asserts something")
        if len(self.text) != len(self.span):
            raise ValueError(
                f"{self.segment_id} has {len(self.text)} characters but a span of "
                f"{len(self.span)}; an offset that has drifted points a reader at the "
                f"wrong sentence"
            )

    @property
    def is_prose(self) -> bool:
        return self.kind is SegmentKind.PROSE

    @property
    def is_code(self) -> bool:
        """Code is segmented and reported, and nothing is extracted from it.

        A number in a fenced block is as likely to be a line number or a hash
        as a claim about the world.
        """
        return self.kind is SegmentKind.CODE


@dataclass(frozen=True, slots=True)
class Segmentation:
    """An answer and the segments it was cut into.

    Constructing one checks the invariants, so an implementation that lost a
    character fails here rather than in a score three stages later.
    """

    answer: str
    segments: tuple[Segment, ...]
    #: The packs that produced this, by name, sorted. Goes on the report.
    segmenters: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        previous_end = 0
        for segment in self.segments:
            if segment.span.start < previous_end:
                raise ValueError(
                    f"{segment.segment_id} starts at {segment.span.start}, before the "
                    f"previous segment ended at {previous_end}"
                )
            if segment.span.end > len(self.answer):
                raise ValueError(f"{segment.segment_id} runs past the end of the answer")
            if segment.text != segment.span.slice(self.answer):
                raise ValueError(f"{segment.segment_id} does not slice back to its own text")
            gap = self.answer[previous_end : segment.span.start]
            if gap.strip():
                raise ValueError(
                    f"{gap.strip()[:40]!r} sits before {segment.segment_id} and is in no "
                    f"segment; everything between segments is whitespace or it is lost"
                )
            previous_end = segment.span.end
        if self.answer[previous_end:].strip():
            raise ValueError("text after the last segment is in no segment")

    def __len__(self) -> int:
        return len(self.segments)

    @property
    def fallback_share(self) -> float:
        """How much of the answer was cut by the weaker rule (ADR-0009).

        By characters rather than by segments, because one unsegmented
        paragraph and one short sentence are not the same amount of answer.
        """
        total = sum(len(s.span) for s in self.segments)
        if not total:
            return 0.0
        weak = sum(len(s.span) for s in self.segments if s.boundary is Boundary.LINE)
        return weak / total

    def of_kind(self, kind: SegmentKind) -> tuple[Segment, ...]:
        return tuple(s for s in self.segments if s.kind is kind)


# --- the algorithm -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Rule:
    """How one terminator character behaves."""

    needs_space_after: bool
    abbreviations: frozenset[str]


def _rules(packs: Sequence[LanguagePack]) -> dict[str, _Rule]:
    """Terminator -> behaviour, merged across the packs.

    Where two packs claim the same character they must agree about whether it
    needs a space after it; ``。`` behaves identically in Japanese and Chinese,
    and a disagreement would mean the answer depended on which pack loaded
    first. Abbreviation lists are unioned, because they are per-language
    vocabulary for a shared character rather than a claim about it.
    """
    rules: dict[str, _Rule] = {}
    for pack in sorted(packs, key=lambda p: p.code):
        for terminator in sorted(pack.terminators):
            existing = rules.get(terminator)
            if existing is None:
                rules[terminator] = _Rule(pack.needs_space_after, pack.abbreviations)
                continue
            if existing.needs_space_after != pack.needs_space_after:
                raise ValueError(
                    f"the packs disagree about {terminator!r}: one says it needs a space "
                    f"after it and another says it does not. A terminator behaves one way "
                    f"or the packs are describing two different characters."
                )
            rules[terminator] = _Rule(
                existing.needs_space_after, existing.abbreviations | pack.abbreviations
            )
    return rules


def _line_spans(answer: str) -> list[Span]:
    """Every line, trimmed of its own leading and trailing whitespace.

    Trimming here rather than later is what keeps ``\\r`` out of a segment's
    text on a document written on Windows, without any segment needing to know
    that line endings differ.
    """
    spans: list[Span] = []
    start = 0
    for index, character in enumerate(answer):
        if character == "\n":
            spans.append(_trimmed(answer, start, index))
            start = index + 1
    spans.append(_trimmed(answer, start, len(answer)))
    return spans


def _trimmed(text: str, start: int, end: int) -> Span:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return Span(start, end)


def _classify(line: str) -> SegmentKind:
    if line.startswith("#") and line.lstrip("#").startswith(" "):
        return SegmentKind.HEADING
    if line.startswith("|"):
        return SegmentKind.TABLE_ROW
    if line.startswith(">"):
        return SegmentKind.QUOTE
    if line.startswith(_LIST_MARKERS):
        return SegmentKind.LIST_ITEM
    head = line.split(" ", 1)[0]
    if len(head) > 1 and head[-1] in ".)、．" and head[:-1].isdigit():
        return SegmentKind.LIST_ITEM
    return SegmentKind.PROSE


def _blocks(answer: str) -> list[tuple[Span, SegmentKind]]:
    """The answer as structural blocks, in order, with the blank lines dropped."""
    lines = _line_spans(answer)
    blocks: list[tuple[Span, SegmentKind]] = []
    paragraph: list[Span] = []
    fence: tuple[int, str] | None = None

    def flush() -> None:
        if paragraph:
            blocks.append((Span(paragraph[0].start, paragraph[-1].end), SegmentKind.PROSE))
            paragraph.clear()

    for line in lines:
        text = line.slice(answer)
        if fence is not None:
            if text.startswith(fence[1]):
                blocks.append((Span(fence[0], line.end), SegmentKind.CODE))
                fence = None
            continue
        if text.startswith(_FENCES):
            flush()
            fence = (line.start, text[:3])
            continue
        if not text:
            flush()
            continue
        kind = _classify(text)
        if kind is SegmentKind.PROSE:
            paragraph.append(line)
            continue
        flush()
        blocks.append((line, kind))

    if fence is not None:
        # An unclosed fence runs to the end. Refusing would be the wrong trade:
        # a truncated answer is exactly the kind of thing worth auditing.
        blocks.append((_trimmed(answer, fence[0], len(answer)), SegmentKind.CODE))
    flush()
    return blocks


def _is_boundary(text: str, at: int, rules: dict[str, _Rule]) -> bool:
    """Whether the terminator at ``at`` really ends a sentence."""
    rule = rules[text[at]]
    if not rule.needs_space_after:
        return True

    character = text[at]
    if character == "." and _inside_a_number(text, at):
        return False
    # A run of dots is an ellipsis, and an ellipsis is more often a pause than
    # an end. Not splitting merges two sentences; splitting invents one. Both
    # move the denominator, and the merge is the one that cannot invent a
    # finding -- so this is a deliberate under-segmentation, and ADR-0009's
    # measurement is where its cost shows up.
    if character == "." and (text[at + 1 : at + 2] == "." or text[at - 1 : at] == "."):
        return False
    if character == "." and _is_an_initial(text, at):
        return False

    after = _run_end(text, at, rules)
    if after >= len(text):
        return True
    if not text[after].isspace():
        return False
    return not (character == "." and _is_an_abbreviation(text, at, rule.abbreviations))


def _run_end(text: str, at: int, rules: dict[str, _Rule]) -> int:
    """Where the terminator at ``at`` really finishes.

    ``?!`` ends a sentence once and not twice, and ``軽い。」`` keeps its closing
    bracket rather than handing it to the next segment. Any terminator absorbs
    any following terminator, whichever pack claims it, because a mixed run is
    a model's punctuation and not two sentences.
    """
    end = at + 1
    while end < len(text) and text[end] in rules:
        end += 1
    while end < len(text) and text[end] in _TRAILING:
        end += 1
    return end


def _inside_a_number(text: str, at: int) -> bool:
    return at > 0 and text[at - 1].isdigit() and at + 1 < len(text) and text[at + 1].isdigit()


def _is_an_initial(text: str, at: int) -> bool:
    """``J. Smith``. One letter, standing alone, followed by a full stop."""
    if at == 0 or not text[at - 1].isalpha() or not text[at - 1].isupper():
        return False
    return at == 1 or not text[at - 2].isalnum()


def _is_an_abbreviation(text: str, at: int, abbreviations: frozenset[str]) -> bool:
    start = at
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "."):
        start -= 1
    return text[start : at + 1].lower() in abbreviations


def _sentences(text: str, rules: dict[str, _Rule]) -> list[tuple[Span, Boundary]]:
    """Spans of ``text``, one per sentence, with why each ended.

    Returns an empty list when the block holds no terminator at all; the caller
    decides what the fallback is, because that is a policy question and this is
    the rule.
    """
    found: list[tuple[Span, Boundary]] = []
    start = 0
    depth = 0
    index = 0
    while index < len(text):
        character = text[index]
        if character in _BRACKETS:
            depth += 1
        elif character in _CLOSERS and depth:
            depth -= 1
        elif character in rules and not depth and _is_boundary(text, index, rules):
            end = _run_end(text, index, rules)
            span = _trimmed(text, start, end)
            if not span.is_empty:
                found.append((span, Boundary.TERMINATOR))
            start = end
            index = end
            continue
        index += 1

    if not found:
        return []
    tail = _trimmed(text, start, len(text))
    if not tail.is_empty:
        found.append((tail, Boundary.END))
    return found


def segment_answer(answer: str, packs: Sequence[LanguagePack]) -> Segmentation:
    """Cut ``answer`` into segments, using the rules ``packs`` carry.

    Deterministic and total: the same answer and the same packs give the same
    segments, and every non-whitespace character ends up in exactly one of them.
    """
    if not packs:
        raise ValueError("segmentation needs at least one language pack")
    rules = _rules(packs)
    segments: list[Segment] = []

    def emit(span: Span, kind: SegmentKind, boundary: Boundary) -> None:
        text = span.slice(answer)
        segments.append(
            Segment(
                segment_id=f"seg_{len(segments) + 1:03d}",
                span=span,
                text=text,
                kind=kind,
                script=script_of(text),
                boundary=boundary,
            )
        )

    for span, kind in _blocks(answer):
        if span.is_empty:
            continue
        if kind is not SegmentKind.PROSE:
            emit(span, kind, Boundary.STRUCTURE)
            continue
        block = span.slice(answer)
        sentences = _sentences(block, rules)
        if sentences:
            for inner, boundary in sentences:
                emit(inner.shifted(span.start), kind, boundary)
            continue
        # No terminator anywhere in the block. Line boundaries are the weaker
        # rule, and every segment produced this way says so (ADR-0009).
        for line in _line_spans(block):
            if not line.is_empty:
                emit(line.shifted(span.start), kind, Boundary.LINE)

    return Segmentation(
        answer=answer,
        segments=tuple(segments),
        # Only the packs that actually claimed a terminator. The shared numeric
        # pack contributes extraction rules and no punctuation, and naming it
        # here would tell a reader that something took part in segmentation
        # when it did not.
        segmenters=tuple(sorted(pack.name for pack in packs if pack.terminators)),
    )
