"""The whole pipeline, from a package and an answer to a report.

The use case decides nothing -- every verdict is domain's -- so what is checked
here is the order of the stages, the provenance the report carries, and the
refusals that stop it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from akashi import __version__
from akashi.application import audit
from akashi.domain.evidence import Evidence
from akashi.domain.package import ContextPackage
from akashi.domain.report import CONTRACT
from akashi.domain.verdict import Verdict
from akashi.errors import ProtectedResponseError
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages import load_package

PACKAGES = Path(__file__).parent / "packages"
ANSWERS = Path(__file__).parent / "answers"


def gear() -> ContextPackage:
    return load_package(PACKAGES / "gear-ja.json")


def answer_text() -> str:
    return (ANSWERS / "gear-ja.txt").read_text(encoding="utf-8")


# --- The report -------------------------------------------------------------


def test_an_answer_is_audited_against_its_package() -> None:
    report = audit(answer_text(), gear(), DEFAULT)
    assert report.contract == CONTRACT
    verdicts = [segment.verdict for segment in report.assessment.segments]
    assert Verdict.FLOATING in verdicts
    assert Verdict.GROUNDED in verdicts


def test_the_report_names_what_it_audited_and_what_did_the_auditing() -> None:
    """Every count has the segmenter in its denominator, so a recheck that
    produced different numbers can attribute the difference (ADR-0009)."""
    report = audit(answer_text(), gear(), DEFAULT, akashi_version=__version__)
    assert report.audited.package_id.startswith("sha256:")
    assert report.audited.response_hash.startswith("sha256:")
    assert report.audited.response_length == len(answer_text())
    assert report.audited.segmenters == (
        "akashi.segmenter/en@1",
        "akashi.segmenter/ja@1",
        "akashi.segmenter/zh@1",
    )
    assert "akashi.extractor/und@1" in report.audited.extractors
    assert report.audited.akashi_version == __version__


def test_the_report_carries_what_the_package_withheld_as_context() -> None:
    report = audit(answer_text(), gear(), DEFAULT)
    assert report.provenance.withheld == (("budget_exhausted", 1), ("redundant_candidate", 1))


def test_the_report_summary_does_not_lead_with_the_score() -> None:
    """A reader takes away the score whatever else is on the page, so what
    precedes it is what bounds it."""
    summary = audit(answer_text(), gear(), DEFAULT).summary()
    assert summary.startswith("5 segments, 2 not checked")
    assert summary.endswith("75% grounded")


def test_an_answer_with_nothing_checkable_says_so_rather_than_scoring() -> None:
    report = audit("The tent was light and easy to carry.", gear(), DEFAULT)
    assert report.assessment.grounded_share is None
    assert "nothing checkable" in report.summary()


def test_an_empty_package_grounds_nothing() -> None:
    """ADR-0006's floor. Correct, useless, and the coverage numbers are what
    say so."""
    empty = ContextPackage(contract="tsumugi.context-package/1", evidence=Evidence())
    report = audit("The tent weighs 2.4kg.", empty, DEFAULT)
    assert report.assessment.grounded_share == 0.0
    assert report.has_findings


# --- Provenance and refusal ---------------------------------------------------


def test_a_protected_answer_is_refused_by_the_use_case_too() -> None:
    """The refusal is in ``admit`` and the use case does not swallow it. A
    pipeline calling ``audit`` gets the same answer as one calling ``admit``."""
    protected = load_package(PACKAGES / "protected-ja.json")
    with pytest.raises(ProtectedResponseError):
        audit("<PERSON_001> は担当です。", protected, DEFAULT)


def test_an_asserted_restoration_reaches_the_report_as_an_assertion() -> None:
    protected = load_package(PACKAGES / "protected-ja.json")
    report = audit(
        "田中は 第30条 の対応を担当し、期限は 2026年8月30日。",
        protected,
        DEFAULT,
        restored_by="mamori@0.17.0",
    )
    assert report.provenance.restoration_asserted
    assert report.provenance.protection_by == "mamori@0.17.0"
    assert report.provenance.describe_restoration() == (
        "asserted restored by mamori@0.17.0; akashi did not verify it"
    )


def test_an_unprotected_answer_reports_no_restoration() -> None:
    report = audit(answer_text(), gear(), DEFAULT)
    assert report.provenance.describe_restoration() == "not restored"
    assert report.provenance.protection_by == ""


# --- Injection ----------------------------------------------------------------


def test_the_packs_are_passed_in_rather_than_imported() -> None:
    """The application layer does not know which languages exist. Narrowing
    them changes the report, which is how you can tell they are really used."""
    everything = audit(answer_text(), gear(), DEFAULT)
    japanese_only = audit(answer_text(), gear(), packs("ja"))
    assert everything.audited.segmenters != japanese_only.audited.segmenters
    assert japanese_only.audited.segmenters == ("akashi.segmenter/ja@1",)


def test_a_narrower_pack_set_widens_what_no_rule_covers() -> None:
    report = audit(answer_text(), gear(), packs("ja"))
    assert "duration" in report.assessment.coverage.kinds_not_extracted


# --- Reproducibility ----------------------------------------------------------


def test_auditing_the_same_answer_twice_gives_the_same_report() -> None:
    """ADR-0003. There is no flag that turns a model on, and nothing here reads
    a clock."""
    assert audit(answer_text(), gear(), DEFAULT) == audit(answer_text(), gear(), DEFAULT)


def test_the_response_hash_is_over_the_text_that_was_audited() -> None:
    """Not the text that was passed in. When a restorer ran, the two differ,
    and the report is about what akashi looked at."""
    plain = audit("The tent weighs 2.4kg.", gear(), DEFAULT)
    same = audit("The tent weighs 2.4kg.", gear(), DEFAULT)
    other = audit("The tent weighs 2.6kg.", gear(), DEFAULT)
    assert plain.audited.response_hash == same.audited.response_hash
    assert plain.audited.response_hash != other.audited.response_hash


def test_an_english_package_audits_too() -> None:
    contract = load_package(PACKAGES / "contract-en.json")
    report = audit(
        "Either party may terminate on 30 days written notice, per Section 4(b). "
        "Liability is capped at 45,000 dollars. The cap was raised in 2025.",
        contract,
        DEFAULT,
    )
    grounded = [
        one.particular.text for segment in report.assessment.segments for one in segment.grounded
    ]
    assert "Section 4(b)" in grounded
    assert "45,000 dollars" in grounded
    floating = [
        one.particular.text for segment in report.assessment.segments for one in segment.floating
    ]
    assert "2025" in floating
