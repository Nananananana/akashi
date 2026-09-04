"""akashi against a package `tsumugi` really produced.

Every other test in this repository reads a package somebody here typed. That
proves akashi is self-consistent and nothing more: ADR-0007 has akashi reading
somebody else's contract without importing them, and the standing cost of that
is that the two implementations can drift while both stay green.

`tests/contracts/context-package-seam.json` is the output of `tsumugi context
--json` over a fixed corpus and a fixed question, vendored beside the schema it
instantiates. The schema says what the shape *may* be; this says what the
producer *does*. A consumer needs both, and only one of them was here before.

**It is deliberately not the happy path.** The producer's own fixture notes say
so, and the three things it goes out of its way to include are the three a
consumer gets wrong:

- **an omission.** The budget binds at 40 characters, so one ranked passage was
  left out. `omissions[]` is the half of this contract most likely to be
  ignored, and a fixture that never carries one never tests it.
- **a superseded passage carried rather than dropped.** `gear-older.md` says
  3.1kg where `gear.md` says 2.4kg, and *both are sent*. A consumer assuming one
  package answers one question finds out here.
- **`protection: null`,** which is a package saying it was not redacted — not a
  package that said nothing. ADR-0008 turns on exactly that difference.

This is also the first place akashi consumes a document it did not write and
produces one of its own from it, which is the condition
`proposals/0002` sets for freezing `akashi.audit-report/1`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from akashi.application import audit
from akashi.domain.package import ContextPackage
from akashi.domain.verdict import Verdict
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from akashi.interfaces.cli.main import AUDITED, main
from conftest import published_schema

CONTRACTS = Path(__file__).parent / "contracts"
FIXTURE = CONTRACTS / "context-package-seam.json"
SCHEMA = CONTRACTS / "context-package-1.json"
REPORT_SCHEMA = published_schema()

#: Quotes one document, quotes the one it supersedes, and invents a third
#: figure that happens to live in the passage the budget left out.
ANSWER = "テントの重量は2.4kgです。6月のメモでは3.1kgとあります。タープは1.9kgです。"


@pytest.fixture(scope="module")
def package() -> ContextPackage:
    return load_package(FIXTURE)


# --- The document itself -----------------------------------------------------


def test_the_fixture_is_an_instance_of_the_schema_vendored_beside_it() -> None:
    """The two are vendored as a pair and are checked as one.

    A fixture that no longer validates means the producer changed its output or
    its schema and akashi is testing against a document that no longer exists.
    """
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(
        json.loads(FIXTURE.read_text(encoding="utf-8")),
        json.loads(SCHEMA.read_text(encoding="utf-8")),
    )


def test_akashi_reads_the_real_thing_without_refusing(package: ContextPackage) -> None:
    """The check ADR-0007 exists to pay for. akashi's reader is a second
    implementation of this contract; this is the only test that puts it in front
    of the first implementation's actual output."""
    assert package.contract == "tsumugi.context-package/1"
    assert package.package_id.startswith("sha256:")
    assert len(package.evidence.items) == 2
    assert len(package.evidence.withheld) == 1


def test_the_offsets_in_the_fixture_are_the_offsets_akashi_uses(package: ContextPackage) -> None:
    """Anchors are document coordinates, and a reader opens the file. An
    off-by-one here would point every citation at the wrong line, and no schema
    can catch it because the document is well-formed either way."""
    first = package.evidence.items[0]
    assert first.anchor.source_path == "gear.md"
    assert first.anchor.span.start == 8
    assert first.text == "テントの重量は2.4kg、二人用。"


# --- The three things the fixture was widened to cover ------------------------


