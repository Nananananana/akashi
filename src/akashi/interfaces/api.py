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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from akashi.application.audit import audit
from akashi.domain.matching import DEFAULT_MATCHER, Matcher
from akashi.domain.report import AuditReport
from akashi.domain.verdict import Standing
from akashi.infrastructure.languages import DEFAULT, packs
from akashi.infrastructure.packages.plain import package_from_contexts, read_sample

__all__ = ["Result", "evaluate", "evaluate_sample"]


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
