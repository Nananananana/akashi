"""Composing a case, and the committed corpus that must still match.

ADR-0010. The prose is authored and the labels are computed, so what these
tests check is the computing: that an offset lands where the markup said, that
a seed changes the arrangement and never the material, and that the corpus on
disk is the corpus the generator produces.

That last one is not belt-and-braces. A generated case that is broken fails a
*correct* implementation, so the oracle has to be checked as often as the code
it is checking -- otherwise a bad fixture looks exactly like a regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from akashi.evaluation.case import PlantKind, Split, load_case, load_cases
from akashi.evaluation.generation import (
    GENERATOR,
    Document,
    GenreSpec,
    SentenceSpec,
    build_case,
    rendered,
    strip_facts,
    write_case,
)
from akashi.evaluation.genres import ALL, genres

CASES = Path(__file__).parent / "cases"
SEED = 20260830
PER_GENRE = 4


def corpus() -> tuple[object, ...]:
    return load_cases(CASES, splits=(Split.TRAIN, Split.HELD_OUT))


def generated() -> dict[str, str]:
    files: dict[str, str] = {}
    for spec in ALL:
        total = min(PER_GENRE, len(spec.sentences))
        for index in range(total):
            files.update(rendered(spec, SEED, index, total))
    return files


# --- Markup and offsets ------------------------------------------------------


def test_the_markup_is_stripped_and_the_offsets_computed() -> None:
    text, facts = strip_facts("テントは{{F:w}}2.4kg{{/F}}、二人用。", "doc_01")
    assert text == "テントは2.4kg、二人用。"
    assert len(facts) == 1
    assert facts[0].fact_id == "w"
    assert facts[0].text == "2.4kg"
    assert facts[0].span.slice(text) == "2.4kg"


def test_several_facts_in_one_paragraph_keep_their_own_offsets() -> None:
    text, facts = strip_facts("{{F:a}}2.4kg{{/F}} と {{F:b}}300g{{/F}} の合計。", "doc_01")
    assert [fact.span.slice(text) for fact in facts] == ["2.4kg", "300g"]
    assert facts[0].span.end < facts[1].span.start


def test_text_with_no_markup_is_unchanged() -> None:
    text, facts = strip_facts("何も印がついていない。", "doc_01")
    assert text == "何も印がついていない。"
    assert facts == ()


def test_a_fact_is_the_particular_and_not_the_clause_around_it() -> None:
    """So that a plant's ``was`` and the span its ``source`` names are the same
    string by construction, rather than by anyone remembering to keep them in
    step."""
    for spec in ALL:
        for document in spec.documents:
            _, facts = strip_facts("\n\n".join(document.paragraphs), document.document_id)
            for fact in facts:
                assert fact.text == fact.text.strip()
                assert "\n" not in fact.text


# --- The committed corpus ----------------------------------------------------


def test_the_committed_corpus_is_what_the_generator_produces() -> None:
    """The `--check-only` guard, as a test, because pytest is what a developer
    runs and CI is what catches what they forgot."""
    wanted = generated()
    for name, body in sorted(wanted.items()):
        path = CASES / name
        assert path.is_file(), f"{name} is missing from the committed corpus"
        assert path.read_text(encoding="utf-8") == body, (
            f"{name} differs from what the generator produces. Regenerate with the "
            f"same seed, or find out why the generator moved."
        )


def test_nothing_on_disk_is_missing_from_the_generator() -> None:
    wanted = set(generated())
    found = {
        f"{folder.name}/{child.name}"
        for folder in CASES.iterdir()
        if folder.is_dir()
        for child in folder.iterdir()
    }
    assert found - wanted == set(), "files on disk that the generator does not produce"


def test_every_committed_case_loads() -> None:
    cases = corpus()
    assert len(cases) == 42


def test_the_corpus_covers_three_languages_and_every_plant_kind() -> None:
    cases = corpus()
    assert {case.language for case in cases} == {"en", "ja", "zh"}  # type: ignore[attr-defined]
    planted = {
        plant.kind
        for case in cases
        for plant in case.plants  # type: ignore[attr-defined]
    }
    assert planted == set(PlantKind)


def test_no_plant_kind_is_too_thin_to_measure() -> None:
    """A rate over three plants is not a rate. The thinnest kinds here are the
    ones a genre carries once, and they are still one per genre per language."""
    counts: dict[PlantKind, int] = {}
    for case in corpus():
        for plant in case.plants:  # type: ignore[attr-defined]
            counts[plant.kind] = counts.get(plant.kind, 0) + 1
    thin = {kind.value: count for kind, count in counts.items() if count < 6}
    assert not thin, f"too few plants to measure: {thin}"


def test_the_held_out_split_is_a_real_split() -> None:
    held = [case for case in corpus() if case.split is Split.HELD_OUT]  # type: ignore[attr-defined]
    assert len(held) == 12
    assert {case.language for case in held} == {"en", "ja", "zh"}  # type: ignore[attr-defined]


def test_the_protected_cases_expect_a_refusal() -> None:
    """ADR-0008's path, in the corpus. An audit that reported on these instead
    of refusing would be the failure the whole admission stage exists for."""
    refusing = [case for case in corpus() if case.expect_refusal]  # type: ignore[attr-defined]
    assert len(refusing) == 6
    for case in refusing:
        assert case.package.is_protected  # type: ignore[attr-defined]
        assert "<PERSON_001>" in case.response  # type: ignore[attr-defined]


def test_every_case_names_the_generator_and_the_seed() -> None:
    for case in corpus():
        assert case.generator == GENERATOR  # type: ignore[attr-defined]
        assert case.seed == SEED  # type: ignore[attr-defined]


def test_the_packages_carry_omissions_for_the_paragraphs_that_were_not_sent() -> None:
    """Not decoration: it gives the report a withheld count to carry, which is
    the only thing akashi may say about an omission (ADR-0012)."""
    withheld = [
        case
        for case in corpus()
        if case.package.evidence.withheld  # type: ignore[attr-defined]
    ]
    assert withheld


# --- Composition -------------------------------------------------------------


TOY = GenreSpec(
    language="ja",
    genre="toy",
    question="重さは?",
    documents=(
        Document(
            document_id="doc_01",
            source_path="notes/toy.md",
            section="装備",
            paragraphs=("前置き。", "テントは{{F:w}}2.4kg{{/F}}。", "関係のない段落。"),
        ),
    ),
    sentences=(
        SentenceSpec(PlantKind.GROUNDED, "テントは2.4kgです。", "2.4kg", "w"),
        SentenceSpec(PlantKind.DIGIT_DRIFT, "テントは2.6kgです。", "2.6kg", "w"),
        SentenceSpec(PlantKind.FAITHFUL_PARAPHRASE, "かなり軽い部類に入ります。"),
        SentenceSpec(PlantKind.INVENTED_PARTICULAR, "ガスは250gでした。", "250g"),
    ),
)


def test_every_sentence_is_used_exactly_once_across_a_genre() -> None:
    """Coverage is a property of the data rather than of the draw, so a corpus
    cannot lose a plant kind to an unlucky seed."""
    used: list[str] = []
    for index in range(4):
        _, _, response, _ = build_case(TOY, SEED, index, 4)
        used.extend(sentence.text for sentence in TOY.sentences if sentence.text in response)
    assert sorted(used) == sorted(sentence.text for sentence in TOY.sentences)


def test_a_plant_lands_where_the_response_says_it_does(tmp_path: Path) -> None:
    case_id, package, response, manifest = build_case(TOY, SEED, 0, 4)
    write_case(tmp_path, case_id, package, response, manifest)
    case = load_case(tmp_path / case_id)
    for plant in case.plants:
        assert plant.span.slice(case.response) == plant.text


def test_the_labels_follow_from_the_kind_and_not_from_the_author(tmp_path: Path) -> None:
    """A spec says what a sentence *is*; what should follow is derived. A spec
    that could state its own expectations would be an annotation."""
    for index in range(4):
        case_id, package, response, manifest = build_case(TOY, SEED, index, 4)
        write_case(tmp_path, case_id, package, response, manifest)
        for plant in load_case(tmp_path / case_id).plants:
            if plant.kind is PlantKind.GROUNDED:
                assert not plant.expect_detected and not plant.is_hallucination
            if plant.kind is PlantKind.DIGIT_DRIFT:
                assert plant.expect_detected and plant.expect_verdict == "contradicted"
            if plant.kind is PlantKind.FAITHFUL_PARAPHRASE:
                assert plant.is_control


def test_a_plant_that_replaced_a_fact_carries_its_source(tmp_path: Path) -> None:
    for index in range(4):
        case_id, package, response, manifest = build_case(TOY, SEED, index, 4)
        write_case(tmp_path, case_id, package, response, manifest)
        for plant in load_case(tmp_path / case_id).plants:
            if plant.kind is PlantKind.DIGIT_DRIFT:
                assert plant.was == "2.4kg"
                assert plant.source is not None
                assert plant.source.document_id == "doc_01"


def test_a_paragraph_with_no_fact_becomes_an_omission(tmp_path: Path) -> None:
    case_id, package, response, manifest = build_case(TOY, SEED, 0, 4)
    write_case(tmp_path, case_id, package, response, manifest)
    case = load_case(tmp_path / case_id)
    assert len(case.package.evidence) == 1
    assert case.package.evidence.withheld_by_rule() == {"below_threshold": 2}


def test_a_target_that_occurs_twice_is_refused() -> None:
    """A plant needs one place to point at."""
    ambiguous = GenreSpec(
        language="ja",
        genre="ambiguous",
        question="?",
        documents=TOY.documents,
        sentences=(SentenceSpec(PlantKind.DIGIT_DRIFT, "2.6kg と 2.6kg。", "2.6kg", "w"),),
    )
    with pytest.raises(ValueError, match="one place to point at"):
        build_case(ambiguous, SEED, 0, 1)


# --- The seed ----------------------------------------------------------------


def test_the_same_seed_gives_the_same_corpus() -> None:
    """ADR-0003 reaches the fixtures. A corpus that differed between runs would
    make every score incomparable to the one before it."""
    assert rendered(TOY, SEED, 0, 4) == rendered(TOY, SEED, 0, 4)


def test_a_different_seed_rearranges_and_does_not_reinvent() -> None:
    def sentences(seed: int) -> list[str]:
        found: list[str] = []
        for index in range(4):
            _, _, response, _ = build_case(TOY, seed, index, 4)
            found.extend(s.text for s in TOY.sentences if s.text in response)
        return found

    first, second = sentences(SEED), sentences(SEED + 1)
    assert sorted(first) == sorted(second)


def test_the_seed_is_stable_across_processes() -> None:
    """``hash()`` is salted per process, so a corpus seeded with it would differ
    between runs on the same seed -- the one thing a seed exists to prevent."""
    import subprocess
    import sys

    script = (
        "import sys; sys.path.insert(0, 'src');"
        "from akashi.evaluation.genres import ALL;"
        "from akashi.evaluation.generation import rendered;"
        "print(rendered(ALL[0], 20260830, 0, 4)['en-contract-01/response.txt'], end='')"
    )
    runs = {
        # S603: the executable is this interpreter and the script is a
        # literal above. Nothing here comes from outside the test.
        subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={"PYTHONHASHSEED": seed, "PYTHONUTF8": "1", "PATH": ""},
            cwd=Path(__file__).parent.parent,
        ).stdout
        for seed in ("0", "1", "12345")
    }
    assert len(runs) == 1, "the corpus depends on PYTHONHASHSEED"
    assert runs.pop()


# --- The genre specs themselves ----------------------------------------------


def test_the_specs_can_be_narrowed_by_language() -> None:
    assert {spec.language for spec in genres("ja")} == {"ja"}
    assert genres() == ALL


def test_an_unknown_language_is_refused() -> None:
    with pytest.raises(ValueError, match="no genre specs for"):
        genres("ko")


def test_every_spec_carries_every_interesting_kind() -> None:
    """A genre that quietly stopped planting paraphrases would leave the
    false-positive rate measured on two thirds of the corpus and nobody would
    see it in the total."""
    wanted = {
        PlantKind.GROUNDED,
        PlantKind.DIGIT_DRIFT,
        PlantKind.UNIT_SWAP,
        PlantKind.INVENTED_PARTICULAR,
        PlantKind.DERIVED_VALUE,
        PlantKind.ENTITY_SWAP,
        PlantKind.NEGATION_FLIP,
        PlantKind.CROSS_DOCUMENT_STITCH,
        PlantKind.FAITHFUL_PARAPHRASE,
    }
    for spec in ALL:
        if spec.protected:
            continue
        found = {sentence.kind for sentence in spec.sentences}
        assert found == wanted, f"{spec.language}-{spec.genre} plants {found ^ wanted} oddly"


def test_every_named_fact_exists() -> None:
    """A sentence naming a fact its documents do not carry would fail only when
    that sentence happened to be drawn."""
    for spec in ALL:
        available = {
            fact.fact_id
            for document in spec.documents
            for fact in strip_facts("\n\n".join(document.paragraphs), document.document_id)[1]
        }
        named = {sentence.fact for sentence in spec.sentences if sentence.fact}
        assert named <= available, f"{spec.genre}: {sorted(named - available)} is planted nowhere"


def test_every_target_occurs_in_its_own_sentence() -> None:
    for spec in ALL:
        for sentence in spec.sentences:
            if sentence.target:
                assert sentence.text.count(sentence.target) == 1, (
                    f"{sentence.text!r} carries {sentence.target!r} "
                    f"{sentence.text.count(sentence.target)} times"
                )


def test_a_grounded_sentence_quotes_its_fact_verbatim() -> None:
    """The control is only a control if it really is in the sources. A grounded
    plant that had drifted would make the false-positive rate measure a
    typo."""
    for spec in ALL:
        facts = {
            fact.fact_id: fact.text
            for document in spec.documents
            for fact in strip_facts("\n\n".join(document.paragraphs), document.document_id)[1]
        }
        for sentence in spec.sentences:
            if sentence.kind is PlantKind.GROUNDED and sentence.fact:
                assert sentence.target == facts[sentence.fact], (
                    f"{spec.genre}: the grounded sentence {sentence.text!r} says "
                    f"{sentence.target!r} where the source says {facts[sentence.fact]!r}"
                )


def test_the_manifests_are_json_a_person_can_read() -> None:
    """CJK in escapes is a fixture nobody reviews, and a fixture nobody reviews
    is a fixture nobody notices going wrong."""
    body = (CASES / "ja-contract-01" / "case.json").read_text(encoding="utf-8")
    assert "\\u" not in body
    assert json.loads(body)["language"] == "ja"