def test_a_package_can_carry_two_answers_and_akashi_grounds_both() -> None:
    """`gear.md` says 2.4kg and `gear-older.md` says 3.1kg, and tsumugi sends
    both: its ADR-0008 marks redundancy rather than removing it.

    akashi grounds each in its own document. It does *not* say which is current
    — that is a judgement about the world, and a grounded particular is a
    statement about strings (STANDING_LIMITS).
    """
    report = audit(ANSWER, load_package(FIXTURE), DEFAULT)
    grounded = {
        one.particular.text: one.locations[0].anchor.source_path
        for segment in report.assessment.segments
        for one in segment.particulars
        if one.locations
    }
    assert grounded["2.4kg"] == "gear.md"
    assert grounded["3.1kg"] == "gear-older.md"


def test_a_figure_from_the_passage_the_budget_left_out_floats() -> None:
    """The tarp's weight is in the corpus and *not in the package*, because the
    budget bound at 40 characters. akashi audits against what was sent
    (ADR-0006), so it floats.

    The report says the package withheld something, and stops there. akashi
    cannot say this particular matched the omission: an omission carries an
    anchor and a reason and not the text, so there is nothing to match against
    (ADR-0012). Naming the two facts side by side is the whole of what akashi
    can honestly do here.
    """
    report = audit(ANSWER, load_package(FIXTURE), DEFAULT)
    floating = {
        one.particular.text
        for segment in report.assessment.segments
        for one in segment.particulars
        if not one.locations
    }
    assert "1.9kg" in floating
    assert report.provenance.withheld == (("budget_exhausted", 1),)


def test_a_package_that_says_it_was_not_redacted_is_audited(package: ContextPackage) -> None:
    """`protection: null` and `declares_protection` true. A package that said
    nothing at all would be refused under ADR-0008; this one told akashi, and
    what it told akashi was that there is nothing to restore."""
    assert package.protection is None
    assert package.declares_protection
    assert audit(ANSWER, package, DEFAULT).assessment.segments


# --- End to end ---------------------------------------------------------------


def test_the_report_names_the_package_it_audited_against(package: ContextPackage) -> None:
    """A report that cannot name its inputs is a report nobody can re-derive.
    The id here was computed by the producer, not by akashi."""
    report = audit(ANSWER, package, DEFAULT)
    assert report.audited.package_id == package.package_id
    assert report.audited.package_id == (
        "sha256:98cefec2db8a9ef55e72b0c1d065d1da22e917793885774647ddfc9d4d659c57"
    )


def test_the_same_producer_document_audits_the_same_way_twice(package: ContextPackage) -> None:
    """ADR-0003 across the seam rather than within it."""
    first = audit(ANSWER, package, DEFAULT)
    second = audit(ANSWER, load_package(FIXTURE), DEFAULT)
    assert first.report_id == second.report_id
    assert first.to_dict() == second.to_dict()


def test_the_report_produced_from_it_validates_against_akashis_own_contract(
    package: ContextPackage,
) -> None:
    """Consume one published contract, produce another. This is the pair
    `proposals/0002` names as the condition for freezing
    `akashi.audit-report/1`."""
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(
        audit(ANSWER, package, DEFAULT).to_dict(),
        json.loads(REPORT_SCHEMA.read_text(encoding="utf-8")),
    )


