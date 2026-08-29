# 9. Segment by script, and record the segmenter on the report

**Status:** accepted

## Context

Before anything can be attributed, the answer has to be cut into pieces. Every
count in the report has the segmenter in its denominator, so a change to it
changes every number — which makes it exactly the kind of component that must
not drift silently.

The three languages this project serves break differently:

- English ends sentences with `.`, which is also a decimal point, an
  abbreviation marker (`Fig. 2`, `No. 4`), an ellipsis, and a version separator.
- Japanese ends with `。`, which is unambiguous, and then wraps sentences with
  `「」` and `（）` that must not be split inside. Line breaks in a generated
  answer are not sentence boundaries. Full-width and half-width digits both
  occur, often in the same sentence.
- Chinese ends with `。！？` and has no spaces at all, so any rule that leans on
  whitespace produces one segment for a paragraph.

A learned segmenter would handle all of this better. ADR-0001 rules it out, and
this ADR is where that cost is paid explicitly rather than discovered later.

## Decision

**Segmentation is deterministic, rule-based, and selected per script; the rules
are data, and the segmenter identifies itself on every report.**

The rules live in language packs — `en`, `ja`, `zh` — following `mamori`'s
ADR-0008. Script is detected from the text rather than declared by the caller,
because a caller who has to remember to declare it is a caller who will get it
wrong, and because a real answer mixes scripts inside one paragraph.

Every segment keeps its offsets into the original answer, and the invariant is
asserted by a property test:

```text
answer[segment.start:segment.end] == segment.text
```

and, separately, that the segments tile the answer with no gap and no overlap.
An offset that has drifted points a reader at the wrong sentence, which is the
same class of failure ADR-0004 rejects fuzzy matching to avoid.

The report names the segmenter and its version — `akashi.segmenter/ja@1` — so a
`recheck` that produced different counts can attribute the difference to
something.

Structure that is not prose is segmented as itself and marked: a list item, a
table row, a fenced code block. A model answering with a table of figures is the
common case in this product's market, and flattening a table into one sentence
would lose every particular's position.

## Consequences

Segmentation is cheap, inspectable, and testable against fixtures rather than
against a model.

Because the rules are data, a fourth language is a language pack and a fixture
set, not a rewrite.

## What it costs

Abbreviations in English are handled by a list, and a list is never complete.
Every miss splits one sentence into two, which changes the denominator and can
turn one `floating` segment into two.

Japanese without `。` — a bulleted answer, a heading, a fragment — falls back to
line boundaries, and that fallback is recorded on the segment so the report can
say how much of the answer was segmented by a weaker rule.

The measurement this ADR owes is the disagreement rate against a hand-segmented
fixture set, per language, published in `docs/measurements.md`. Until that
number exists, the segmenter is unmeasured and the documentation says so.
