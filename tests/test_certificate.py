"""The artefact that leaves the machine.

`akashi audit` prints for somebody at a terminal who can re-run it. A
certificate is attached to a filing, forwarded to a reviewer, and held for as
long as the filing is held — by people who cannot re-run anything and did not
watch it being made. Every test here is about that difference.

The heaviest one is `test_the_answer_survives_verbatim`. A certificate whose
markup altered the text it audited would be a document asserting things about a
string it does not contain, and the alteration would be invisible: nobody
compares a rendered page against a JSON file character by character.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from akashi.application import audit
from akashi.errors import ContractError
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import certificate

PACKAGES = Path(__file__).parent / "packages"
CONTRACTS = Path(__file__).parent / "contracts"

ANSWER = "テントは 2.4kg、ガスは 250mg カートリッジ。"


def report(answer: str = ANSWER, package: str = "gear-ja.json") -> dict[str, Any]:
    """A report as a plain dictionary, which is all a certificate may read."""
    return audit(answer, load_package(PACKAGES / package), DEFAULT).to_dict()


def archived(body: dict[str, Any]) -> dict[str, Any]:
    """Through JSON, the way a certificate is actually reached: somebody wrote
    a report to a file weeks ago and is rendering it now."""
    restored: dict[str, Any] = json.loads(json.dumps(body, ensure_ascii=False))
    return restored


class Stripper(HTMLParser):
    """Text with every tag removed, and a note of what tags were seen."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        self.tags.append(tag)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def strip(html: str) -> Stripper:
    parser = Stripper()
    parser.feed(html)
    parser.close()
    return parser


def _is_a_page(html: str) -> bool:
    """Whether there is a certificate here at all.

    Every assertion about what a certificate does *not* contain is true of a
    page that contains nothing, so each of them says this first. Found by
    poisoning `certificate()` to return an empty string and watching two tests
    stay green.
    """
    return (
        html.startswith("<!DOCTYPE html>")
        and "<h2>Traced</h2>" in html
        and ANSWER in html
        and len(html) > 2000
    )


# --- what a signer is holding ------------------------------------------------


def test_the_answer_survives_verbatim() -> None:
    """The text between the marks is the audited answer, exactly.

    Every span on the page indexes this string. If the markup dropped a
    character, inserted one, or re-ordered anything, the offsets a signer is
    asked to trust would point somewhere else — and the page would still look
    right, because nobody diffs a rendering against its JSON.
    """
    body = archived(report())
    html = certificate(body)
    block = re.search(r'<div class="answer">(.*?)</div>', html, re.S)
    assert block is not None
    # The marks are their own elements, so removing those leaves the answer and
    # nothing else. Written as a removal rather than a comparison of the marked
    # text, because `+` and `!` are legal characters in an answer and a test
    # that tolerated them here would tolerate them anywhere.
    without_marks = re.sub(r'<span class="mk [a-z]+">.</span>', "", block.group(1))
    assert "".join(strip(without_marks).text) == body["answer"]


def test_a_particular_is_marked_where_it_stands() -> None:
    """Not merely listed in a table below. The reason the certificate is HTML
    rather than the text report printed: a reader sees which words in the
    sentence were checked, and how much of it carries no mark."""
    html = certificate(archived(report()))
    assert '<mark class="grounded">2.4kg</mark>' in html
    assert '<mark class="floating">250mg</mark>' in html
    assert "テントは " in html


def test_standing_is_not_carried_by_colour_alone() -> None:
    """Printed in monochrome, and read by somebody who does not separate the
    hues. The underline shape and a mark before the text carry the distinction;
    colour is on top of it."""
    html = certificate(archived(report()))
    assert '<span class="mk grounded">+</span>' in html
    assert '<span class="mk floating">!</span>' in html
    assert "border-bottom: 2px solid" in html
    assert "border-bottom: 2px dotted" in html


def test_what_was_not_checked_comes_before_the_score() -> None:
    """ADR-0005, and on a certificate it is not a stylistic preference: the
    signer is the person for whom a missed exclusion is expensive."""
    html = certificate(archived(report()))
    assert html.index("Not checked") < html.index("Coverage")
    assert html.index("Not checked") < html.index("Grounded")


