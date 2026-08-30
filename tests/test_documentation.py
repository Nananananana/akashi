"""The documentation rules, where they can be checked by machine.

``docs/README.md`` says the three kinds of document must never be mistaken for
one another, and that an ADR index that has drifted from the directory is a
defect. Both are cheap to assert and expensive to notice by eye, so they are
asserted.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADR = ROOT / "docs" / "adr"

#: Words that must not appear in anything akashi renders for a reader. A
#: particular is ``grounded`` or ``floating``; a segment is ``grounded``,
#: ``floating``, ``contradicted`` or ``unbearing``. This is ADR-0004 made
#: unavoidable rather than a style rule -- a report that says "verified" has
#: claimed something akashi cannot establish.
FORBIDDEN_IN_OUTPUT = ("verified fact", "factually correct", "proven true")


def _adr_files() -> list[Path]:
    found = sorted(p for p in ADR.glob("*.md") if p.name != "README.md")
    assert found, "no ADRs found; this test is measuring nothing"
    return found


def test_every_adr_is_listed_in_the_index() -> None:
    index = (ADR / "README.md").read_text(encoding="utf-8")
    for adr in _adr_files():
        assert adr.name in index, (
            f"{adr.name} exists but the ADR index does not list it. An index that has "
            f"drifted from the directory is how a decision stops being findable."
        )


def test_the_index_lists_no_adr_that_does_not_exist() -> None:
    index = (ADR / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"\((\d{4}-[a-z0-9-]+\.md)\)", index))
    present = {adr.name for adr in _adr_files()}
    assert listed == present, (
        f"the index lists {sorted(listed - present)} which do not exist, and omits "
        f"{sorted(present - listed)}."
    )


def test_adr_numbers_are_unique_and_contiguous() -> None:
    numbers = sorted(int(adr.name[:4]) for adr in _adr_files())
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"ADR numbers are {numbers}; they should run from 1 with no gaps and no "
        f"duplicates. A superseded decision keeps its number and gains a successor."
    )


@pytest.mark.parametrize("adr", _adr_files(), ids=lambda p: p.name)
def test_every_adr_says_what_it_costs(adr: Path) -> None:
    """The section that is usually missing, and the reason these are worth writing."""
    text = adr.read_text(encoding="utf-8")
    assert "## What it costs" in text, (
        f"{adr.name} has no 'What it costs' section. A decision recorded without its "
        f"price is a decision the next reader cannot re-examine."
    )


@pytest.mark.parametrize("adr", _adr_files(), ids=lambda p: p.name)
def test_every_adr_declares_its_status(adr: Path) -> None:
    text = adr.read_text(encoding="utf-8")
    assert re.search(r"^\*\*Status:\*\* (accepted|proposed|superseded)", text, re.MULTILINE), (
        f"{adr.name} does not declare a status on its own second line."
    )


def test_the_design_proposal_says_it_is_a_proposal() -> None:
    """A proposal read as current state is how unbuilt work gets depended on."""
    design = (ROOT / "docs" / "proposals" / "0001-the-design.md").read_text(encoding="utf-8")
    assert "**Status: proposed.**" in design
    assert "Nothing in this document exists yet" in design


def test_there_is_no_architecture_document_yet() -> None:
    """ADR-style rule from ``AGENTS.md``: a current-state document before the code
    is fiction. When ``domain/`` has an architecture, this test is deleted in the
    same commit that describes it."""
    assert not (ROOT / "docs" / "architecture.md").exists(), (
        "docs/architecture.md exists. If there is now an architecture to describe, "
        "delete this test in the commit that describes it."
    )


def test_a_published_schema_is_packaged_with_the_wheel() -> None:
    """ADR-0002: the contract ships inside the wheel.

    The ``force-include`` block in ``pyproject.toml`` is commented out while
    ``schemas/`` is empty, because hatchling refuses to build against a
    force-include that resolves to nothing. This is what stops that comment
    from outliving its reason.

    **This reads the effective configuration rather than the text**, so a block
    that has been commented out is simply absent and the assertion fails. It
    also checks where the files are sent, because a destination of
    ``akashi/schema`` would build a perfectly good wheel that no consumer can
    read.

    What it cannot do is open the artefact. ``force-include`` does not apply to
    an editable install, so the developer's own tree never has the schema at
    that path and a test looking for it would fail for everybody. The one place
    a real install exists is the ``dependency count is zero`` CI job, and the
    check that opens it lives there.
    """
    published = sorted(path.name for path in (ROOT / "schemas").glob("*.json"))
    if not published:
        pytest.skip("no schema published yet; v0.2")

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "force-include" in wheel, (
        "schemas/ now holds a published contract, so the force-include block in "
        "pyproject.toml must be uncommented. A consumer validating a report should not "
        "have to fetch a schema from the internet."
    )

    package = Path(wheel["packages"][0]).name
    assert wheel["force-include"] == {"schemas": f"{package}/schemas"}, (
        f"the schemas must land inside the {package} package directory, or "
        f"importlib.resources cannot find them and the wheel ships a contract "
        f"nobody can open: {wheel['force-include']}"
    )


def test_the_contract_tests_cannot_quietly_stop_running() -> None:
    """``jsonschema`` is what proves a report matches the published contract,
    and every test that uses it begins with ``pytest.importorskip``.

    That is right for a dev-only dependency, and it leaves one hole: if
    ``jsonschema`` were dropped from the ``dev`` extra, or the environment lost
    it, **every conformance test would skip and CI would stay green with no
    schema validated at all.** A suite that silently stops checking the thing it
    exists to check is the same shape as a wheel that silently stops carrying
    the schema.

    The guard is safe because ``pytest`` sits in the same extra: anything that
    can run this file has the extra installed, so an unimportable
    ``jsonschema`` means the extra lost a package rather than that a developer
    chose a lighter install.

    ``importorskip`` itself is not the hole. pytest raises on a module that is
    installed but broken and skips only on one that is absent, so *broken* and
    *missing* stay apart -- checked on pytest 9.1 by importing a module that
    raises, which produced a collection error rather than a skip.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = config["project"]["optional-dependencies"]["dev"]
    assert any(name.startswith("jsonschema") for name in dev)

    try:
        import jsonschema  # noqa: F401
    except ImportError as error:  # pragma: no cover - the failure being guarded
        pytest.fail(
            f"jsonschema is in the dev extra and pytest is running, so it should be "
            f"importable. Every contract-conformance test is skipping and nothing is "
            f"validating a report against its published schema: {error}"
        )


