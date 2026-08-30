"""The number that can falsify ADR-0004.

The generated corpus measures the detector against known plants, and its prose
was authored for it. These are answers written the way a model answers, with
every particular marked by hand against ADR-0004's definition rather than
against what the extractor happens to find.

If akashi finds four particulars in a paragraph that holds nine, the coverage
figure on every report is honest and the product is not useful. That is the
falsification condition, and this is where it is checked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from akashi.domain.extraction import extract_from_answer
from akashi.domain.particular import ParticularKind
from akashi.domain.segment import segment_answer
from akashi.domain.span import Span
from akashi.errors import ContractError
from akashi.evaluation.marked import (
    DECLARED_ABSENT,
    ExtractionScore,
    MarkedAnswer,
    Marking,
    load_marked,
    score_extraction,
    strip_markings,
)
from akashi.infrastructure.languages import DEFAULT
from akashi.interfaces.cli.main import AUDITED, main

MARKED = Path(__file__).parent / "marked"
CASES = Path(__file__).parent / "cases"


@pytest.fixture(scope="module")
def measured() -> tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]]:
    return score_extraction(load_marked(MARKED), DEFAULT)


# --- The markup --------------------------------------------------------------


def test_the_markup_is_stripped_and_the_offsets_computed() -> None:
    text, markings = strip_markings("公差は{{P:quantity}}0.02mm{{/P}}です。")
    assert text == "公差は0.02mmです。"
    assert markings[0].kind is ParticularKind.QUANTITY
    assert markings[0].span.slice(text) == "0.02mm"


def test_a_marking_of_a_kind_akashi_does_not_know_is_refused() -> None:
    """A marking silently ignored would lower recall by an amount nobody could
    see."""
    with pytest.raises(ContractError, match="not a particular kind"):
        strip_markings("{{P:vibe}}something{{/P}}")


def test_a_marking_that_does_not_slice_back_is_refused() -> None:
    with pytest.raises(ValueError, match="does not slice back"):
        MarkedAnswer(
            name="x",
            language="ja",
            genre="x",
            text="short",
            markings=(Marking(ParticularKind.NUMBER, Span(0, 99), "nope"),),
        )


def test_a_file_that_does_not_name_its_language_is_refused(tmp_path: Path) -> None:
    (tmp_path / "answer.md").write_text("no markings", encoding="utf-8")
    with pytest.raises(ContractError, match="language-genre-number"):
        load_marked(tmp_path)


def test_an_empty_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="no marked answers"):
        load_marked(tmp_path)


# --- The set itself ----------------------------------------------------------


def test_the_answers_cover_three_languages_and_three_genres() -> None:
    answers = load_marked(MARKED)
    assert len(answers) == 9
    assert {answer.language for answer in answers} == {"en", "ja", "zh"}
    assert {answer.genre for answer in answers} == {"contract", "clinical", "engineering"}


def test_the_answers_mark_kinds_akashi_does_not_extract() -> None:
    """Marked by the definition, not by the implementation. A marking derived
    from the extractor would measure nothing."""
    marked = {marking.kind for answer in load_marked(MARKED) for marking in answer.markings}
    assert marked >= DECLARED_ABSENT


def test_the_answers_look_like_answers_rather_than_lists_of_figures() -> None:
    """Prose, tables and bullets, and sentences that carry nothing to check.

    Asserted on structure rather than on length: Chinese says in 160 characters
    what English needs 400 for, and a character threshold would be a threshold
    on the script.
    """
    joined = "\n".join(answer.text for answer in load_marked(MARKED))
    assert "|---|" in joined
    assert "\n- " in joined

    for answer in load_marked(MARKED):
        segmentation = segment_answer(answer.text, DEFAULT)
        particulars = extract_from_answer(segmentation, DEFAULT)
        assert len(segmentation.segments) >= 6, f"{answer.name} is too short to be an answer"
        bare = [
            segment
            for segment in segmentation.segments
            if not any(segment.span.contains(one.span) for one in particulars)
        ]
        assert bare, (
            f"{answer.name} is all figures. An answer with nothing in it that akashi "
            f"cannot check would measure the extractor on the easy half of its job."
        )


# --- What was measured -------------------------------------------------------


def test_every_particular_akashi_claims_to_extract_is_found(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    """The claimed-kinds recall. Whether akashi does what it says, as opposed
    to how much of an answer it sees."""
    overall, _, _ = measured
    assert overall.recall_on_claimed_kinds == 1.0


def test_the_only_misses_are_the_kinds_akashi_declares_it_does_not_extract(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    overall, _, _ = measured
    assert all("proper_noun" in miss for miss in overall.misses)


def test_the_spans_are_exact_and_not_merely_overlapping(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    """A boundary disagreement is not a miss and it is not a hit either: an
    offset with the wrong edges points a reader at the wrong text. This was
    seven before the sign and the year-month were fixed."""
    overall, _, _ = measured
    assert overall.overlapping == 0
    assert overall.exact == overall.found


def test_nothing_is_extracted_that_nobody_marked(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    overall, _, _ = measured
    assert overall.surplus == ()
    assert overall.precision == 1.0


def test_coverage_over_everything_marked_is_below_one_and_says_so(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    """The honest headline. Reporting only the claimed-kinds figure would score
    akashi against a boundary it drew for itself."""
    overall, _, _ = measured
    assert overall.recall is not None
    assert 0.85 < overall.recall < 1.0


def test_a_third_of_a_realistic_answer_bears_nothing_to_check(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    """The falsification condition from ``proposals/0001`` section 10: if most
    segments were unbearing, akashi would be silent about most of the answer
    and the roadmap would change. A third is not most, and it is far above the
    13% the generated corpus shows -- because that corpus was written to carry
    particulars."""
    overall, _, _ = measured
    assert overall.unbearing_share is not None
    assert 0.25 < overall.unbearing_share < 0.5


def test_the_score_is_cut_by_language_and_by_kind(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    _, by_language, by_kind = measured
    assert set(by_language) == {"en", "ja", "zh"}
    assert by_kind["proper_noun"].recall == 0.0
    assert by_kind["quantity"].recall == 1.0


def test_no_language_is_much_worse_than_the_others(
    measured: tuple[ExtractionScore, dict[str, ExtractionScore], dict[str, ExtractionScore]],
) -> None:
    """An aggregate hides that extraction is strong on Japanese figures and
    weak on English legal citations. This is the test that would notice."""
    _, by_language, _ = measured
    shares = [score.recall_on_claimed_kinds for score in by_language.values()]
    assert all(share == 1.0 for share in shares), dict(zip(by_language, shares, strict=True))


def test_measuring_twice_gives_the_same_numbers() -> None:
    answers = load_marked(MARKED)
    first, _, _ = score_extraction(answers, DEFAULT)
    second, _, _ = score_extraction(answers, DEFAULT)
    assert first == second


# --- Through the command line ------------------------------------------------


def test_eval_reports_extraction_when_the_marked_answers_are_there(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["eval", "--cases", str(CASES), "--marked", str(MARKED)]) == AUDITED
    printed = capsys.readouterr().out
    assert "Extraction, on hand-marked realistic answers" in printed
    assert "recall over everything marked" in printed
    assert "recall over the claimed kinds" in printed


def test_eval_skips_extraction_when_they_are_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Skipped rather than refused: the corpus and the marked answers measure
    different things, and a caller with one should get what it supports."""
    assert main(["eval", "--cases", str(CASES), "--marked", str(tmp_path / "none")]) == AUDITED
    assert "Extraction, on hand-marked" not in capsys.readouterr().out


def test_the_json_carries_both_recalls_and_the_misses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["eval", "--cases", str(CASES), "--marked", str(MARKED), "--json"])
    body = json.loads(capsys.readouterr().out)["extraction"]
    assert body["overall"]["recall"] < body["overall"]["recall_on_claimed_kinds"]
    assert body["misses"]
    assert set(body["by_language"]) == {"en", "ja", "zh"}


def test_the_caveat_about_who_marked_them_is_printed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The person who marked these wrote the extractor. That is the bias
    ADR-0010 warns about, and it travels with the number."""
    main(["eval", "--cases", str(CASES), "--marked", str(MARKED)])
    printed = capsys.readouterr().out
    assert "marked by the person who wrote the extractor" in printed
