# 5. Say what could not be checked, on every report

**Status:** accepted

The sibling of `tsumugi`'s ADR-0005, "selection is a report". The same argument,
applied to an auditor instead of a selector.

## Context

akashi's coverage is partial by construction (ADR-0004), and partial coverage
reported as a single number reads as total coverage. A report that says
`grounded: 94%` and stops has told the reader that 6% of the answer is
questionable. What it has actually established is that 94% of the *extracted
particulars* resolved — which says nothing about the sentences that had no
particulars, nothing about the kinds the extractor does not know, and nothing
about whether the true statement was assembled from two unrelated documents.

The failure mode is specific and it is the one that gets people hurt: a
compliance officer sees a high score, signs off, and the sentence that mattered
was one akashi never looked at.

## Decision

**Every report carries an account of its own blind spots, and the account is
required rather than optional.**

Three things appear on every report:

- **`unchecked[]`** — segments and spans akashi did not check, each with the
  reason. `no_particulars` (the segment asserts something with no load-bearing
  token in it), `kind_not_extracted` (a particular kind the language pack does
  not cover), `outside_the_package` (a segment that refers to a document the
  package did not contain), `derived_value` (a number that appears to be
  computed from grounded ones). Empty only when nothing was skipped.

- **`limits`** — the standing limits of the method, restated on the artefact
  rather than left in the documentation. That cross-document stitching is
  invisible. That a meaning reversal with intact particulars passes. That a
  `grounded` verdict is a statement about strings, not about truth.

- **`coverage`** — the denominator, in plain numbers: how many segments, how
  many carried particulars, how many particulars were extracted, how many were
  checked. A ratio whose denominator is not visible is a ratio a reader will
  assume the wrong denominator for.

The wording is fixed rather than left to the caller, and it never uses `true`,
`false`, `correct` or `verified fact`. A particular is `grounded` or `floating`.
A segment is `grounded`, `floating`, `contradicted` or `unbearing`. These words
are chosen to be uncomfortable to over-read, and a test asserts that the
forbidden vocabulary does not appear in any rendered output.

## Consequences

The human-readable rendering of a report leads with what was not checked, not
with the score. That is a deliberate reversal of what every dashboard in this
category does, and it is the reason the artefact can be handed to a regulator.

A silent cap becomes impossible. If the extractor stops at a length limit, or
the package was truncated, or a language pack was missing, the report says so
under `unchecked[]` with the rule that caused it.

## What it costs

The number akashi prints will be lower and uglier than a competitor's, and it
will be surrounded by caveats. That is a commercial cost and it is accepted: the
buyer for this product is the one who will not sign something whose limits are
not written down.

Every new detector has to declare what it misses before it ships, which is
slower than shipping it. This is invasive to retrofit and so it is done from the
first detector.
