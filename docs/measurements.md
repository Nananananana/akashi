# Measurements

**Status: current.** Every number here was produced by a command in this
repository, on the date given, and every one states what it does *not* say.

A number in a document is measured or it is not written. Three figures were
named as unmeasured in `AGENTS.md` until this run; they have values now, and the
most important of them is not the flattering one.

**Measured on 2026-08-30.** akashi `0.1.0.dev0`, Python 3.12.8, Windows.
Corpus seed `20260830`, generator `akashi.cases/1`.

```bash
python -m akashi.interfaces.cli.main eval          # everything below
python tools/generate_cases.py --check-only        # the corpus is what the generator makes
```

---

## The headline, and the two ways to read it

| | |
|---|---|
| Extraction recall over **everything marked** | **87 of 96 — 91%** |
| Extraction recall over **the kinds akashi claims** | **87 of 87 — 100%** |

The first is coverage: how much of a realistic answer akashi sees at all. The
second is whether it does what it says. The nine-particular gap is entirely
`proper_noun`, which akashi declares it does not extract
([ADR-0004](adr/0004-the-particular-is-the-unit-of-verification.md)).

Reporting only the second would score akashi against a boundary it drew for
itself. Reporting only the first would count a declared limit as a defect.

---

## Extraction, on nine hand-marked realistic answers

`tests/marked/`, 96 markings. See
[`evaluation-corpus.md`](evaluation-corpus.md) for the marking rule.

| | Found | Marked | |
|---|---:|---:|---:|
| Everything marked | 87 | 96 | 91% |
| The claimed kinds | 87 | 87 | **100%** |
| Spans exact rather than merely overlapping | 87 | 87 | 100% |
| Precision — extractions a marking covers | 87 | 87 | **100%** |

### Per kind

| Kind | | |
|---|---:|---:|
| `quantity` | 35 / 35 | 100% |
| `reference` | 12 / 12 | 100% |
| `date` | 9 / 9 | 100% |
| `number` | 9 / 9 | 100% |
| `duration` | 7 / 7 | 100% |
| `identifier` | 6 / 6 | 100% |
| `percentage` | 6 / 6 | 100% |
| `money` | 3 / 3 | 100% |
| **`proper_noun`** | **0 / 9** | **0%** |

### Per language

| | Everything | Claimed kinds |
|---|---:|---:|
| `en` | 28 / 31 — 90% | 100% |
| `ja` | 30 / 33 — 91% | 100% |
| `zh` | 29 / 32 — 91% | 100% |

No language is much worse than the others, which is the thing an aggregate
would hide and a test now watches for.

### What this does not say

- Nine answers, one model, one sitting, three genres. A sample, not a
  distribution.
- **The person who marked them wrote the extractor.** ADR-0010 warns about
  exactly this for a labelled corpus. The marking rule and the visibility of the
  markings are mitigations, not an answer.
- A unit the extractor does not know makes a *unit swap* undetectable. Two such
  gaps were found by this measurement and closed (`℉`, `percentage points`), and
  the general fact stands: the unit lists are lists, and a list is never
  complete.
- Precision of 100% is over *these* answers. A digit inside a word used to be
  extracted as a number; the fix forbids a letter before a bare number and
  allows one after, so `HbA1c` yields nothing and `350kPa` still yields `350`.
  A number glued to an unknown unit *and* preceded by a letter is still missed.

---

## Coverage: how much of an answer akashi is silent about

| | | |
|---|---:|---:|
| Unbearing segments, **realistic answers** | 28 / 80 | **35%** |
| Unbearing segments, generated corpus | 18 / 135 | 13% |

**35% is the number to use.** The generated corpus was written to carry
particulars, so its 13% is optimistic by construction.

Of the 28, **22 are prose and 6 are table rows** — and the table rows are
`|---|---|` separators, which assert nothing and are counted anyway because a
segment is a segment.

Reading the 22: most are the model hedging or reporting what it *could not*
find — *"Governing law and jurisdiction are left to be agreed separately, so I
cannot tell you what they are from this document alone."* That is a different
thing from a claim akashi cannot check, and it is a better result than the bare
number suggests.

**This settles a falsification condition.**
[proposals/0001 §10](proposals/0001-the-design.md) said: *if most sentences of a
real answer carry no particular, akashi is silent about most of the answer* and
the roadmap changes. A third is not most. **ADR-0004 survives.**

---

## Detection, on the generated corpus

30 train cases, 177 planted spans across 42 cases.

