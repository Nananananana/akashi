"""A case, and the refusal to trust an offset somebody typed.

ADR-0010. The manifest is ground truth only because every span in it can be
checked against the files it describes -- and this project has already paid for
the alternative once, when three of four hand-written fixture anchors were the
wrong length on their first run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from akashi.domain.span import Span
from akashi.errors import ContractError
from akashi.evaluation.case import (
    CASE_FORMAT,
    Case,
    Plant,
    PlantKind,
    Source,
    Split,
    load_case,
    load_cases,
)

ITEM = "テントは 2.4kg、二人用。前回より 300g 軽い。"
RESPONSE = "テントは 2.6kg、二人用です。\n前回より 300g 軽くなりました。\n"


def package_document(text: str = ITEM, start: int = 100) -> dict[str, Any]:
    return {
        "contract": "tsumugi.context-package/1",
        "package_id": "sha256:" + "0" * 64,
        "query": "テントの重量は?",
        "items": [
            {
                "item_id": "itm_01",
                "kind": "document_span",
                "text": text,
                "anchor": {
                    "document_id": "doc_01",
                    "source_path": "notes/gear.md",
                    "start": start,
                    "end": start + len(text),
                    "text_hash": "sha256:" + "1" * 64,
                    "document_hash": "sha256:" + "2" * 64,
                },
                "provenance": {"layer": "fact", "producer": "tsumugi.ingest/1"},
                "selection": {"rank": 1, "score": 0.9},
                "cost": 20,
            }
        ],
        "omissions": [],
        "budget": {
            "unit": "tokens",
            "limit": 400,
            "estimate": 20,
            "estimator": "heuristic/cjk-aware@1",
            "measured_error": {
                "p50": 0.03,
                "p95": 0.11,
                "against": "cl100k_base",
                "dataset": "ja-mixed-500",
            },
        },
        "provenance": {
            "tsumugi_version": "0.2.0",
            "providers": ["filesystem"],
            "protection": None,
        },
    }


def at(response: str, fragment: str) -> list[int]:
    """The span of ``fragment`` in ``response``, computed rather than typed.

    Every offset in every fixture here goes through this. A test that typed one
    would be testing the same thing the module refuses to do.
    """
    start = response.index(fragment)
    return [start, start + len(fragment)]


def write_case(
    folder: Path,
    *,
    response: str = RESPONSE,
    plants: list[dict[str, Any]] | None = None,
    manifest: dict[str, Any] | None = None,
    package: dict[str, Any] | None = None,
) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "response.txt").write_text(response, encoding="utf-8")
    (folder / "package.json").write_text(
        json.dumps(package if package is not None else package_document(), ensure_ascii=False),
        encoding="utf-8",
    )
    body: dict[str, Any] = {
        "format": CASE_FORMAT,
        "case_id": folder.name,
        "language": "ja",
        "genre": "mountaineering",
        "split": "train",
        "generator": "test",
        "seed": 1,
        "tier": ["ci"],
        "plants": plants if plants is not None else [],
    }
    if manifest:
        body.update(manifest)
    (folder / "case.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return folder


DRIFT: dict[str, Any] = {
    "kind": "digit_drift",
    "span": at(RESPONSE, "2.6kg"),
    "text": "2.6kg",
    "was": "2.4kg",
    "source": {"document_id": "doc_01", "span": [105, 110]},
    "expect_detected": True,
    "is_hallucination": True,
    "expect_verdict": "contradicted",
}

CONTROL: dict[str, Any] = {
    "kind": "grounded",
    "span": at(RESPONSE, "300g"),
    "text": "300g",
    "expect_detected": False,
    "is_hallucination": False,
}


# --- Reading a case -----------------------------------------------------------


def test_a_case_reads(tmp_path: Path) -> None:
    case = load_case(write_case(tmp_path / "ja-0001", plants=[DRIFT, CONTROL]))
    assert case.case_id == "ja-0001"
    assert case.language == "ja"
    assert case.genre == "mountaineering"
    assert case.split is Split.TRAIN
    assert case.in_ci_tier
    assert len(case.package.evidence) == 1
    assert case.response == RESPONSE


def test_a_plant_carries_what_was_done_and_what_should_follow(tmp_path: Path) -> None:
    case = load_case(write_case(tmp_path / "ja-0001", plants=[DRIFT]))
    plant = case.plants[0]
    assert plant.kind is PlantKind.DIGIT_DRIFT
    assert plant.text == "2.6kg"
    assert plant.was == "2.4kg"
    assert plant.source == Source(document_id="doc_01", span=Span(105, 110))
    assert plant.expect_verdict == "contradicted"
    assert "digit_drift" in plant.describe()


def test_the_plants_are_classified_three_ways(tmp_path: Path) -> None:
    """``expect_detected``, ``is_hallucination`` and ``declared_miss`` are three
    questions, not one, and the plants where they disagree are the reason the
    corpus is worth more than a hallucination benchmark."""
    stitch: dict[str, Any] = {
        "kind": "cross_document_stitch",
        "span": at(RESPONSE, "二人用です"),
        "text": "二人用です",
        "expect_detected": False,
        "is_hallucination": True,
        "declared_miss": True,
    }
    case = load_case(write_case(tmp_path / "ja-0001", plants=[DRIFT, CONTROL, stitch]))
    assert [plant.kind.value for plant in case.hallucinations] == [
        "digit_drift",
        "cross_document_stitch",
    ]
    assert [plant.kind.value for plant in case.controls] == ["grounded"]
    assert [plant.kind.value for plant in case.declared_misses] == ["cross_document_stitch"]


def test_a_derived_value_is_an_acknowledged_false_positive(tmp_path: Path) -> None:
    """Not a hallucination, and akashi flags it anyway, because it does no
    arithmetic. It gets its own number rather than being hidden in the others."""
    derived: dict[str, Any] = {
        "kind": "derived_value",
        "span": at(RESPONSE, "2.6kg"),
        "text": "2.6kg",
        "expect_detected": True,
        "is_hallucination": False,
    }
    plant = load_case(write_case(tmp_path / "ja-0001", plants=[derived])).plants[0]
    assert plant.is_acknowledged_false_positive
    assert not plant.is_control


def test_plants_can_be_selected_by_kind(tmp_path: Path) -> None:
    case = load_case(write_case(tmp_path / "ja-0001", plants=[DRIFT, CONTROL]))
    assert len(case.plants_of(PlantKind.DIGIT_DRIFT)) == 1
    assert case.plants_of(PlantKind.UNIT_SWAP) == ()


# --- The refusals ------------------------------------------------------------


def test_a_manifest_that_disagrees_with_its_response_is_refused(tmp_path: Path) -> None:
    """The check that makes an offset verifiable. Without the manifest carrying
    the text, an edited response would move every plant onto different words
    and the manifest would agree with itself all the way down."""
    wrong = dict(DRIFT, text="2.4kg")
    with pytest.raises(ContractError, match="disagrees with its own files"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_a_plant_with_no_text_is_refused(tmp_path: Path) -> None:
    plant = {key: value for key, value in DRIFT.items() if key != "text"}
    with pytest.raises(ContractError, match="has no 'text'"):
        load_case(write_case(tmp_path / "ja-0001", plants=[plant]))


def test_an_edited_response_is_caught_by_the_next_load(tmp_path: Path) -> None:
    folder = write_case(tmp_path / "ja-0001", plants=[DRIFT])
    load_case(folder)
    (folder / "response.txt").write_text("テントは 9.9kg です。\n", encoding="utf-8")
    with pytest.raises(ContractError, match="disagrees with its own files"):
        load_case(folder)


def test_a_source_the_package_does_not_hold_is_refused(tmp_path: Path) -> None:
    """A localisation target akashi could never reach is not a target."""
    wrong = dict(DRIFT, source={"document_id": "doc_99", "span": [0, 5]})
    with pytest.raises(ContractError, match="inside no item of the package"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_a_source_that_does_not_hold_what_it_claims_is_refused(tmp_path: Path) -> None:
    """The only part of the ground truth that can be checked against something
    other than itself, and it is the part source localisation is scored on."""
    wrong = dict(DRIFT, source={"document_id": "doc_01", "span": [100, 105]})
    with pytest.raises(ContractError, match="says the source holds"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_an_unknown_plant_kind_is_refused(tmp_path: Path) -> None:
    wrong = dict(DRIFT, kind="creative_liberty")
    with pytest.raises(ContractError, match="akashi does not know"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_an_unknown_split_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="akashi knows"):
        load_case(write_case(tmp_path / "ja-0001", manifest={"split": "validation"}))


def test_an_unknown_case_format_is_refused(tmp_path: Path) -> None:
    """A case written against an older format is refused rather than read with
    the wrong meaning. Same rule as the package reader, same reason."""
    with pytest.raises(ContractError, match="akashi reads"):
        load_case(write_case(tmp_path / "ja-0001", manifest={"format": "akashi.case/9"}))


def test_a_declared_miss_that_expects_detection_is_refused(tmp_path: Path) -> None:
    """A miss akashi is expected to catch is not a miss."""
    wrong = dict(DRIFT, declared_miss=True, expect_detected=True)
    with pytest.raises(ContractError, match="not a miss"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_a_span_that_is_not_two_offsets_is_refused(tmp_path: Path) -> None:
    wrong = dict(DRIFT, span=[5])
    with pytest.raises(ContractError, match="two-element span"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_a_backwards_span_is_refused(tmp_path: Path) -> None:
    wrong = dict(DRIFT, span=[10, 5], text="")
    with pytest.raises(ContractError, match="not a usable span"):
        load_case(write_case(tmp_path / "ja-0001", plants=[wrong]))


def test_a_case_with_no_manifest_is_refused(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(ContractError, match="cannot read"):
        load_case(tmp_path / "empty")


def test_a_manifest_that_is_not_json_is_refused(tmp_path: Path) -> None:
    folder = write_case(tmp_path / "ja-0001")
    (folder / "case.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError, match="not JSON"):
        load_case(folder)


def test_a_case_with_no_response_is_refused(tmp_path: Path) -> None:
    folder = write_case(tmp_path / "ja-0001")
    (folder / "response.txt").unlink()
    with pytest.raises(ContractError, match="cannot read"):
        load_case(folder)


def test_a_case_whose_package_is_unreadable_is_refused(tmp_path: Path) -> None:
    folder = write_case(tmp_path / "ja-0001")
    (folder / "package.json").write_text('{"contract": "nonsense/9"}', encoding="utf-8")
    with pytest.raises(ContractError, match="does not read"):
        load_case(folder)


# --- Loading a corpus --------------------------------------------------------


def test_a_corpus_loads_in_a_fixed_order(tmp_path: Path) -> None:
    """ADR-0003 reaches the measurement too: a score computed over cases in a
    different order every run is a score nobody can compare."""
    for name in ["ja-0003", "ja-0001", "ja-0002"]:
        write_case(tmp_path / name, plants=[DRIFT])
    assert [case.case_id for case in load_cases(tmp_path)] == ["ja-0001", "ja-0002", "ja-0003"]


def test_the_held_out_split_is_not_read_unless_it_is_asked_for(tmp_path: Path) -> None:
    """A held-out split that anything touches by default is a training split
    with a different name."""
    write_case(tmp_path / "ja-0001", plants=[DRIFT])
    write_case(tmp_path / "ja-0002", plants=[DRIFT], manifest={"split": "held_out"})

    assert [case.case_id for case in load_cases(tmp_path)] == ["ja-0001"]
    both = load_cases(tmp_path, splits=(Split.TRAIN, Split.HELD_OUT))
    assert [case.case_id for case in both] == ["ja-0001", "ja-0002"]


def test_a_tier_narrows_the_corpus(tmp_path: Path) -> None:
    write_case(tmp_path / "ja-0001", plants=[DRIFT])
    write_case(tmp_path / "ja-0002", plants=[DRIFT], manifest={"tier": []})
    assert [case.case_id for case in load_cases(tmp_path, tier="ci")] == ["ja-0001"]


def test_a_directory_that_is_not_a_case_is_ignored(tmp_path: Path) -> None:
    write_case(tmp_path / "ja-0001", plants=[DRIFT])
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.md").write_text("not a case", encoding="utf-8")
    assert len(load_cases(tmp_path)) == 1


def test_a_missing_corpus_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="no case directory"):
        load_cases(tmp_path / "nowhere")


# --- The values themselves ---------------------------------------------------


def test_a_plant_whose_span_disagrees_with_its_text_is_refused() -> None:
    with pytest.raises(ValueError, match="span covers"):
        Plant(kind=PlantKind.DIGIT_DRIFT, span=Span(0, 99), text="2.6kg")


def test_a_plant_covering_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="covers no text"):
        Plant(kind=PlantKind.DIGIT_DRIFT, span=Span(0, 0), text="")


def test_a_case_needs_an_id_to_be_reported_on() -> None:
    with pytest.raises(ValueError, match="cannot be reported on"):
        Case(case_id="", language="ja", genre="x", package=None, response="")  # type: ignore[arg-type]


def test_omitted_source_is_not_a_plant_kind() -> None:
    """ADR-0012 withdrew it: an omission carries no text to plant against, and
    a plant nothing can detect measures nothing."""
    assert "omitted_source" not in {kind.value for kind in PlantKind}
