"""The documentation rules, where they can be checked by machine.

``docs/README.md`` says the three kinds of document must never be mistaken for
one another, and that an ADR index that has drifted from the directory is a
defect. Both are cheap to assert and expensive to notice by eye, so they are
asserted.
"""

from __future__ import annotations

import ast
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


def test_the_published_schema_is_inside_the_package_tree() -> None:
    """ADR-0002: the contract ships inside the wheel, and #57: by one route.

    It used to reach the wheel through ``force-include`` from a ``schemas/``
    directory at the repository root. That builds a correct wheel and has a
    known hole: **``force-include`` does not apply to an editable install**, so
    the path only existed after a real install and nothing local could look at
    it. `doctor` is the reader that made the move worth making, and now one
    route -- ``importlib.resources`` -- works in a checkout, an editable
    install and a wheel alike.

    **This test replaced one that skipped itself.** The old version began
    ``if not (ROOT / "schemas").glob("*.json"): pytest.skip(...)``, so the
    moment the directory moved it stopped running and reported nothing. A guard
    whose absence-of-subject is spelled as a skip is a guard that disappears
    exactly when the thing it guards changes.
    """
    package = Path(
        tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"][
            "build"
        ]["targets"]["wheel"]["packages"][0]
    )
    published = sorted(path.name for path in (ROOT / package / "schemas").glob("*.json"))
    assert published, (
        f"{package}/schemas holds akashi's published contract. If a schema moved, "
        f"this test is the reader that has to move with it -- do not make it skip."
    )

    from importlib.resources import files

    for name in published:
        shipped = files("akashi") / "schemas" / name
        assert shipped.is_file(), (
            f"{name} is on disk and importlib.resources cannot reach it, which is the "
            f"route docs/audit-report.md sends a consumer down"
        )


