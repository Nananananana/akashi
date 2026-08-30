"""Extraction recall on prose nobody wrote for akashi.

The generated corpus measures the *detector* against known plants, and its
prose was authored for it -- so a high score there says the method works on
material designed for the method. This measures something harder and it is the
number that can falsify ADR-0004: **how much of a real answer does akashi
actually see?**

If it finds four particulars in a paragraph that holds nine, the coverage
figure on every report is honest and the product is not useful.

**The marking is by hand and by the definition, not by the implementation.** A
particular is marked where a person reading the sentence would say a wrong
value there changes what it means. So proper nouns are marked, and akashi
extracts none of them.

That is why the score is reported twice. *Over everything marked* is coverage:
how much of the answer akashi sees at all. *Over the kinds it claims* is
whether it does what it says. Publishing only the second would be scoring
against a boundary akashi drew for itself; publishing only the first would
count a declared limit as a defect.

The obvious objection stands and is not answered: the person who marked these
wrote the extractor. The rule above and the visibility of the markings in the
files are the mitigation, and a set drawn from real traffic would be worth more
than all of it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from akashi.domain.extraction import extract_from_answer
from akashi.domain.language import LanguagePack
from akashi.domain.particular import ParticularKind
from akashi.domain.segment import segment_answer
from akashi.domain.span import Span
from akashi.errors import ContractError

__all__ = [
    "ExtractionScore",
    "MarkedAnswer",
    "Marking",
    "load_marked",
    "score_extraction",
    "strip_markings",
]

_MARK = re.compile(r"\{\{P:([a-z_]+)\}\}(.*?)\{\{/P\}\}", re.DOTALL)

#: Kinds akashi says it does not extract. Reported separately rather than
#: excluded, because a declared limit counted as a defect is as misleading as a
#: defect counted as a limit.
DECLARED_ABSENT = frozenset({ParticularKind.PROPER_NOUN})


@dataclass(frozen=True, slots=True)
class Marking:
    """One particular a person marked, and where it sits."""

    kind: ParticularKind
    span: Span
    text: str

    @property
    def is_declared_absent(self) -> bool:
        return self.kind in DECLARED_ABSENT

    def describe(self) -> str:
        return f"{self.kind.value} {self.text!r} at [{self.span.start}:{self.span.end}]"


@dataclass(frozen=True, slots=True)
class MarkedAnswer:
    """A realistic answer, and every particular in it."""

    name: str
    language: str
    genre: str
    text: str
    markings: tuple[Marking, ...] = ()

    def __post_init__(self) -> None:
        for marking in self.markings:
            if marking.span.slice(self.text) != marking.text:
                raise ValueError(
                    f"{self.name}: {marking.describe()} does not slice back to its own text"
                )


def strip_markings(text: str) -> tuple[str, tuple[Marking, ...]]:
    """Remove the markup and compute where each marking ended up.

    An unknown kind is refused rather than dropped: a marking akashi silently
    ignored would lower recall by an amount nobody could see.
    """
    out: list[str] = []
    markings: list[Marking] = []
    at = 0
    for match in _MARK.finditer(text):
        out.append(text[at : match.start()])
        start = sum(len(piece) for piece in out)
        body = match.group(2)
        out.append(body)
        try:
            kind = ParticularKind(match.group(1))
        except ValueError:
            raise ContractError(
                f"the marking {match.group(1)!r} is not a particular kind akashi knows. "
                f"It knows {sorted(one.value for one in ParticularKind)}."
            ) from None
        markings.append(Marking(kind=kind, span=Span(start, start + len(body)), text=body))
        at = match.end()
    out.append(text[at:])
    return "".join(out), tuple(markings)


def load_marked(root: Path | str) -> tuple[MarkedAnswer, ...]:
    """Every marked answer under ``root``, in a fixed order.

    The name carries the language and the genre -- ``ja-contract-01.md`` -- so
    there is no metadata block to drift from the filename.
    """
    location = Path(root)
    if not location.is_dir():
        raise ContractError(f"no marked answers at {location}")

    found: list[MarkedAnswer] = []
    for path in sorted(location.glob("*.md")):
        if path.name == "README.md":
            continue
        parts = path.stem.split("-")
        if len(parts) < 3:
            raise ContractError(
                f"{path.name} is not named language-genre-number, so its language and "
                f"genre cannot be read from it"
            )
        text, markings = strip_markings(path.read_text(encoding="utf-8"))
        try:
            found.append(
                MarkedAnswer(
                    name=path.stem,
                    language=parts[0],
                    genre=parts[1],
                    text=text,
                    markings=markings,
                )
            )
        except ValueError as error:
            raise ContractError(f"{path.name}: {error}") from error
    if not found:
        raise ContractError(f"no marked answers under {location}")
    return tuple(found)


@dataclass(frozen=True, slots=True)
class ExtractionScore:
    """What akashi found, against what a person marked."""

    label: str = "all"
    #: Markings akashi extracted with exactly the same span.
    exact: int = 0
    #: Markings akashi extracted with a span that overlaps but differs. A
    #: boundary disagreement rather than a miss, and worth its own number: it
    #: is the difference between not seeing a figure and reporting it with the
    #: wrong edges.
    overlapping: int = 0
    marked: int = 0
    #: Of the above, the ones whose kind akashi says it does not extract.
    marked_declared_absent: int = 0
    found_declared_absent: int = 0
    #: Particulars akashi extracted that no marking covers.
    unmarked_extractions: int = 0
    extracted: int = 0
    segments: int = 0
    unbearing: int = 0
    misses: tuple[str, ...] = field(default_factory=tuple)
    surplus: tuple[str, ...] = field(default_factory=tuple)

    @property
    def found(self) -> int:
        return self.exact + self.overlapping

    @property
    def recall(self) -> float | None:
        """Over everything marked. Coverage, including the declared limits."""
        return self.found / self.marked if self.marked else None

    @property
    def recall_on_claimed_kinds(self) -> float | None:
        """Over the kinds akashi says it extracts. Whether it does what it says."""
        total = self.marked - self.marked_declared_absent
        found = self.found - self.found_declared_absent
        return found / total if total else None

    @property
    def precision(self) -> float | None:
        if not self.extracted:
            return None
        return (self.extracted - self.unmarked_extractions) / self.extracted

    @property
    def unbearing_share(self) -> float | None:
        return self.unbearing / self.segments if self.segments else None

    def __add__(self, other: ExtractionScore) -> ExtractionScore:
        return ExtractionScore(
            label=self.label,
            exact=self.exact + other.exact,
            overlapping=self.overlapping + other.overlapping,
            marked=self.marked + other.marked,
            marked_declared_absent=self.marked_declared_absent + other.marked_declared_absent,
            found_declared_absent=self.found_declared_absent + other.found_declared_absent,
            unmarked_extractions=self.unmarked_extractions + other.unmarked_extractions,
            extracted=self.extracted + other.extracted,
            segments=self.segments + other.segments,
            unbearing=self.unbearing + other.unbearing,
            misses=self.misses + other.misses,
            surplus=self.surplus + other.surplus,
        )


def _score_one(answer: MarkedAnswer, packs: Sequence[LanguagePack]) -> ExtractionScore:
    segmentation = segment_answer(answer.text, packs)
    particulars = extract_from_answer(segmentation, packs)
    spans = {particular.span for particular in particulars}

    exact = overlapping = found_absent = 0
    misses: list[str] = []
    for marking in answer.markings:
        if marking.span in spans:
            exact += 1
            found_absent += int(marking.is_declared_absent)
        elif any(span.overlaps(marking.span) for span in spans):
            overlapping += 1
            found_absent += int(marking.is_declared_absent)
        else:
            misses.append(f"{answer.name}: missed {marking.describe()}")

    surplus = [
        f"{answer.name}: extracted {particular.describe()}, which nothing marked"
        for particular in particulars
        if not any(particular.span.overlaps(marking.span) for marking in answer.markings)
    ]

    unbearing = sum(
        1
        for segment in segmentation.segments
        if not segment.is_code and not any(segment.span.contains(one.span) for one in particulars)
    )

    return ExtractionScore(
        label=answer.name,
        exact=exact,
        overlapping=overlapping,
        marked=len(answer.markings),
        marked_declared_absent=sum(1 for m in answer.markings if m.is_declared_absent),
        found_declared_absent=found_absent,
        unmarked_extractions=len(surplus),
        extracted=len(particulars),
        segments=len(segmentation.segments),
        unbearing=unbearing,
        misses=tuple(misses),
        surplus=tuple(surplus),
    )


def score_extraction(
    answers: Sequence[MarkedAnswer], packs: Sequence[LanguagePack]
) -> tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]]:
    """The overall score, and the same cut by language and by marked kind."""
    overall = ExtractionScore()
    languages: dict[str, ExtractionScore] = {}
    kinds: dict[str, ExtractionScore] = {}

    for answer in answers:
        score = _score_one(answer, packs)
        overall = overall + score
        languages[answer.language] = (
            languages.get(answer.language, ExtractionScore(answer.language)) + score
        )

        for kind in sorted({marking.kind for marking in answer.markings}, key=lambda k: k.value):
            single = _score_one(_only(answer, kind), packs)
            kinds[kind.value] = kinds.get(kind.value, ExtractionScore(kind.value)) + single

    return overall, dict(sorted(languages.items())), dict(sorted(kinds.items()))


def _only(answer: MarkedAnswer, kind: ParticularKind) -> MarkedAnswer:
    """The same answer with only one kind's markings.

    The per-kind recall is over that kind's markings; everything else about the
    answer -- what akashi extracted, how it segmented -- is unchanged, so the
    surplus count is not meaningful per kind and is not read there.
    """
    return MarkedAnswer(
        name=answer.name,
        language=answer.language,
        genre=answer.genre,
        text=answer.text,
        markings=tuple(marking for marking in answer.markings if marking.kind is kind),
    )
