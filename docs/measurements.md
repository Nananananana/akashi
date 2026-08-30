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

| | v0.3 | v0.4 |
|---|---|---|
| Extraction recall over **everything marked** | 87 of 96 — 91% | **91 of 96 — 95%** |
| Extraction recall over **the kinds akashi claims** | 87 of 87 — 100% | 91 of 96 — 95% |
| Extraction precision | 100% | **100%** |
| Unbearing segments | 35% | **30%** |
| Verdict correctness | 18 of 51 — 35% | **30 of 51 — 59%** |
| Source localisation | 0 of 33 — 0% | **12 of 33 — 36%** |
| Source misdirection | not measurable | **0 of 12 — 0%** |

The two recalls were far apart in v0.3 because `proper_noun` was a kind akashi
attempted nothing for. **The structural name rules in v0.4 closed that**, so the
two are now the same number and the five remaining misses are names with no
title, honorific or legal form beside them.

They are still reported separately. A kind added later that nothing extracts
would pull them apart again, and a reader who has watched them move together
learns more than one handed a single figure.

**akashi reads structure, not names**, and that is now a standing limit on every
report rather than an entry in `kinds_not_extracted`.

The other three moved because `contradicted` shipped, and **36% is a ceiling
akashi chose rather than a wall it hit**. Naming the source for a value whose
digits drifted would take localisation to 27 of 33 and is wrong more often than
right; the trade that bought 0% misdirection is measured further down and
decided in [ADR-0015](adr/0015-the-digits-are-the-evidence.md).

---

## Extraction, on nine hand-marked realistic answers

`tests/marked/`, 96 markings. See
[`evaluation-corpus.md`](evaluation-corpus.md) for the marking rule.

| | Found | Marked | |
|---|---:|---:|---:|
| Everything marked | 91 | 96 | **95%** |
| Spans exact rather than merely overlapping | 91 | 91 | 100% |
| Precision — extractions a marking covers | 91 | 91 | **100%** |

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
| **`proper_noun`** | **4 / 9** | **44%** |

### Per language

| | Everything marked |
|---|---:|
| `en` | 30 / 31 — 97% |
| `ja` | 31 / 33 — 94% |
| `zh` | 30 / 32 — 94% |

No language is much worse than the others, which is the thing an aggregate
would hide and a test now watches for.

### What this does not say

- Nine answers, one model, one sitting, three genres. A sample, not a
  distribution.
- **The person who marked them wrote the extractor.** ADR-0010 warns about
  exactly this for a labelled corpus. The marking rule and the visibility of the
  markings are mitigations, not an answer.
- **The structural name rules were written *after* seeing these answers**, which
  is the same bias one level down. Discount the 91 → 95 accordingly. What can be
  said in its defence: the three families — a title, an honorific, a legal form —
  are what anyone listing structural markers for these genres would list, and
  the rules were narrowed, not widened, when precision fell. Two candidate rules
  were **not** written because they would have been invented to pass this set:
  `[甲乙丙丁]社` for Japanese contract parties and `[甲乙]方` for Chinese ones.
  Both are standard legal conventions and both stay out until material nobody
  here wrote asks for them.
- **The five remaining misses are `Borden Systems`, `甲社`, `乙社`, `甲方` and
  `乙方`.** A company name with no legal form, and party designators.
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
| Unbearing segments, **realistic answers** | 24 / 80 | **30%** |
| Unbearing segments, generated corpus | 18 / 135 | 13% |

**35% is the number to use.** The generated corpus was written to carry
particulars, so its 13% is optimistic by construction.

It was 35% before the structural name rules shipped, and the five-point fall is
the clearest evidence that coverage and extraction are the same question asked
twice: a segment whose only load-bearing token was a name used to bear nothing.

Of the 24, most are prose and six are table rows — and the table rows are
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
| Verdict correctness | 30 / 51 | 59% | the verdict a plant should *ultimately* carry |
| Source localisation | 12 / 33 | 36% | naming the value that was replaced |
| Source misdirection | 0 / 12 | **0%** | naming one that is *not* the value replaced |
| Refusals | 3 / 3 | 100% | protected responses refused rather than audited |
| Reproducibility | 30 / 30 | 100% | the same case audited twice, byte for byte |

Floating particulars attributable to no plant: **0**. Plants the segmenter cut
in two: **0**.

Per language, fabrication recall and false positives are 14/14 and 0/14 in each
of `en`, `ja` and `zh`.

### The trade behind source localisation