@pytest.mark.parametrize("word", FORBIDDEN_IN_OUTPUT)
def test_the_forbidden_vocabulary_is_absent_from_the_readme(word: str) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert word not in readme, (
        f"README.md contains {word!r}. akashi establishes that a string is where the "
        f"answer implies it is, and nothing stronger. See "
        f"docs/adr/0004-the-particular-is-the-unit-of-verification.md"
    )


def test_every_local_link_in_every_document_resolves() -> None:
    """A link whose text is right and whose target is wrong is worse than no
    link: it sends a reader somewhere with confidence.

    That is the judgement `contradicted` is built on one layer down — akashi
    declines to name a source rather than name the wrong one — and it applies to
    a document that names a file.

    This was found with one broken link in it, in an ADR written the same day:
    the display text said `ADR-0004` and the target dropped three words of the
    filename. Nothing rendered it as an error; the anchor simply went nowhere.

    External links are not followed. Reaching them needs the network, and a
    check that cannot run offline is a check that gets skipped exactly when
    somebody is working without one.
    """
    broken = []
    for document in sorted(ROOT.rglob("*.md")):
        if any(part in {".venv", ".git", "node_modules"} for part in document.parts):
            continue
        for target in re.findall(r"\]\(([^)\s]+)\)", document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = target.partition("#")[0]
            if path and not (document.parent / path).resolve().exists():
                broken.append(f"{document.relative_to(ROOT).as_posix()} -> {target}")
    assert not broken, "documents point at files that are not there:\n  " + "\n  ".join(broken)
