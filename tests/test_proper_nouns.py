"""A name is a name because of what sits beside it.

`proper_noun` was the whole coverage gap: extraction recall was 100% over the
kinds akashi claimed and 91% over everything a person marked, and all nine
misses were names.

**The rules are structural and that is the point.** A token in front of
`株式会社`, behind `Dr.`, or in front of `医師` is a name *because of the
structure*, which is evidence and fits ADR-0001 and ADR-0003. A capitalised-word
heuristic is not: it would put a particular on every sentence-initial word in
English and akashi would be guessing.

**akashi is precision-first, and `mamori` is not.** Its Japanese name detector
is far larger and recall-first by policy (its ADR-0013): it would rather
over-detect a name than leak one. Here a false proper noun is a floating
particular on every report that mentions an ordinary word, so most of these
tests are about what must *not* be found.
"""

from __future__ import annotations

import pytest

from akashi.domain.extraction import extract_from_answer
from akashi.domain.particular import ParticularKind
from akashi.domain.segment import segment_answer
from akashi.infrastructure.languages import DEFAULT


def names(answer: str) -> list[str]:
    segmentation = segment_answer(answer, DEFAULT)
    return [
        particular.text
        for particular in extract_from_answer(segmentation, DEFAULT)
        if particular.kind is ParticularKind.PROPER_NOUN
    ]


# --- What the structure says is a name ---------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("担当は田中医師です。", ["田中"]),
        ("佐藤さんに確認しました。", ["佐藤"]),
        ("山田氏の見解によれば。", ["山田"]),
        ("鈴木教授が指導しています。", ["鈴木"]),
        ("担当弁護士は高橋弁護士です。", ["高橋"]),
        ("株式会社さくら商事と契約。", ["株式会社さくら商事"]),
        ("有限会社みどりから見積を取得。", ["有限会社みどり"]),
        ("大和証券が引受先です。", ["大和証券"]),
    ],
)
def test_japanese_names_with_structure_beside_them(answer: str, expected: list[str]) -> None:
    assert names(answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("主治医师为李医生。", ["李"]),
        ("负责人为王经理。", ["王"]),
        ("张教授出席了会议。", ["张"]),
        ("北京华兴科技有限公司提供。", ["北京华兴科技有限公司"]),
        ("由中信证券承销。", ["中信证券"]),
    ],
)
def test_chinese_names_with_structure_beside_them(answer: str, expected: list[str]) -> None:
    assert names(answer) == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("The note is signed by Dr. Okafor.", ["Okafor"]),
        ("Reviewed by Prof. Anne Whitfield.", ["Anne Whitfield"]),
        ("Ms. Chen approved it.", ["Chen"]),
        ("Acme Ltd is the counterparty.", ["Acme Ltd"]),
        ("Signed with Borden Systems Inc.", ["Borden Systems Inc."]),
        ("Nordwind Handels GmbH supplied them.", ["Nordwind Handels GmbH"]),
    ],
)
def test_english_names_with_structure_beside_them(answer: str, expected: list[str]) -> None:
    assert names(answer) == expected


def test_the_marker_is_evidence_and_not_part_of_the_name() -> None:
    """``田中`` is the person and ``医師`` is the role. The pattern looks ahead
    so the evidence is matched without being captured."""
    assert names("担当は田中医師です。") == ["田中"]
    assert names("The note is signed by Dr. Okafor.") == ["Okafor"]


def test_a_legal_form_is_part_of_the_name() -> None:
    """Unlike a title. ``Acme Ltd`` is the company's name and ``Ltd`` is in it;
    ``Dr.`` is not part of anybody's."""
    assert names("Acme Ltd is the counterparty.") == ["Acme Ltd"]


# --- What must not be found --------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "皆さんお疲れ様でした。",
        "彼氏と相談しました。",
        "主治医師の判断による。",
        "弊社の規定では認められません。",
        "当社および他社の比較。",
        "貴社のご意向を確認します。",
        "各部門の担当者が対応します。",
    ],
)
def test_an_ordinary_japanese_word_is_not_a_name(answer: str) -> None:
    """One of these on every report is what makes a precision-first extractor
    worthless."""
    assert names(answer) == []