These were 35% and 0% through v0.3, when `contradicted` did not ship: a
`digit_drift` that should ultimately read `contradicted` read `floating`, and a
floating particular resolves nowhere and so carried no location. They were
measured anyway, for three versions, because **a metric introduced at the same
time as the feature it scores measures nothing.**

v0.4 moved them, and **36% is a number that was chosen rather than reached.**
akashi names the source only where the answer kept the source's digits exactly
and changed the text beside them. Letting it also explain a value whose digits
drifted takes localisation to 27 of 33 — and here is what that costs, measured
over three widths of neighbourhood with the plants' declared sources as ground
truth:

| the relation | segment | answer's items | whole package |
|---|---:|---:|---:|
| digits drifted, unit intact | 0 / 2 | 12 / 28 (43%) | 18 / 38 (47%) |
| unit swapped, digits intact | 2 / 2 | 7 / 7 | 12 / 12 |

The neighbourhood barely matters; which half of the value changed decides
everything. Three plant kinds explain the top row and none can be told from a
drift by anything in the text: an **invented** figure sits near a source number
of the same shape exactly as a drifted one does; a **derived** value such as
`28回` sits beside the `2回` it was computed from, so naming that source is not
unhelpful but *false*; and a contract full of `60 days`, `90 days` and `30 days`
offers a drifted `45 days` several equally good parents.

So `source misdirection` is the gated number and `source localisation` is not.
27 of 33 of the recall was given up in an afternoon to hold misdirection at
none, and a floor under localisation would have forbidden exactly that trade.
[ADR-0015](adr/0015-the-digits-are-the-evidence.md) is the decision.

### What this does not say

- 100% recall on a corpus authored for the method is evidence the method works
  on material designed for it. It is not evidence about production traffic.
- `declared misses passed` at 100% is not a score. It is the count of
  hallucinations akashi is known not to catch, published so a reader can price
  it. Improving it would mean building something ADR-0004 says is not possible
  deterministically.
- **The localisation recall is not independent of its generator.** All twelve
  are `unit_swap` plants, produced by a rule that swaps the unit and keeps the
  digits, measured by a rule that looks for digits kept and a unit swapped.
  That is the fifth falsification condition in `proposals/0002` — *the corpus
  measures its own author* — naming itself, and the figure should be read as
  "this fires when it should" rather than as a rate. The **precision** figure
  does not have this problem: it is measured against the `derived_value`,
  `invented_particular`, `digit_drift` and `grounded` plants, which were
  generated independently and which the rule declines.
- Twelve localisations is a small number and 0/12 is a weak claim about zero.

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
| Verdict correctness | 59% | ≥ 25% | bound unmoved; see below |
| Source misdirection | 0% | ≤ 5% | one of twelve breaches |
| Refusals | 100% | ≥ 100% | **invariant** (ADR-0008) |
| Reproducibility | 100% | ≥ 100% | **invariant** (ADR-0003) |
| Extraction recall, claimed kinds | 95% | ≥ 85% | |
| Extraction precision | 100% | ≥ 90% | |
| Unbearing segments | 30% | ≤ 55% | |

Three metrics are deliberately **ungated**: `declared misses passed`,
`acknowledged false positives` and `source localisation`. Gating a number you
want to move is how a measurement becomes a cage — and v0.4 is what that rule
was for. Localisation recall was cut from 27 of 33 to 12 of 33 to hold
misdirection at zero, and a floor under it would have made the right change a
build failure.

**Verdict correctness rose 24 points and its bound did not move.** It was set at
25% when the score was 35% and `contradicted` had not shipped; the score is 59%
now and the bound is still 25%. Raising a floor because a score rose is how a
floor quietly becomes a target, and the ``measured`` column is the record of
what was seen rather than a thing the bound must chase.

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

**Two more, from v0.4.** The first `contradicted` rule reported that `2.6kg`
contradicted **`300g`** — the source read `テントは 2.4kg、二人用。前回より
300g 軽い。` and both candidates were quantities in the sentence the segment's
grounded particular landed in. Every clause of the specified rule was satisfied
and the output was nonsense, because *same kind and nearby* is not a relation
between two values but a coincidence of layout. That defect is what produced the
table above and ADR-0015, and the repair narrowed the feature to roughly a third
of what it was specified to do.

The other: the first structural name rules put a proper noun on `筐体仕様` — `様` is an honorific and also the second character of 仕様, 模様,
多様 and 同様, which are words that live in exactly the specification and
contract documents akashi is aimed at. Precision fell to 99% and `様` was
dropped. That costs `佐藤様`, a real case, and the trade is the right way round:
**a precision-first extractor that is not precise is worth nothing at all.**