def test_the_seam_works_through_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Through the installed entry point, not the Python API. A seam that only
    works when called from inside its own test suite is not a seam."""
    answer = tmp_path / "answer.txt"
    answer.write_text(ANSWER, encoding="utf-8")
    code = main(["audit", "--package", str(FIXTURE), "--response", str(answer), "--json"])
    assert code == AUDITED
    body = json.loads(capsys.readouterr().out)
    assert body["audited"]["package_id"] == (
        "sha256:98cefec2db8a9ef55e72b0c1d065d1da22e917793885774647ddfc9d4d659c57"
    )
    assert any(segment["verdict"] == Verdict.FLOATING.value for segment in body["segments"])


# --- The contract closed, and akashi had been reading past the fact ----------


def test_the_real_package_carries_nothing_the_contract_does_not_list() -> None:
    """The baseline. Everything below is the same package with one field added,
    and it means nothing unless this one is empty."""
    assert load_package(FIXTURE).unrecognised == ()


@pytest.mark.parametrize(
    ("where", "expected"),
    [
        ("root", "invented"),
        ("item", "items[0].invented"),
        ("provenance", "provenance.invented"),
    ],
)
def test_a_field_the_contract_does_not_list_reaches_the_reader(where: str, expected: str) -> None:
    """Read past, and said out loud.

    `tsumugi.context-package/1` is closed: every object sets
    ``additionalProperties: false``, so this package does not conform to the
    contract it names. akashi can still audit it and does -- unknown is not
    wrong -- but a reader who is told nothing cannot tell which document the
    audit was performed on.

    Asserted on the **rendered text**, not on the dataclass. The field was
    populated and printed nowhere for the length of one edit, and every test
    passed: recording a fact and telling somebody are two changes, and only one
    of them was under test.
    """
    from akashi.infrastructure.packages.contextpackage import read_package
    from akashi.infrastructure.rendering import as_text

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    target = {"root": raw, "item": raw["items"][0], "provenance": raw["provenance"]}[where]
    target["invented"] = "whatever"

    package = read_package(raw)
    assert package.unrecognised == (expected,)

    printed = as_text(audit(ANSWER, package, DEFAULT))
    assert expected in printed
    assert "does not conform" in printed


def test_it_is_not_worded_as_though_it_explained_a_finding() -> None:
    """ADR-0012, in the same position as ``withheld``. A non-conforming package
    is a fact about the document; it is not a reason any particular floated,
    and a report that let the two blur would be offering an excuse."""
    from akashi.infrastructure.packages.contextpackage import read_package
    from akashi.infrastructure.rendering import as_text

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["invented"] = "whatever"
    printed = as_text(audit(ANSWER, read_package(raw), DEFAULT))

    provenance = printed.split("Provenance")[1]
    assert "invented" in provenance, "the fact belongs beside the document, not beside a finding"
    assert "invented" not in printed.split("Provenance")[0]


def test_the_report_carries_it_as_data_too() -> None:
    """A report is a document (ADR-0002). A fact only in the text rendering is
    a fact the next consumer of the JSON does not have."""
    from akashi.infrastructure.packages.contextpackage import read_package

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["invented"] = "whatever"
    body = audit(ANSWER, read_package(raw), DEFAULT).to_dict()
    assert body["provenance"]["unrecognised"] == ["invented"]


def test_an_unknown_selection_signal_does_not_stop_the_audit() -> None:
    """What the 2026-09-04 refresh actually changed, pinned so the next one is
    a comparison rather than a fresh investigation.

    tsumugi began emitting ``confirmed_share:0.88`` in ``items[].selection
    .signals``. That is a new **value** inside a field the contract already
    names, not a new field, so `_unrecognised` does not report it -- it walks
    field names and says so in its own docstring, and going deeper would need
    akashi to hold a second copy of the whole schema.

    akashi reads neither, and that is the point: the audit is over
    ``items[].text`` and the anchors. A producer's account of *why it retrieved*
    an item is not evidence about the answer, and akashi relaying somebody
    else's confidence beside its own offsets is how a reader comes to think the
    0.88 was checked by something here.

    So the seam survived a producer change without a code change. The record of
    which change that was is the thing worth keeping.
    """
    package = load_package(FIXTURE)
    signals = [
        signal
        for item in json.loads(FIXTURE.read_text(encoding="utf-8"))["items"]
        for signal in item.get("selection", {}).get("signals", ())
    ]
    assert any(signal.startswith("confirmed_share:") for signal in signals), (
        "upstream no longer carries the signal this test is about"
    )
    assert package.unrecognised == ()

    report = audit("テントの重量は2.4kg。", package, DEFAULT)
    assert report.assessment.segments
    assert report.provenance.unrecognised == ()
