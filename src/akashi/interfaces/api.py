"""One call, for somebody who has an answer and some strings.

The rest of akashi is built for a pipeline: read a package, read a response,
write a report. What a person trying akashi for the first time has is three
values in a notebook, and every library they might compare it against takes
exactly those three:

```python
from akashi import evaluate

result = evaluate(
    answer="The tent weighs 2.4kg and the gas is 9.9kg.",
    contexts=["The tent weighs 2.4kg.", "Gas cartridge, 250mg."],
)
result.grounded_share   # 0.5
result.floating         # ('9.9kg',)
```

**It is a shell, not a shortcut.** Every verdict comes from the same
`audit()` the CLI calls, over a package built by
`infrastructure/packages/plain.py`, and the report it returns is the same
document `--json` writes. Nothing here decides anything, which is what makes
the number this returns the same number the artefact carries.

**It lives beside the CLI and the MCP server, and not in `application`,**
because it does the same job they do: it chooses the language packs and builds
the package. `application` may name only the domain and the ports -- the
architecture test enforces that, and it is what caught the first attempt at
putting this there. akashi has three surfaces now, and this is the third.

**And `grounded_share` is not a faithfulness score.** Every library in this
space reports a 0-1 number by that name, computed by asking a model whether the
context entails each claim. This one is *the share of load-bearing strings in
the answer that occur in the text that was sent* -- a different question with a
different answer, and comparing the two numbers is comparing nothing.
`Result.limits` carries that on the object rather than in a README.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from akashi.application.audit import audit
from akashi.domain.matching import DEFAULT_MATCHER, Matcher
from akashi.domain.report import AuditReport
from akashi.domain.verdict import Standing
from akashi.errors import ContractError, ProtectedResponseError
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages.plain import package_from_contexts, read_sample

__all__ = ["Refused", "Result", "Results", "evaluate", "evaluate_sample", "evaluate_samples"]


@dataclass(frozen=True, slots=True)
class Result:
    """What one answer came to, with the whole report behind it."""

    report: AuditReport

    @property
    def grounded_share(self) -> float | None:
        """Grounded particulars over the checkable ones, or ``None``.

        ``None`` and not ``0.0`` when nothing in the answer could be checked.
        An answer with nothing to check has not scored, and a number there
        would be read as though it had.
        """
        return self.report.assessment.grounded_share

    @property
    def grounded(self) -> tuple[str, ...]:
        """Every particular found in the text that was sent, in order."""
        return tuple(
            one.particular.text
            for segment in self.report.assessment.segments
            for one in segment.particulars
            if one.standing is Standing.GROUNDED
        )

    @property
    def floating(self) -> tuple[str, ...]:
        """Every particular in none of the text that was sent.

        *In none of the text that was sent* -- not *false*, and not *invented*.
        A figure correctly derived from two grounded figures is here, because
        akashi does no arithmetic, and so is anything the answer paraphrased.
        """
        return tuple(
            one.particular.text
            for segment in self.report.assessment.segments
            for one in segment.particulars
            if one.standing is Standing.FLOATING
        )

    @property
    def unchecked(self) -> tuple[str, ...]:
        """Why each skipped segment was skipped, one line each.

        Reading this is the difference between a score and a measurement: a
        share of 1.0 over two particulars in a twelve-sentence answer is not
        the same claim as a share of 1.0 over forty.
        """
        return tuple(
            f"{skip.segment_id}: {skip.rule.value}" for skip in self.report.assessment.skipped
        )

    @property
    def limits(self) -> tuple[str, ...]:
        """What this does not establish, on the object as well as the report."""
        return self.report.assessment.limits

    def to_dict(self) -> dict[str, Any]:
        """The full report as plain data -- the same document ``--json`` writes."""
        return self.report.to_dict()


def evaluate(
    answer: str,
    contexts: Sequence[str],
    *,
    question: str = "",
    languages: Sequence[str] = (),
    matcher: Matcher = DEFAULT_MATCHER,
) -> Result:
    """Audit ``answer`` against ``contexts``, with no package and no files.

    ``languages`` restricts the packs; the default loads all of them, because
    narrowing under-segments (ADR-0011) and a caller who has not measured that
    should not be choosing.
    """
    chosen = packs(*languages) if languages else DEFAULT
    return Result(audit(answer, package_from_contexts(contexts, question), chosen, matcher=matcher))


def evaluate_sample(sample: Mapping[str, Any], **options: Any) -> Result:
    """The same, from a RAGAS, DeepEval or plain sample dictionary.

    Reads ``user_input`` / ``input`` / ``question``, ``response`` /
    ``actual_output`` / ``answer``, and ``retrieved_contexts`` /
    ``retrieval_context`` / ``contexts``. A person with a dataset should be able
    to point akashi at it rather than port it.
    """
    answer, package = read_sample(sample)
    chosen = packs(*options.pop("languages", ())) or DEFAULT
    return Result(audit(answer, package, chosen, **options))


@dataclass(frozen=True, slots=True)
class Refused:
    """A row akashi would not audit, and why.

    Kept rather than raised, because one malformed row in five hundred should
    not lose the other four hundred and ninety-nine -- and kept rather than
    dropped, because a run that quietly audited fewer rows than it was given is
    the failure this project exists to remove. `Results.share` names the count.
    """

    index: int
    reason: str


@dataclass(frozen=True, slots=True)
class Results:
    """What a dataset came to.

    **The aggregate is not a mean of the per-row shares.** A mean would weight a
    one-particular answer the same as a forty-particular one, and would have to
    decide what a row with nothing checkable contributes -- and every available
    answer to that is wrong. `0.0` says the row failed; dropping it says the run
    was over rows it was not over; `1.0` is absurd. So the share here counts
    **particulars, not rows**, and `describe()` says how many rows reached it.
    """

    results: tuple[Result, ...]
    refused: tuple[Refused, ...] = ()

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self) -> Iterator[Result]:
        return iter(self.results)

    def __getitem__(self, index: int) -> Result:
        return self.results[index]

    @property
    def grounded_share(self) -> float | None:
        """Grounded particulars over checkable ones, across every row.

        ``None`` when no row had anything to check, for the same reason a single
        result's is ``None``: nothing was measured, and a number would be read
        as though something had been.
        """
        grounded = sum(len(one.grounded) for one in self.results)
        checkable = grounded + sum(len(one.floating) for one in self.results)
        return grounded / checkable if checkable else None

    @property
    def scored(self) -> int:
        """Rows that had at least one particular to check."""
        return sum(1 for one in self.results if one.grounded_share is not None)

    def describe(self) -> str:
        """The share and everything needed to read it, in one line.

        A bare number over a dataset hides three different things -- rows that
        refused, rows with nothing checkable, and how many particulars the share
        is actually over. All three go here, because the caller who prints this
        is the one who will quote the number.
        """
        share = self.grounded_share
        checkable = sum(len(one.grounded) + len(one.floating) for one in self.results)
        head = "no row had anything to check" if share is None else f"{share:.3f}"
        return (
            f"{head} over {checkable} particulars in {self.scored} of {len(self.results)} rows"
            f"{f'; {len(self.refused)} refused' if self.refused else ''}"
        )

    def rows(self) -> list[dict[str, Any]]:
        """One flat dict per audited row, for a DataFrame or a CSV.

        `pandas.DataFrame(results.rows())` works and akashi does not depend on
        pandas. `limits` travels on every row rather than once beside the table,
        because a column of numbers is exactly the thing that gets copied out of
        its context.
        """
        return [
            {
                "row": index,
                "grounded_share": one.grounded_share,
                "grounded": list(one.grounded),
                "floating": list(one.floating),
                "unchecked": list(one.unchecked),
                "limits": list(one.limits),
                "report_id": one.report.report_id,
            }
            for index, one in enumerate(self.results)
        ]


def evaluate_samples(samples: Iterable[Mapping[str, Any]], **options: Any) -> Results:
    """Audit a dataset of RAGAS, DeepEval or plain samples.

    The loop every caller was writing, with the two decisions they should not
    have to make alone: a row akashi refuses is **kept as a refusal** rather than
    raised or dropped, and the aggregate counts particulars rather than
    averaging rows (`Results`).
    """
    done: list[Result] = []
    refused: list[Refused] = []
    for index, sample in enumerate(samples):
        try:
            done.append(evaluate_sample(sample, **options))
        except (ContractError, ProtectedResponseError) as error:
            refused.append(Refused(index=index, reason=str(error)))
    return Results(tuple(done), tuple(refused))
