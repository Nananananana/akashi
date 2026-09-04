"""What an audit is allowed to cost, in operations rather than in seconds.

A timing assertion on a shared CI runner is a flaky test that eventually gets
deleted, and deleting it removes the only thing guarding the property. So the
guards here count *calls* -- deterministic, machine-independent, and failing for
exactly the reason a regression would be slow.

Both defects these were written for were the same shape: work that depends on
one thing done inside a loop over another.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from akashi import evaluate
from akashi.domain import particular as particular_module
from akashi.domain import text as text_module

ANSWER = "。".join([f"テントの重量は2.{n % 10}kgで、参加者は{n}人です" for n in range(20)]) + "。"


@contextmanager
def counting(module: Any, name: str) -> Iterator[list[int]]:
    """Count calls to ``module.name`` while the block runs."""
    original = getattr(module, name)
    calls = [0]

    def counted(*args: Any, **kwargs: Any) -> Any:
        calls[0] += 1
        return original(*args, **kwargs)

    setattr(module, name, counted)
    try:
        yield calls
    finally:
        setattr(module, name, original)


def audit_with(contexts: int) -> int:
    """Reductions of *particulars* performed while auditing against ``contexts``."""
    texts = [f"テントの重量は2.{i % 10}kgです。参加者は{i}人でした。" for i in range(contexts)]
    # Patched in `particular`, not in `text`: `Particular.form` binds the name
    # at import, so replacing it in `text` would intercept nothing -- which is
    # what the first version of this file did, and the poison walked through it.
    with counting(particular_module, "search_form") as calls:
        evaluate(answer=ANSWER, contexts=texts)
    return calls[0]


def test_looking_a_particular_up_does_not_refold_it_once_per_document() -> None:
    """`Evidence.locate` read `particular.form` inside its loop over items, and
    that property folds the text every time it is read.

    On 240 particulars against 160 contexts that was 38,400 reductions of 240
    distinct strings -- two thirds of the time an audit spent looking things up,
    and a 3x speed-up when it was hoisted out.

    The number of reductions must grow with the number of *documents*, because
    each one is reduced when it is built. It must not grow with documents times
    particulars.
    """
    few, many = audit_with(4), audit_with(40)
    assert few, "nothing was reduced, so this measures nothing"

    # A particular is reduced a fixed number of times regardless of how many
    # documents it is looked for in. Ten times the documents must not be
    # anywhere near ten times the reductions.
    assert many < few * 2, (
        f"{few} reductions of particulars for 4 documents and {many} for 40. "
        f"Something is folding once per (particular, document) pair again."
    )


def test_the_reductions_are_one_per_document_plus_a_constant() -> None:
    """Stated as a difference rather than a ratio, which is what the shape
    actually is: a fixed cost for the answer, plus one for each document."""
    at_four, at_forty = audit_with(4), audit_with(40)
    per_document = (at_forty - at_four) / 36
    assert per_document < 1, (
        f"{per_document:.1f} reductions of particulars added per extra document; "
        f"a particular's reduced form does not depend on how many documents exist"
    )


def test_a_contradiction_candidate_is_found_by_lookup_and_not_by_scanning() -> None:
    """`SourceIndex.explain` walked every entry three times, once per scope,
    calling `replaces` on each -- and `replaces` refuses every pair whose digits
    differ in its first line.

    Grouping by digits is exact, not an approximation, so this asserts the
    grouping exists and covers what the scan would have reached.
    """
    from akashi.domain.contradiction import SourceIndex, _digits
    from akashi.infrastructure.languages import DEFAULT
    from akashi.infrastructure.packages.plain import package_from_contexts

    package = package_from_contexts(
        [f"テントの重量は2.{i % 10}kgです。参加者は{i}人でした。" for i in range(40)]
    )
    index = SourceIndex.of(package.evidence, DEFAULT)
    assert len(index) > 20, "the index is too small to distinguish a lookup from a scan"

    with_digits = [entry for entry in index.entries if _digits(entry.text)]
    assert with_digits, "no entry carries digits, so the grouping is not exercised"
    assert sum(len(bucket) for bucket in index.by_digits.values()) == len(with_digits)

    for (kind, digits), bucket in index.by_digits.items():
        for entry in bucket:
            assert entry.kind is kind
            assert _digits(entry.text) == digits


def test_the_index_is_built_even_when_a_caller_constructs_one_directly() -> None:
    """Every test in the suite that builds a `SourceIndex` by hand would
    otherwise get an empty grouping and silently contradict nothing."""
    from akashi.domain.anchor import Anchor
    from akashi.domain.contradiction import SourceIndex, SourceParticular
    from akashi.domain.particular import ParticularKind
    from akashi.domain.span import Span

    entry = SourceParticular(
        item_id="itm_01",
        kind=ParticularKind.QUANTITY,
        text="5mg",
        anchor=Anchor(document_id="doc", span=Span(0, 3)),
        sentence=Span(0, 3),
    )
    index = SourceIndex(entries=(entry,))
    assert index.by_digits, "a directly built index has no grouping and would explain nothing"


def test_the_small_case_is_still_the_same_report() -> None:
    """Every change above is a speed change and none of them may be an answer
    change. The suite covers this thoroughly; this is the sentinel that says so
    in the file where the speed work lives."""
    assert text_module.search_form.__module__.startswith("akashi"), "the patch leaked"
    result = evaluate(
        answer="The tent weighs 2.4kg and the gas is 9.9kg.",
        contexts=["The tent weighs 2.4kg.", "Gas cartridge, 250mg."],
    )
    assert result.grounded == ("2.4kg",)
    assert result.floating == ("9.9kg",)
    assert result.grounded_share == 0.5