def test_no_force_include_smuggles_a_contract_into_the_wheel() -> None:
    """The half that would otherwise rot silently.

    With the schemas inside the package tree, ``force-include`` is not needed
    and its presence would mean two routes to the same file -- one that works
    in an editable install and one that does not, disagreeing only on the
    machine where it matters.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "force-include" not in wheel, (
        "the schemas live inside the package tree now (#57); a force-include beside "
        f"that is a second route that behaves differently in an editable install: "
        f"{wheel.get('force-include')}"
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


def test_the_contract_says_what_a_package_less_reader_may_conclude() -> None:
    """A report travels — signed by somebody else, forwarded, filed, read by a
    party who was not there.

    That reader can confirm strictly less than one holding the package, and
    which half is which is a property of the *document*, not a courtesy of the
    tool that prints it. `akashi explain` says it under any segment carrying an
    outward claim; the contract has to say it too, or the distinction exists
    only for readers who happen to use akashi's own renderer.

    Presence rather than wording. Pinning the prose would make every edit to it
    a test failure, and what must not happen is the section going away or
    stopping naming the fields it is about.
    """
    contract = (ROOT / "docs" / "audit-report.md").read_text(encoding="utf-8")
    assert "What a reader who does not hold the package may conclude" in contract

    outward = contract.split("may conclude", 1)[1].split(chr(10) + "---" + chr(10), 1)[0]
    for field in ("locations", "contradiction", "answer"):
        assert field in outward, f"the section does not say where {field!r} falls"
    assert "an assertion" in outward


def test_explain_and_the_contract_agree_on_which_fields_point_outward() -> None:
    """The two halves meet here and nowhere else.

    `explain` decides to print its footer from `locations` and `contradiction`.
    The contract lists the fields a package-less reader cannot check. If either
    moved without the other, a reader would be told one thing by the document
    and another by the tool, and each half would still pass its own tests.
    """
    import inspect

    from akashi.infrastructure.rendering import explanation

    footer = inspect.getsource(explanation._footer)
    contract = (ROOT / "docs" / "audit-report.md").read_text(encoding="utf-8")
    outward = contract.split("may conclude", 1)[1].split(chr(10) + "---" + chr(10), 1)[0]

    for field in ("locations", "contradiction"):
        assert field in footer, f"explain no longer keys its footer on {field!r}"
        assert field in outward, f"the contract no longer lists {field!r} as an assertion"


def test_no_test_asserts_only_inside_a_loop_over_something_akashi_computed() -> None:
    """The wider class, and the one that gives no hint from the file layout.

    The check below catches a loop over what the *filesystem* handed back. This
    catches a loop over what **akashi** handed back — an audit, an extraction, a
    set of locations. Nothing about the code says the collection could be empty;
    it just is, when a change makes it so, and the test goes green.

    Two were here. `pairwise` over one particular yields no pairs, so the
    overlap invariant passed with extraction returning `()`; and three nested
    loops down to `locations` passed on an answer that grounded nothing. Both
    count their population now and assert it before iterating.

    A loop over an iterable written out in the test is not this: a literal
    cannot become empty by surprise. Excluding those took the scan from one
    false positive in three to none.

    Reported by `mamori`, which found a shared contract skipping four of its five
    subclasses — and the fifth passing against an empty result, which is the
    same defect without even the skip to say something happened.
    """
    called = {
        "audit",
        "evaluate",
        "evaluate_sample",
        "extract_from_answer",
        "extract_from_segment",
        "segment_answer",
        "claims_for",
        "judge_report",
        "locate",
        "find_all",
        "load_cases",
        "read_sample",
        "check_segment",
        "assess",
    }
    offenders: list[str] = []

    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        ]:
            decorators = {
                getattr(one, "id", "") or getattr(getattr(one, "func", None), "id", "")
                for one in function.decorator_list
            }
            if "given" in decorators:
                continue  # hypothesis supplies the population and can never be empty
            names = {
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
            }
            if not names & called:
                continue
            # A name bound to a literal is still a literal. `mamori` needed the
            # same widening for its module constants, and the very next test
            # written here -- a list of fragments assigned to `bearing` -- was
            # flagged by the narrower rule.
            literals = {
                target.id
                for node in [*ast.walk(function), *ast.walk(tree)]
                if isinstance(node, ast.Assign)
                and isinstance(node.value, (ast.Tuple, ast.List, ast.Set, ast.Constant, ast.Dict))
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            loops = [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.For)
                and any(isinstance(inner, ast.Assert) for inner in ast.walk(node))
                and not isinstance(node.iter, (ast.Tuple, ast.List, ast.Set, ast.Constant))
                and not (isinstance(node.iter, ast.Name) and node.iter.id in literals)
            ]
            if not loops:
                continue
            in_a_loop = {id(inner) for loop in loops for inner in ast.walk(loop)}
            asserts_outside = [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Assert) and id(node) not in in_a_loop
            ]
            if not asserts_outside:
                offenders.append(f"{path.name}:{function.lineno} {function.name}")

    assert not offenders, (
        "these tests assert only inside a loop over something akashi computed, so a "
        "change that empties it leaves them green: " + ", ".join(offenders)
    )


def test_no_test_asserts_only_inside_a_loop_over_something_it_discovered() -> None:
    """`for x in []: assert ...` is green, and so is `if not found: skip`.

    Both spell an empty population as a pass, and both go quiet on exactly the
    day the thing they guard moves -- which is not hypothetical here: when
    `schemas/` moved into the package tree (#57), the test guarding its
    packaging began skipping itself and reported nothing.

    The dangerous shape is narrow, so this check is too. A loop over a
    *hypothesis* strategy or a literal is fine; a loop over what the filesystem
    or the import system happened to hand back is not, because that is the
    collection that silently becomes empty. Those must assert their population
    before iterating it.

    Reported by the cross-repository review, which found fourteen of these in
    another project: pointing its source root at a renamed directory left every
    architecture rule passing.
    """
    discovery = {"glob", "rglob", "iterdir", "walk", "walk_packages", "iter_modules", "listdir"}
    offenders: list[str] = []

    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        ]:
            called = {
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", "")
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
            }
            if not called & discovery:
                continue
            in_a_loop = {
                id(inner)
                for loop in ast.walk(function)
                if isinstance(loop, ast.For)
                for inner in ast.walk(loop)
            }
            asserts_outside = [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.Assert) and id(node) not in in_a_loop
            ]
            loops_that_assert = [
                loop
                for loop in ast.walk(function)
                if isinstance(loop, ast.For)
                and any(isinstance(node, ast.Assert) for node in ast.walk(loop))
            ]
            if loops_that_assert and not asserts_outside:
                offenders.append(f"{path.name}:{function.lineno} {function.name}")

    assert not offenders, (
        "these tests assert only inside a loop over a collection they discovered, so "
        "an empty collection passes silently:\n  " + "\n  ".join(offenders)
    )


def test_the_readme_names_every_sibling_it_sits_between() -> None:
    """#48. Counting mentions across the six repositories, the `iriguchi`
    column was **entirely zero**: it referenced `mamori` 36 times and `tsumugi`
    14, and nothing referenced it. The library named "entrance" was the one
    nobody could see, and it is the first thing a prompt touches.

    This is not the cross-repository drift check #48 rules out -- keeping six
    copies of a diagram in step is a human job, and a checker for it would be
    the seventh thing to keep in step. This is one repository's own README, and
    the only thing it asserts is that a name did not fall out of it again.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for sibling in ("kiseki", "musubi", "tsumugi", "iriguchi", "mamori"):
        assert sibling in readme, f"{sibling} is invisible from akashi's README (#48)"


def test_the_readme_does_not_claim_a_consumer_akashi_does_not_have() -> None:
    """The last arrow is a dead end, and the diagram says so. Nothing in the
    other five repositories reads `akashi.audit-report/1-draft` -- measured
    across their `src/` trees, not assumed -- and that is the same fact as the
    contract still saying `-draft`.

    The day somebody does read one, this test is where the diagram gets
    corrected rather than the claim quietly becoming true by accident.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "(no consumer yet)" in readme
    assert "akashi.audit-report/1-draft" in readme


def test_the_readme_latency_claim_is_still_true() -> None:
    """The README quotes two timings. A claim about speed on the front page is
    the easiest thing in a repository to leave behind, and the quadratic
    extraction defect (#c276ef6) is what a slow path actually looks like here.

    Bounds are set well above the measurement on purpose (floors, not targets):
    0.35ms and 56ms measured on the machine this was written on, asserted at
    5ms and 400ms so that a slower CI box is not a red build, but an order of
    magnitude is.
    """
    import time

    from akashi import evaluate

    answer = "The tent weighs 2.4kg and the gas is 9.9kg."
    contexts = ["The tent weighs 2.4kg.", "Gas cartridge, 250mg."]
    evaluate(answer=answer, contexts=contexts)
    start = time.perf_counter()
    for _ in range(50):
        evaluate(answer=answer, contexts=contexts)
    small = (time.perf_counter() - start) / 50 * 1000
    assert small < 5.0, f"the README says 0.35 ms for this; it took {small:.2f} ms"

    long_answer = "。".join(["テントの重量は2.4kgで、参加者は12人です"] * 100) + "。"
    many = ["テントの重量は2.4kgです。"] * 20
    evaluate(answer=long_answer, contexts=many)
    start = time.perf_counter()
    for _ in range(5):
        evaluate(answer=long_answer, contexts=many)
    large = (time.perf_counter() - start) / 5 * 1000
    assert large < 400.0, f"the README says 56 ms for this; it took {large:.0f} ms"
