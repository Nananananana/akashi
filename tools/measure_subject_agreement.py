"""How often does a grounded value come from a sentence about something else?

Issue #83. `The tent weighs 2.4kg.` grounds against `The stove weighs 2.4kg.`
and akashi reports a share of 1.0, because a `Particular` is a value with no
subject and nothing asks what the sentence it landed in was about.

Before proposing any rule, this measures the ground truth the corpus already
carries. Two populations:

  grounded, and the case says the answer was faithful there
  grounded, and the case marks it a planted hallucination

If a signal separates those two, it is worth building on. If it does not, the
honest output is that number and no feature. This prints the distribution and
computes nothing that could be mistaken for a threshold.

    python tools/measure_subject_agreement.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from akashi.application.audit import audit
from akashi.domain.segment import segment_answer
from akashi.domain.span import Span
from akashi.domain.text import search_form
from akashi.errors import ProtectedResponseError
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package

CASES = Path(__file__).resolve().parents[1] / "tests" / "cases"


def bigrams(text: str) -> set[str]:
    """Character bigrams of the folded form.

    Characters rather than words: akashi reads Japanese and Chinese, where a
    word boundary is a model's opinion and this measurement must not depend on
    one. Bigrams rather than single characters because a shared `の` says
    nothing.
    """
    reduced = search_form(text).text
    return {reduced[index : index + 2] for index in range(len(reduced) - 1)}


def context_of(text: str, particular: str) -> set[str]:
    """What a sentence says apart from the value in question.

    The value itself is removed from both sides before comparing. Leaving it in
    would guarantee an overlap of exactly the thing that already matched, which
    is the measurement agreeing with itself.
    """
    return bigrams(text.replace(particular, " "))


@dataclass(frozen=True, slots=True)
class Observation:
    case: str
    particular: str
    planted: bool
    shared: int
    answer_terms: int
    source_terms: int

    @property
    def overlap(self) -> float:
        smaller = min(self.answer_terms, self.source_terms)
        return self.shared / smaller if smaller else 0.0


skipped: list[str] = []


def observations() -> Iterator[Observation]:
    for folder in sorted(CASES.iterdir()):
        case_file = folder / "case.json"
        if not case_file.is_file():
            continue
        case = json.loads(case_file.read_text(encoding="utf-8"))
        response = folder / "response.txt"
        if not response.is_file():
            continue
        answer = response.read_text(encoding="utf-8")
        package = load_package(folder / "package.json")
        # The two plant kinds that ARE #83, both declared undetectable by the
        # corpus itself: `entity_swap` ("a particular replaced by one of the
        # same kind from a different item -- it still resolves, so akashi passes
        # it") and `cross_document_stitch` ("subject from one item, predicate
        # from another, both verbatim").
        #
        # Filtering on `expect_detected` was the first attempt and it selected
        # against exactly this population: these are marked not-detected, which
        # is the defect being measured, not a reason to exclude them.
        planted = {
            str(plant.get("text", ""))
            for plant in case.get("plants", [])
            if plant.get("kind") in {"entity_swap", "cross_document_stitch"}
        }
        try:
            report = audit(answer, package, DEFAULT)
        except ProtectedResponseError:
            # A protected case needs a restorer, and this measurement is about
            # what a grounded value landed beside -- not about ADR-0008. Counted
            # as skipped rather than dropped, so the population is stated.
            skipped.append(folder.name)
            continue
        items = {entry.item_id: entry for entry in package.evidence.items}

        for segment in report.assessment.segments:
            for one in segment.particulars:
                for location in one.locations:
                    entry = items.get(location.item_id)
                    if entry is None:
                        continue
                    sentence = sentence_around(entry.text, entry.anchor.span, location)
                    if sentence is None:
                        continue
                    value = one.particular.text
                    left = context_of(segment.segment.text, value)
                    right = context_of(sentence, value)
                    yield Observation(
                        case=folder.name,
                        particular=value,
                        planted=value in planted,
                        shared=len(left & right),
                        answer_terms=len(left),
                        source_terms=len(right),
                    )


def sentence_around(text: str, item_span: Span, location: object) -> str | None:
    """The sentence of ``text`` holding the location, in the item's coordinates."""
    anchor = getattr(location, "anchor", None)
    if anchor is None:
        return None
    start = anchor.span.start - item_span.start
    end = anchor.span.end - item_span.start
    if start < 0 or end > len(text):
        return None
    for segment in segment_answer(text, DEFAULT).segments:
        if segment.span.start <= start and end <= segment.span.end:
            return segment.text
    return None


def main() -> None:
    found = list(observations())
    if not found:
        print("no grounded particular in the corpus reached a source sentence")
        return

    faithful = [one for one in found if not one.planted]
    planted = [one for one in found if one.planted]

    print(f"{len(found)} grounded particulars, {len(planted)} of them planted\n")
    print(f"  {'overlap of the sentence around the value':<44}  faithful  swapped")
    edges = [(0.0, 0.0), (0.0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 1.01)]
    for low, high in edges:
        label = "exactly 0 (share nothing)" if high == 0.0 else f"{low:.2f} - {high:.2f}"
        in_faithful = sum(1 for one in faithful if _within(one.overlap, low, high))
        in_planted = sum(1 for one in planted if _within(one.overlap, low, high))
        print(f"  {label:<44}  {in_faithful:>8}  {in_planted:>7}")

    zero_faithful = sum(1 for one in faithful if one.overlap == 0.0)
    print(
        f"\n  A rule refusing to ground on zero overlap would move "
        f"{zero_faithful} faithful and {sum(1 for one in planted if one.overlap == 0.0)} planted."
    )


def _within(value: float, low: float, high: float) -> bool:
    return value == 0.0 if high == 0.0 else low < value <= high


if __name__ == "__main__":
    main()