def test_traced_is_on_the_page_and_above_the_coverage_numbers() -> None:
    """The `Traced` section is what a signer signs — the claim *this figure
    came from your document, at this offset*. The findings matter to whoever
    fixes the answer; this is what the artefact is for."""
    html = certificate(archived(report()))
    assert "<h2>Traced</h2>" in html
    assert html.index("<h2>Traced</h2>") < html.index("<h2>Coverage</h2>")
    assert "notes/2025-06-03-装備メモ.md" in html
    assert "[1209:1214]" in html


# --- #53: what the holder of this file can check -----------------------------


def test_it_says_which_offsets_the_holder_cannot_check() -> None:
    """#53. The certificate is the artefact *designed to circulate without the
    package*, so the split between an offset into the answer — printed above —
    and an offset into a document the holder does not have is the one thing
    this page must not let a signer assume away."""
    html = certificate(archived(report()))
    assert "What this page lets you check" in html
    assert "Offsets into the answer point at text printed above" in html
    assert "Offsets into a source document you cannot" in html


def test_a_report_with_no_outward_offsets_does_not_warn_about_them() -> None:
    """A caveat that appears whether or not it applies is a caveat readers
    learn to skip, and this one has to survive being read."""
    body = archived(report("犬が寝ている。"))
    assert not any(
        one.get("locations")
        for segment in body["segments"]
        for one in segment.get("particulars", [])
    )
    html = certificate(body)
    assert "Offsets into a source document you cannot" not in html
    assert "It did not decide whether the answer is true" in html


def test_it_does_not_claim_the_answer_is_true() -> None:
    html = certificate(archived(report()))
    assert "did not decide whether the answer is true" in html


# --- what must not be in a document that outlives its machine ----------------


def test_there_is_no_script_anywhere() -> None:
    """An empty page has no script in it either.

    This and the one below were written as absence alone, and both passed with
    `certificate()` returning `""`. Absence is only a claim about a page that
    exists, so the page is checked first.
    """
    html = certificate(archived(report()))
    assert _is_a_page(html)
    assert "<script" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "onload" not in html.lower()
    assert "onerror" not in html.lower()


def test_nothing_is_fetched_when_the_page_is_opened() -> None:
    """One file. A certificate that reached a CDN would tell that CDN who was
    reading a compliance artefact and when, and would render differently once
    the CDN was gone. For a document meant to outlive the machine that made it,
    both are disqualifying."""
    html = certificate(archived(report()))
    assert _is_a_page(html)
    assert not re.search(r"https?://", html)
    assert "@import" not in html
    assert "@font-face" not in html
    assert not re.search(r"<link\b", html, re.I)
    assert not re.search(r"<img\b", html, re.I)
    assert not re.search(r"\burl\s*\(", html, re.I)


def test_the_same_report_renders_to_the_same_bytes() -> None:
    """A signature is over bytes. A certificate carrying a timestamp, a host
    name or an ordering that depends on insertion would mean a signature over
    one copy did not verify the other — and the difference would sit in a field
    nobody looks at."""
    body = archived(report())
    assert certificate(body).encode("utf-8") == certificate(archived(report())).encode("utf-8")


def test_it_reads_the_report_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    """The claim `docs/audit-report.md` makes about a report being a document,
    exercised where it would break. Rendering must not reach for the package,
    the response file or the corpus.
    """
    body = archived(report())

    def refuse(*args: object, **kwargs: object) -> object:
        raise AssertionError("the certificate opened a file")

    monkeypatch.setattr(Path, "open", refuse)
    monkeypatch.setattr("builtins.open", refuse)
    assert "<h2>Traced</h2>" in certificate(body)


# --- untrusted text ----------------------------------------------------------


def test_an_answer_containing_markup_is_escaped_not_rendered() -> None:
    """The answer came from a language model, which was reading the owner's
    documents. Neither is a source this renderer may trust with markup."""
    body = archived(report("<script>alert(1)</script> は 2.4kg です。"))
    html = certificate(body)
    assert "<script" not in html.lower()
    assert "&lt;script&gt;" in html


def test_a_source_path_containing_markup_is_escaped() -> None:
    """Every string on the page comes from somewhere akashi does not control:
    the answer, the item text, and the document paths the package named."""
    body = archived(report())
    for segment in body["segments"]:
        for one in segment.get("particulars", []):
            for location in one.get("locations", []):
                location["source_path"] = '"><script>alert(1)</script>'
    html = certificate(body)
    assert "<script" not in html.lower()
    assert "&lt;script&gt;" in html