| | | | |
|---|---:|---:|---|
| Fabrication recall | 42 / 42 | 100% | planted hallucinations akashi should catch |
| False positives | 0 / 42 | **0%** | controls flagged anyway |
| Acknowledged false positives | 9 / 9 | 100% | correct values floated, because akashi does no arithmetic |
| Declared misses passed | 42 / 42 | 100% | hallucinations ADR-0004 says akashi cannot see |
| Verdict correctness | 18 / 51 | 35% | the verdict a plant should *ultimately* carry |
| Source localisation | 0 / 33 | 0% | finding the value that was replaced |
| Refusals | 3 / 3 | 100% | protected responses refused rather than audited |
| Reproducibility | 30 / 30 | 100% | the same case audited twice, byte for byte |

Floating particulars attributable to no plant: **0**. Plants the segmenter cut
in two: **0**.

Per language, fabrication recall and false positives are 14/14 and 0/14 in each
of `en`, `ja` and `zh`.

### Reading the two low ones

**Verdict correctness at 35% and source localisation at 0% are correct.**
`contradicted` does not ship until v0.4, so a `digit_drift` that should
ultimately read `contradicted` reads `floating`, and a floating particular
resolves nowhere and therefore carries no location. Both are measured now on
purpose: **a metric introduced at the same time as the feature it scores
measures nothing.** These are the baseline v0.4 has to move.

### What this does not say

- 100% recall on a corpus authored for the method is evidence the method works
  on material designed for it. It is not evidence about production traffic.
- `declared misses passed` at 100% is not a score. It is the count of
  hallucinations akashi is known not to catch, published so a reader can price
  it. Improving it would mean building something ADR-0004 says is not possible
  deterministically.

---

## The segmenter

| | Segments | Fallback share |
|---|---:|---:|
| Realistic answers | 80 | **1.1%** |
| Generated corpus | 177 | 0% |

The fallback is the weaker rule
([ADR-0009](adr/0009-segment-by-script-and-record-the-segmenter.md)): a prose
block with no terminator anywhere in it, cut by line. On realistic answers it
touches about one per cent of the characters — the list items that end without
punctuation.

Structurally the realistic answers cut into **53 prose segments, 15 table rows
and 12 list items**, which is the mix a segmenter has to handle and the
generated corpus does not contain (177 prose, nothing else). That gap is worth
knowing: **the corpus does not exercise the structure pass at all**, and the
marked answers are the only thing that does.

### What this does not say

There is no hand-segmented reference set, so there is no disagreement rate
against one. ADR-0009 owes that number and it is still owed. What is measured
here is how often the *fallback* fires, not how often the sentence rule is
right.

---

## The floors

Set on 2026-08-30 against the run above, in
`src/akashi/evaluation/floors.py`. **Floors, not targets** — each bound is
deliberately below its measurement, and constructing one at or above its
measurement raises.

| Metric | Measured | Bound | |
|---|---:|---:|---|
| Fabrication recall | 100% | ≥ 90% | |
| False positives | 0% | ≤ 5% | tightest bound |
| Verdict correctness | 35% | ≥ 25% | |
| Refusals | 100% | ≥ 100% | **invariant** (ADR-0008) |
| Reproducibility | 100% | ≥ 100% | **invariant** (ADR-0003) |
| Extraction recall, claimed kinds | 100% | ≥ 90% | |
| Extraction precision | 100% | ≥ 90% | |
| Unbearing segments | 35% | ≤ 55% | |

Three metrics are deliberately **ungated**: `declared misses passed`,
`acknowledged false positives` and `source localisation`. Gating a number you
want to move is how a measurement becomes a cage.

---

## What was found by measuring

Five things, all on the first two runs, which is what a first run is for.

1. **`℉` was not in the SI alternation.** `60℉` extracted as a bare `60` and
   grounded against the `60℃` it was swapped from — a unit swap made invisible
   by the unit not being known.
2. **`percentage points` was not an English unit.** `3.5 percentage points`
   grounded against `3.5%`.
3. **The sign was dropped from a signed quantity.** `-20℃` extracted as `20℃`
   and `±0.02mm` as `0.02mm`, so a flipped sign would have grounded against the
   value it was flipped from. This is the one that mattered.
4. **A year-month date read as a month-day date.** `August 2026` came out as
   `August 20` — a *wrong* particular rather than a missing one.
5. **A digit inside a word was extracted.** Every report mentioning `HbA1c`
   carried a stray `1`.

And one thing found by the corpus about the corpus: three plants labelled
`entity_swap` were inventions wearing the wrong label. akashi flagged them
correctly, the runner said *"the label or the limit is wrong"*, and it was the
label.

Fixing (5) then broke `350kPa` in the corpus on the same afternoon, which is
why the rule forbids a letter *before* a bare number and not after.