def test_the_ambiguous_honorific_was_dropped_and_the_cost_is_known() -> None:
    """``様`` ends 仕様, 模様, 多様, 同様 -- words that live in exactly the
    specification and contract documents akashi is aimed at. It put a name on
    ``筐体仕様`` on the first measured run.

    Dropping it costs ``佐藤様``, and that loss is asserted here rather than
    discovered later. One false proper noun per specification is worse.
    """
    assert names("筐体仕様の改訂について。") == []
    assert names("同様の対応を取ります。") == []
    assert names("佐藤様よりご連絡がありました。") == []


@pytest.mark.parametrize(
    "answer",
    [
        "主治医生说明了情况。",
        "各部门经理出席了会议。",
        "前任经理已离职。",
        "责任经理需要签字。",
        "总经理办公室在三楼。",
    ],
)
def test_an_ordinary_chinese_word_is_not_a_name(answer: str) -> None:
    assert names(answer) == []


def test_a_chinese_name_needs_a_connector_before_it() -> None:
    """Chinese has no spaces, so a name is always preceded by a character. A
    lookbehind on "not a kanji" rejects every real case and lets a wrong one
    through, because the engine restarts one character later and takes ``治``
    out of ``主治医生``. Requiring a connector is *more* evidence, not less."""
    assert names("主治医师为李医生。") == ["李"]
    assert names("主治医生说明了情况。") == []


@pytest.mark.parametrize(
    "answer",
    [
        "The tent weighs 2.4kg and the stove 300g.",
        "Either party may terminate on 30 days notice.",
        "Liability is capped under Art. 12.",
        "Assembly is covered in the companion volume.",
    ],
)
def test_ordinary_english_prose_yields_no_names(answer: str) -> None:
    """No capitalised-word heuristic. It would put a particular on every
    sentence-initial word, and akashi would be guessing rather than reading."""
    assert names(answer) == []


def test_a_sentence_initial_capital_is_not_a_name() -> None:
    assert names("Liability is capped at 45,000 dollars.") == []
    assert names("September was the month it was signed.") == []


# --- How the rules are built -------------------------------------------------


def test_an_organisation_name_does_not_swallow_the_sentence_after_it() -> None:
    """The tempered character class, borrowed from ``mamori``: a greedy run of
    kana otherwise takes the rest of the sentence, and
    ``株式会社さくら商事の田中さん`` comes back as one name ending in ``の田中``."""
    assert names("株式会社さくら商事の田中さんに確認。") == ["株式会社さくら商事", "田中"]


def test_a_rejected_match_is_data_and_not_a_callable() -> None:
    """A rule stays a value. A pattern with a function attached could not be
    compared, printed or reasoned about from a report."""
    from akashi.domain.extraction import rules_of

    rejecting = [rule for rule in rules_of(DEFAULT) if rule.reject]
    assert rejecting
    for rule in rejecting:
        assert isinstance(rule.reject, frozenset)
        assert all(isinstance(word, str) for word in rule.reject)


def test_a_group_may_not_be_negative() -> None:
    from akashi.domain.particular import ExtractionRule

    with pytest.raises(ValueError, match="names group"):
        ExtractionRule(kind=ParticularKind.PROPER_NOUN, pattern="x", group=-1)


def test_names_are_particulars_like_any_other() -> None:
    """They ground, they float, and they carry a span. Nothing about the kind
    changes how it is checked."""
    from akashi.domain.evidence import Evidence, item

    evidence = Evidence.of([item("itm_01", "担当は田中医師、期限は 2026年8月30日。")])
    segmentation = segment_answer("担当は田中医師です。", DEFAULT)
    found = extract_from_answer(segmentation, DEFAULT)
    assert [one.kind for one in found] == [ParticularKind.PROPER_NOUN]
    assert evidence.locate(found[0])

    other = segment_answer("担当は佐藤医師です。", DEFAULT)
    assert not evidence.locate(extract_from_answer(other, DEFAULT)[0])
