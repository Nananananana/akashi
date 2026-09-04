"""Where a limit changed the answer, said out loud.

akashi has four bounds, and every one of them is correct. `MAX_RUN` is what
stopped a hostile answer from taking 38 seconds; `MAX_DEPTH` is what stopped a
nested document from ending an MCP session; `_LIMIT` and `MAX_CLAIMS` keep one
audit from producing an unbounded report or an unbounded bill.

**What was wrong is that three of them were silent.** Measured on today's code
before this module existed:

| bound | what happened | what the report said |
| --- | --- | --- |
| ``_LIMIT`` | 40 occurrences reported as 32 | nothing |
| ``MAX_CLAIMS`` | 200 floating claims, 64 judged | nothing |
| ``MAX_RUN`` | a 300-digit number **vanished** | nothing |

The third is the one that matters. A sentence plainly containing a number came
back `share=None` -- *akashi looked and there was nothing to check* -- which is
not a weaker answer than the truth, it is a different one. Nothing raised.
Nothing was slow. The report was wrong and looked fine.

A bound is a decision akashi made on the caller's behalf, so it is a fact about
the audit, and ADR-0012 already settles what happens to those: **an omission is
a receipt.** Every bound that actually bit produces a line on the artefact,
naming itself, its value, and what it left out.

Bounds are **not** settings (`infrastructure/settings.py` says why). A caller
who could raise `MAX_RUN` could restore the quadratic blow-up it exists to
prevent, on input akashi is specifically built to receive from strangers. What
a caller gets instead is the truth about what the bound did.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "Bound",
    "from_oversized",
    "from_truncated_locations",
    "from_unsent_claims",
    "oversized_runs",
]


@dataclass(frozen=True, slots=True)
class Bound:
    """One limit, and the fact that it bit.

    Only constructed when a bound was actually reached. A report listing every
    bound akashi has would be a report where the one that mattered is buried
    among three that did not, which is the same silence in a longer form.
    """

    #: The constant, by the name it has in the source, so a reader can go and
    #: find the reasoning rather than guess at it.
    name: str
    #: Its value at the time of this audit. Recorded rather than looked up,
    #: because a report is read after the version that produced it moved on.
    limit: int
    #: What it left out, in a whole sentence. This is what a reader acts on,
    #: and a bare count would put the work of interpreting it on them.
    because: str

    def __post_init__(self) -> None:
        if not self.name or not self.because:
            raise ValueError(
                "a bound that does not say what it left out is the silence this "
                "module exists to remove"
            )

    def as_line(self) -> str:
        return f"{self.name}={self.limit}: {self.because}"


#: A run of digits long enough that no extraction rule can match it.
#:
#: Rules are rewritten so every repeat is bounded (`extraction._bounded`), which
#: means a number longer than the bound is not *partly* seen -- it is not seen at
#: all. Finding those needs its own scan, because the thing being detected is
#: precisely the thing the rules cannot express.
#:
#: A run must end on a digit. Without that the full stop closing a sentence
#: counted as part of the number, so a run of exactly `MAX_RUN` digits measured
#: as one over and produced a receipt for a figure akashi had in fact read --
#: found by the test asserting the receipt does *not* fire at the bound.
_DIGITS = re.compile(r"[0-9０-９](?:[0-9０-９.,．，]*[0-9０-９])?")


def oversized_runs(text: str, limit: int) -> tuple[int, ...]:
    """The length of every digit run in ``text`` too long for the rules to see.

    Returned rather than reported here so the caller decides what it means: in
    an answer it is a particular akashi missed, and in evidence it is a place a
    particular could not have been found. They are different sentences.
    """
    return tuple(
        len(found.group()) for found in _DIGITS.finditer(text) if len(found.group()) > limit
    )


def from_oversized(runs: Sequence[int], limit: int) -> tuple[Bound, ...]:
    """A receipt for digit runs the rules could not reach, or nothing.

    Plural is kept plural. "A number was too long" and "nine numbers were too
    long" are different situations for a reader deciding whether to care.
    """
    if not runs:
        return ()
    longest = max(runs)
    counted = (
        f"{len(runs)} runs of digits were" if len(runs) > 1 else f"a run of {longest} digits was"
    )
    return (
        Bound(
            name="MAX_RUN",
            limit=limit,
            because=(
                f"{counted} longer than the {limit} digits an extraction rule can match "
                f"(longest: {longest}), so no particular was taken from "
                f"{'them' if len(runs) > 1 else 'it'}. This is not a finding about the "
                f"answer -- akashi did not look, and a share computed without "
                f"{'those figures' if len(runs) > 1 else 'that figure'} is over less than "
                f"the answer contains."
            ),
        ),
    )


def from_truncated_locations(count: int, limit: int) -> tuple[Bound, ...]:
    """A receipt for particulars whose occurrence list stopped at the cap.

    The count of *particulars* affected, not of occurrences dropped, because
    akashi stopped counting and therefore does not know how many there were.
    Reporting a number it did not measure is the failure in the other
    direction.
    """
    if not count:
        return ()
    subject = "one particular occurs" if count == 1 else f"{count} particulars occur"
    return (
        Bound(
            name="LOCATION_LIMIT",
            limit=limit,
            because=(
                f"{subject} at least {limit} times in one document, and akashi stopped "
                f"listing places at {limit}. The occurrence counts on "
                f"{'that particular' if count == 1 else 'those particulars'} are floors, "
                f"not totals -- akashi stopped counting and does not know the total."
            ),
        ),
    )


def from_unsent_claims(sent: int, total: int, limit: int) -> tuple[Bound, ...]:
    """A receipt for claims a judge was never shown.

    The defect this closes: 200 floating particulars produced 64 claims, the
    judge answered 64, and the report carried 64 judgements with nothing saying
    the other 136 existed. A reader counts the judgements and believes the judge
    looked at the answer.
    """
    if sent >= total:
        return ()
    return (
        Bound(
            name="MAX_CLAIMS",
            limit=limit,
            because=(
                f"{total} claims could have been sent to a judge and {sent} were. The "
                f"remaining {total - sent} were not judged by anything, and are absent "
                f"from 'judged' for that reason rather than because a judge had nothing "
                f"to say about them."
            ),
        ),
    )