def test_the_document_parses(subtests: object = None) -> None:
    """Well-formed enough that a browser and a converter agree on it. A
    certificate that renders in Chrome and not in whatever produces the PDF for
    the filing is a certificate that fails on the day it is needed."""
    html = certificate(archived(report("<b>2.4kg</b> と 250mg。")))
    parser = strip(html)
    assert parser.tags[:2] == ["html", "head"]
    assert "body" in parser.tags


# --- reading a report this akashi did not write ------------------------------


def test_a_report_from_a_newer_akashi_still_renders() -> None:
    """A document may outlive the reader. An unknown verdict is not a finding
    here and is not an error either — refusing to render an archived
    certificate because a field grew would defeat the point of the format."""
    body = archived(report())
    body["segments"][0]["verdict"] = "something_akashi_0_9_says"
    html = certificate(body)
    assert "<h2>Findings</h2>" in html


def test_something_that_is_not_a_report_is_refused_by_name() -> None:
    with pytest.raises(ContractError, match="no 'segments'"):
        certificate({"contract": "akashi.audit-report/1-draft"})


def test_a_report_whose_answer_is_missing_is_refused_rather_than_half_rendered() -> None:
    body = archived(report())
    body["answer"] = None
    with pytest.raises(ContractError, match="not text"):
        certificate(body)


def test_a_span_outside_the_answer_is_dropped_rather_than_slicing_wrongly() -> None:
    """A report akashi did not produce, or one edited by hand. Marking at a
    bad offset would move every following mark; dropping one is visible as an
    unmarked figure, and a wrong one is not."""
    body = archived(report())
    body["segments"][0]["particulars"][0]["span"] = [900, 950]
    html = certificate(body)
    block = re.search(r'<div class="answer">(.*?)</div>', html, re.S)
    assert block is not None
    without_marks = re.sub(r'<span class="mk [a-z]+">.</span>', "", block.group(1))
    assert "".join(strip(without_marks).text) == body["answer"]


def test_overlapping_particulars_do_not_nest_marks() -> None:
    """Two underlines of an unclear extent say something neither akashi nor the
    reader can pin down."""
    body = archived(report())
    first = body["segments"][0]["particulars"][0]
    body["segments"][0]["particulars"].append(
        {**first, "span": [first["span"][0] + 1, first["span"][1] + 3]}
    )
    html = certificate(body)
    assert "<mark" in html
    assert '<mark class="grounded"><mark' not in html
    block = re.search(r'<div class="answer">(.*?)</div>', html, re.S)
    assert block is not None
    without_marks = re.sub(r'<span class="mk [a-z]+">.</span>', "", block.group(1))
    assert "".join(strip(without_marks).text) == body["answer"]


# --- the facts that must not be lost in translation --------------------------


def test_an_asserted_restoration_is_worded_as_an_assertion() -> None:
    """ADR-0013. A restoration akashi watched and one it was told about are
    different claims, and a certificate is the single artefact where losing
    that difference matters most."""
    from akashi.domain.evidence import Evidence, item
    from akashi.domain.package import ContextPackage, Protection

    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "担当は田中太郎。")]),
        protection=Protection(by="mamori@0.27.0", scope="s", reversible=True),
        declares_protection=True,
    )
    body = archived(
        audit("担当は田中太郎です。", package, DEFAULT, restored_by="mamori@0.27.0").to_dict()
    )
    html = certificate(body)
    assert "asserted mamori@0.27.0" in html
    assert "akashi did not verify it" in html


def test_a_non_conforming_package_is_named_on_the_certificate() -> None:
    """ADR-0016. The fact travels with the artefact or it does not travel."""
    from akashi.infrastructure.packages.contextpackage import read_package

    raw = json.loads((PACKAGES / "gear-ja.json").read_text(encoding="utf-8"))
    raw["invented"] = "whatever"
    body = archived(audit(ANSWER, read_package(raw), DEFAULT).to_dict())
    html = certificate(body)
    assert "does not conform" in html
    assert "invented" in html


def test_the_withheld_note_does_not_read_as_explaining_a_finding() -> None:
    """ADR-0012, in a rendering where a signer is looking for a reason."""
    html = certificate(archived(report()))
    if "withheld" in html:
        assert "does not explain any finding" in html
