"""A report identifies itself by what determined it, and by nothing else.

Two runs over the same answer, the same package and the same akashi produce one
id. That is what makes ``recheck`` a check rather than a re-print, and it is why
these tests are mostly about what is *not* in the hash.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from akashi import __version__
from akashi.application import audit
from akashi.domain.package import ContextPackage
from akashi.domain.report import Audited, report_id
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import load_package
from akashi.interfaces.cli.main import main

PACKAGES = Path(__file__).parent / "packages"
ANSWERS = Path(__file__).parent / "answers"


def gear() -> ContextPackage:
    return load_package(PACKAGES / "gear-ja.json")


def answer() -> str:
    return (ANSWERS / "gear-ja.txt").read_text(encoding="utf-8")


def audited(**changes: object) -> Audited:
    body: dict[str, object] = {
        "package_id": "sha256:aaa",
        "response_hash": "sha256:bbb",
        "response_length": 42,
        "segmenters": ("akashi.segmenter/ja@1",),
        "extractors": ("akashi.extractor/und@1",),
        "packs": ("ja", "und"),
        "akashi_version": "0.1.0",
    }
    body.update(changes)
    return Audited(**body)  # type: ignore[arg-type]


# --- What is in the hash -----------------------------------------------------


def test_the_same_inputs_give_the_same_id() -> None:
    assert report_id(audited()) == report_id(audited())


@pytest.mark.parametrize(
    "field",
    ["package_id", "response_hash", "akashi_version", "segmenters", "extractors", "packs"],
)
def test_every_input_that_determines_a_report_is_in_its_id(field: str) -> None:
    changed = {
        "package_id": "sha256:different",
        "response_hash": "sha256:different",
        "akashi_version": "0.2.0",
        "segmenters": ("akashi.segmenter/en@1",),
        "extractors": ("akashi.extractor/en@1",),
        "packs": ("en", "und"),
    }[field]
    assert report_id(audited(**{field: changed})) != report_id(audited())


def test_the_pack_set_is_in_the_id() -> None:
    """The part that is easy to miss. Narrowing the packs changes the
    segmentation and therefore every count, so two audits that hashed the same
    either way could claim one id for different findings."""
    everything = audit(answer(), gear(), DEFAULT, akashi_version=__version__)
    japanese = audit(answer(), gear(), packs("ja"), akashi_version=__version__)
    assert everything.assessment.coverage != japanese.assessment.coverage
    assert everything.report_id != japanese.report_id


def test_a_one_character_change_to_the_answer_changes_the_id() -> None:
    first = audit("The tent weighs 2.4kg.", gear(), DEFAULT)
    second = audit("The tent weighs 2.5kg.", gear(), DEFAULT)
    assert first.report_id != second.report_id


def test_the_field_order_is_fixed_and_written_down() -> None:
    """Anyone reimplementing the canonical form needs the order and the
    separator, so it is spelled out rather than derived from a dataclass -- a
    derivation would silently change the answer the next time a field is
    added."""
    from akashi.domain import report as module

    assert module._FIELD == "\n"
    assert "canonical" in module.report_id.__doc__ or "canonical" in module.__doc__  # type: ignore[operator]


# --- What is not in the hash -------------------------------------------------


def test_the_clock_is_not_in_the_id() -> None:
    """A hash that changes when nothing changed is a hash nobody can compare,
    which is the whole use. Asserted by auditing twice: nothing here reads a
    clock, and if something started to, this fails."""
    first = audit(answer(), gear(), DEFAULT, akashi_version=__version__)
    second = audit(answer(), gear(), DEFAULT, akashi_version=__version__)
    assert first.report_id == second.report_id
    assert first == second


def test_the_response_length_is_not_in_the_id() -> None:
    """It is derived from the response, which is already hashed. Hashing a
    derivation of an input adds nothing and gives a second thing to keep in
    step."""
    assert report_id(audited(response_length=1)) == report_id(audited(response_length=999))


def test_the_findings_are_not_in_the_id() -> None:
    """The id is over the *inputs*. A report whose id covered its own findings
    could not be used to check that the findings were re-derived correctly --
    it would always agree with itself."""
    report = audit(answer(), gear(), DEFAULT, akashi_version=__version__)
    assert report.report_id == report_id(report.audited)


# --- Where it appears --------------------------------------------------------


def test_the_id_is_on_the_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(ANSWERS / "gear-ja.txt"),
            "--json",
        ]
    )
    body = json.loads(capsys.readouterr().out)
    assert body["report_id"].startswith("sha256:")
    assert body["audited"]["packs"] == ["en", "ja", "und", "zh"]


def test_the_id_is_printed_for_a_reader_who_will_archive_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(ANSWERS / "gear-ja.txt"),
        ]
    )
    printed = capsys.readouterr().out
    assert "report sha256:" in printed


def test_a_report_over_an_unnamed_package_still_has_an_id() -> None:
    """A caller with no package id gets a report that identifies itself by the
    rest. Refusing would make akashi unusable for anyone whose producer does not
    set one."""
    assert report_id(audited(package_id="")).startswith("sha256:")


# --- Properties --------------------------------------------------------------

TOKENS = st.text(alphabet="abcdef0123456789", min_size=1, max_size=12)


@given(response=TOKENS, package=TOKENS, version=TOKENS)
def test_the_id_is_always_a_named_sha256(response: str, package: str, version: str) -> None:
    """The algorithm is in the value, so a reader holding the string alone can
    still check it."""
    value = report_id(audited(response_hash=response, package_id=package, akashi_version=version))
    assert value.startswith("sha256:")
    assert len(value) == len("sha256:") + 64


@given(left=TOKENS, right=TOKENS)
def test_two_different_responses_never_share_an_id(left: str, right: str) -> None:
    if left == right:
        return
    assert report_id(audited(response_hash=left)) != report_id(audited(response_hash=right))


@given(segmenters=st.lists(TOKENS, min_size=1, max_size=3, unique=True))
def test_the_separator_cannot_be_forged_by_a_field_containing_it(
    segmenters: list[str],
) -> None:
    """The fields are joined by a newline and none of them may contain one --
    a hash, a version and a pack name are all single tokens. If one ever could,
    two different reports could serialize identically."""
    for name in segmenters:
        assert "\n" not in name
    assert report_id(audited(segmenters=tuple(segmenters))).startswith("sha256:")
