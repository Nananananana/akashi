"""akashi in a test file, where the rest of somebody's checks already live.

Most of why people reach for DeepEval is that its assertions sit beside their
unit tests and fail a build. akashi had `--fail-on-findings` on the command line
and nothing for a `def test_...`, which meant using it in CI was a shell step
that printed JSON somebody had to read.

```python
from akashi.testing import assert_grounded

def test_the_summary_quotes_the_report():
    assert_grounded(answer=summarise(doc), contexts=[doc], at_least=0.9)
```

**The failure message is the finding, not a number.** A bare
``assert 0.72 >= 0.9`` tells you a build went red and nothing about why. What
this raises names every floating particular, what was skipped and why, and the
limits the number was produced under -- the same three things the report leads
with, because they are what a person staring at a red CI job needs.

**`at_least` has no default.** A threshold akashi picked would be a threshold
nobody chose, applied to a number whose meaning depends entirely on the corpus
it was computed over. Passing one is the caller saying what their bar is.

**It imports pytest lazily and works without it.** The failure is an
`AssertionError` either way, so this is usable from a plain script, from
unittest, or from anything that treats an exception as a failure.

This module is deliberately not in `interfaces/`: it is a library surface a
caller imports, the same as `evaluate`, and it composes them rather than
reaching past.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from akashi.interfaces.api import Result, evaluate, evaluate_sample

__all__ = ["GroundingError", "assert_grounded", "assert_sample_grounded"]


class GroundingError(AssertionError):
    """A grounding assertion that did not hold, with the report attached.

    An `AssertionError`, so every runner already treats it as a failure; and
    carrying `result`, so a test that wants to look closer does not have to run
    the audit twice.
    """

    def __init__(self, message: str, result: Result) -> None:
        super().__init__(message)
        self.result = result


def assert_grounded(
    *,
    answer: str,
    contexts: Sequence[str],
    at_least: float,
    allow_floating: Sequence[str] = (),
    **options: Any,
) -> Result:
    """Fail unless ``answer``'s grounded share reaches ``at_least``.

    ``allow_floating`` names particulars that are expected not to occur in the
    evidence -- a figure the answer computes, a date it formats differently --
    and they are removed from the count rather than waived silently. A name in
    that list which did **not** float is itself a failure: it means the test is
    carrying a waiver for something that no longer needs one, and a waiver
    nobody notices going stale is how a suite stops checking.

    Returns the `Result` on success, so a test can go on to assert something
    more specific without auditing twice.
    """
    return _check(evaluate(answer=answer, contexts=contexts, **options), at_least, allow_floating)


def assert_sample_grounded(
    sample: Any,
    *,
    at_least: float,
    allow_floating: Sequence[str] = (),
    **options: Any,
) -> Result:
    """The same, from a RAGAS, DeepEval or plain sample dictionary."""
    return _check(evaluate_sample(sample, **options), at_least, allow_floating)


def _check(result: Result, at_least: float, allow_floating: Sequence[str]) -> Result:
    if not 0.0 <= at_least <= 1.0:
        raise ValueError(f"at_least is a share between 0 and 1, got {at_least}")

    waived = tuple(allow_floating)
    floating = result.floating
    unused = [one for one in waived if one not in floating]
    if unused:
        raise GroundingError(
            f"allow_floating names {', '.join(repr(one) for one in unused)}, which did not "
            f"float. A waiver for something that no longer needs one is a test that has "
            f"stopped checking; remove it, or check the answer still says what you think.",
            result,
        )

    remaining = tuple(one for one in floating if one not in waived)
    grounded = len(result.grounded)
    checkable = grounded + len(remaining)
    if not checkable:
        raise GroundingError(
            "nothing in this answer could be checked against the evidence, so there is no "
            "share to compare with at_least. akashi looked and found no figure, name or "
            f"date to compare.\n\n{_skipped(result)}",
            result,
        )

    share = grounded / checkable
    if share >= at_least:
        return result

    raise GroundingError(
        f"grounded share {share:.3f} is below at_least={at_least:.3f} "
        f"({grounded} of {checkable} checkable particulars).\n\n"
        f"floating -- in none of the text that was sent:\n"
        + "".join(f"  {one}\n" for one in remaining)
        + (f"\nwaived by allow_floating: {', '.join(waived)}\n" if waived else "")
        + f"\n{_skipped(result)}"
        + "\nwhat this number is not:\n"
        + "".join(f"  {line}\n" for line in result.limits),
        result,
    )


def _skipped(result: Result) -> str:
    if not result.unchecked:
        return "nothing in the answer was skipped."
    return "skipped, and why:\n" + "".join(f"  {line}\n" for line in result.unchecked)
