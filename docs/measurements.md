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
| Detection recall over **everything planted** | 42 of 84 — 50% | 42 of 84 — 50% |
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
| **Recall over everything planted** | **42 / 84** | **50%** | **including the ones ADR-0004 says it cannot** |
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
- **The 100% and the 50% are the same corpus.** Fabrication recall excludes the
  declared misses, which is why it is a hundred; recall over everything planted
  includes them. Both are true and the second is the one to quote at somebody
  who has not read this page.

  Excluding them is right — the method cannot reach a negation flip or a
  cross-document stitch, and effort does not change that. But **a declaration
  lets a reader adjust what they expect; it does not move a denominator.** If it
  did, the cheapest way to improve any rate here would be to declare more of it
  out of scope, and the extraction section has printed two recalls since v0.3
  for exactly this reason. Detection printed one until it was noticed that a
  reader could take 100% away from a corpus where half the planted
  hallucinations are ones akashi passes on purpose.
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

## The unit check that did not ship

Issue #42 proposed a check needing no unit table. A unit the extractor does not
know makes a swap **invisible**: `2.4 furlongs` extracts as the bare number
`2.4`, that number grounds against the `2.4` inside a source's `2.4kg`, and
nothing floats. The proposed rule: *if a number grounds, and the token after it
in the answer differs from the token after the matched number in the source,
something was swapped.* The issue required it be priced before its scope was
fixed, and that if precision were poor it would not ship and the measurement
would be published anyway. This is that measurement.

### The material is 7 numbers, and that is the first finding

Across all 42 cases in both splits there are **7 grounded bare numbers**. In the
nine hand-marked answers there are 9, and every one is followed by a space or a
full stop. That is not an accident of authorship: a number extracts as *bare*
exactly when the extractor saw no unit after it, so the tail of a bare number is
something akashi has already decided is not a unit.

The case the check exists for — a unit akashi does not know — **does not occur
in either corpus**, because the person who wrote the unit lists also wrote the
sentences.

### What the naive rule does

Every firing below is a false positive; there are no true positives to find.

| how "the token after" is defined | fires | en | ja | zh |
|---|---:|---:|---:|---:|
| up to whitespace or punctuation | 5 of 7 | 0/1 | 3/3 | 2/3 |
| exactly one character | 7 of 7 | 1/1 | 3/3 | 3/3 |
| Latin letters only | 0 of 7 | 0/1 | 0/3 | 0/3 |

The reason is visible in the data. **Japanese and Chinese have no whitespace**,
so what follows a bare number is a particle or a verb phrase, not a unit:
`68` → `で`, `1.2.3` → `において`, `1.2.3` → `将公差改为`. The only definition
that stays quiet is "Latin letters only" — which is a unit table wearing a
different hat, and is blind to `2.4 千克` and `2.4 ファーロング`, the cases in the
two languages akashi exists to handle alongside English.

### A narrowing that works, and the thing it cannot see

Use the unit table on the **source** side only, where it need not be complete:
fire when the source demonstrably has a *quantity* at that position and the
answer's following word differs. This catches both motivating cases and fires on
**0 of 7** in the corpus:

```
The mass is 2.4 furlongs.       FLAGS  answer 'furlongs'  source 'kg'
重量は 2.4 ファーロング です。      FLAGS  answer 'ファーロング'  source 'kg'
```

It cannot distinguish a **swapped** unit from a **re-worded** one. `2.4
kilogrammes` and `2.4 furlongs` are structurally identical — a bare number
followed by a word the extractor does not know, where the source has a known
unit — and separating them needs a unit table with synonyms, which is the thing
the check exists to avoid. One is a faithful answer and the other is a
hallucination, and akashi would flag both identically.

### Why it does not ship

That ambiguity cannot be measured here, and **expanding this corpus would not
fix it — it would only move it.** New sentences would be written by the same
author as the unit lists, and the rate would measure that author's imagination.

This is the same self-reference that
[ADR-0015](adr/0015-the-digits-are-the-evidence.md) names, and it is not
confined to akashi: `tsumugi`'s `proposals/0003` calls its own section *"Ten
genres was not a corpus, it was a mirror"*, and `iriguchi` and `mamori` have the
same structure. Four libraries, one blind spot, no external ruler.

The exit is the v0.6 public corpus, and the honest position until then is that
the check has an **unmeasured** precision rather than a poor one. Shipping a
flag whose false-positive behaviour on unit synonyms is unknown would contradict
ADR-0015, written the same day.

**One thing this did establish, independent of the feature.** The corpus's 100%
fabrication recall is flattered: every unit in it is a unit the extractor knows,
so a swap into an unknown unit is currently invisible *and untested*. That gap
is real whether or not #42 ever ships.

---

## Latency, and the range that is part of it

`akashi audit`, end to end, on the nine hand-marked answers. **Two batches, some
hours apart**, on one machine that had other agent sessions and GPU work running
throughout.

| | batch 1 | batch 2 |
|---|---:|---:|
| the nine realistic answers (median each) | 1.16 – 1.57 ms | 1.11 – 1.56 ms |
| 2,832 characters | 8.53 ms | 8.53 ms |
| 11,334 characters | 34.08 ms | 32.75 ms |
| 45,342 characters | 134.09 ms | 132.61 ms |
| a 1-item package | 0.40 ms | 0.41 ms |
| a 1,000-item package | 211.64 ms | 204.04 ms |
| cold start, process to report | 318 – 375 ms | 359 – 380 ms |

**Linear in both directions.** Four times the characters is four times the time;
a package a thousand times larger costs about five hundred times as much, and
the `SourceIndex` that walks the whole package is the reason it is the second
axis at all. Nothing in segmentation, extraction or matching is quadratic.

### Why two batches rather than more repetitions

Repeating a measurement twenty times inside one batch establishes that
conditions held **for the length of the batch**, and nothing else. A sibling
project measured ±1% across three consecutive runs and **25% between batches an
hour apart** on this same machine — precise inside the batch, and about the
machine rather than about the code.

akashi's spread between batches is **at most about 4%** on everything except
cold start, which moved ~13% and is the one that is mostly Python's interpreter
starting rather than akashi doing anything.

That is a result about akashi rather than a claim about measurement hygiene: an
audit is pure CPU with no I/O in the loop, no model and no network, so there is
little for the machine's state to act on. **Two batches is two batches**, and
the number to quote is the range rather than either end of it.

### What this does not say

- **It is one machine.** 28 logical CPUs, Windows, CPython 3.12.8. Nothing here
  is portable to another; only the *shape* — linear, sub-millisecond per
  sentence, three orders of magnitude under a model — is expected to survive.
- **No GPU was involved and none could be.** That is structural rather than
  observed: `src/akashi` imports fourteen standard-library modules and nothing
  else, and the zero-dependency CI job and the `no-network` import contract both
  enforce it. **"No GPU is used" is checked; "the timings are hardware
  independent" is false** and is not claimed.
- **Cold start is Python's**, not akashi's. 1.5 ms of the ~370 ms is the audit.
  It is reported because it is what a CLI user feels.
- The nine answers were written for the extractor by the person who wrote it,
  and their length distribution is not evidence about production traffic.

### What it settles for v0.6

The roadmap's comparison against a model judge has one prior that no longer
needs measuring: **a model judge does not run in this range.** The cheapest one
is tens to hundreds of milliseconds per call and usually more, so the gap is two
to three orders of magnitude. A 25% error of the kind the sibling found would
not close it, and neither would a 10× one.

That is not an argument that akashi is better. It is the reason the comparison
has to be about **agreement**, not about speed: the speed question is already
answered and answering it again would be measuring the obvious.

---

## The cost of an audit, on input somebody else chose

akashi audits text a model produced, and `akashi mcp` lets the model choose the
arguments. So the length and the shape of an answer are numbers an attacker
controls, and until v0.5 extraction was **quadratic** in them.

Measured end to end through `akashi audit`, one segment, all four packs:

| answer | 8,000 chars | 16,000 chars | growth per doubling |
| --- | --- | --- | --- |
| ordinary prose | 0.05 s | 0.09 s | ×1.8 |
| **digits only, before the bound** | 10.06 s | **38.09 s** | **×4.0** |
| digits only, after the bound | 0.85 s | 1.60 s | ×1.9 |

`x4.0 per doubling` is quadratic to three digits, held across five sizes. At
16,000 characters the adversarial answer costs **420 times** what prose of the
same length costs; at 160,000 it would cost an hour.

**The cause is not exotic.** `\d[\d,.]*\d` followed by a unit consumes the
run, fails to find the unit, and retries at every shorter length, at every
start position. Read with `re`'s own parser rather than by eye, **32 of the 40
shipped rules have an unbounded repetition** and 102 unbounded repeats between
them; 28 use lookaround.

**The fix is a bound, not a timeout.** An audit is reproducible (ADR-0003), and
a run that gives up after a second gives a different report on a slower machine.
`MAX_RUN = 256` caps every repetition at compile time, set the way a floor is:
the longest particular in the whole corpus is **21 characters**, the 99th
percentile is 14, and the longest evidence item or segment is 94.

```text
unbounded repeats in the shipped rules   102  ->  0
particulars extracted from the corpus    412  ->  412   identical, in order, at the same offsets
```

Every metric below is unchanged by it, which is the other half of the claim.

## What the corpus cannot tell apart

`domain/matching.py` justifies a spacing tolerance at length: `2.4kg` finds
`2.4 kg`, `第30条` finds `第 30 条`, and the module's own docstring calls it one
of the two problems a plain substring search gets wrong. Unit tests cover it.

Making the matcher selectable made it measurable, and the answer is that **no
published number here measures it at all**:

| matcher | grounded | floating | share |
| --- | --- | --- | --- |
| `normalized` | 102 | 52 | 66.2% |
| `exact` | 102 | 52 | 66.2% |

Identical, particular for particular, over all 30 cases. The evidence contains
**45** quantities written with a space (`14 days`, `4 weeks`, `30 days`), and
**zero** answers re-space one — because the generator writes answers that quote
the evidence verbatim.

So this is a statement about the corpus, not about the matchers. A model
re-spaces a quantity constantly, and the tolerance is why akashi survives that;
what is missing is a case that shows it. `tests/test_matcher_choice.py` asserts
the two agree, so the gap stops being invisible: **when the corpus grows a case
that re-spaces a quantity, that test fails and should be deleted.**

## The five particulars akashi missed, and what closed four of them

The hand-marked corpus said extraction recall was **91 of 96**, and the five
misses were all `proper_noun`:

```text
en-contract-01: missed proper_noun 'Borden Systems'
ja-contract-01: missed proper_noun '甲社'
ja-contract-01: missed proper_noun '乙社'
zh-contract-01: missed proper_noun '甲方'
zh-contract-01: missed proper_noun '乙方'
```

**Four of the five are a convention, not a name.** `甲` / `乙` / `丙` as a
contract party is as fixed as *Party A* — a closed set of five stems and a
closed set of suffixes — so it is a structural rule like every other one here,
and not a lookup of the four strings that were missed.

| | before | after |
| --- | --- | --- |
| recall over everything marked | 91 of 96 — 91% | **95 of 96 — 99%** |
| recall over the claimed kinds | 91 of 96 — 95% | **95 of 96 — 99%** |
| spans exact rather than near | 91 of 91 | 95 of 95 |
| **precision** | 100% | **100%** |
| unbearing segments (marked) | 30% | **28%** |
| planted-corpus false positives | 0 of 42 | **0 of 42** |

Precision holding at 100% across both corpora is the check that matters: a rule
that found four more names by finding things that are not names would trade a
silent miss for a loud lie, and a false name grounds against nothing and reads
as a fabrication in the answer.

**These four were in the measured set.** The rule is general and the score is
partly in-sample, and both halves of that sentence are true. `--held-out` reports
the same 99%.

**The fifth is what a library would be for.** `Borden Systems` is a company name
with no legal form beside it, and no structural rule reaches it —
`docs/adr/` and the report's own `limits` have said so since v0.4: *akashi reads
structure, not names.*

## What an external NER model would and would not buy

Measured before reaching for one, because the answer decides whether the
dependency is worth its licence and its weight.

**On extraction:** one of the five misses above. The other four were a rule.

**On the 30% of segments akashi finds nothing in:** nothing. Those segments are

```text
No follow-up was arranged.
Liability under this agreement is not capped.
In short, either side can bring the arrangement to an end.
It is worth noting that the exposure is bounded rather than open.
```

Negations, summaries and hedges with no name, no figure and no date in them. An
entity recogniser finds nothing there either, because there is nothing there —
which is what `docs/proposals/0002` already reported as *about a third of a
realistic answer is prose akashi has nothing to check in*.

**And the licences are not uniform.** GLiNER's v1 models are **CC-BY-NC-4.0** —
non-commercial — and only v2.1 and GLiNER2 are Apache-2.0. spaCy's code and its
small models are MIT, with OntoNotes provenance behind the English one.

**The caveat this cannot settle.** The corpus is generated and hand-marked by
the people who wrote the extractor (ADR-0010), so it may under-represent exactly
the text a model would help with. What is measured here is that on *this*
corpus the payoff is one particular; whether that holds on somebody else's is
the open question, and it is the same shape as the corpus not being able to tell
two matchers apart.

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

Four metrics are deliberately **ungated**: `declared misses passed`,
`acknowledged false positives`, `source localisation` and `recall over
everything planted`. Gating a number you
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

## Which guards have been watched failing

Every number above is produced by something, and every one of those things is
guarded by something else. A guard nobody has watched fail is a guard nobody has
evidence about — `exit 0` is not evidence until something has shown it can be
non-zero.

This section exists because a sibling project found that its layering gate had
**never run once** in the project's whole history, silently, while reporting
success. akashi's gate is invoked differently and is fine. The audit that
established that is below, including the half that came out badly.

**Watched failing, deliberately:**

| guard | how it was made to fail |
|---|---|
| `lint-imports` | a forbidden `domain -> infrastructure` import added to `span.py`; exit 1, violation named |
| the vendored-copy hash | the recorded `sha256` corrupted |
| the upstream drift check | a real 404, after `tsumugi` moved its schema — which is how it was found to be *skipping* rather than failing |
| the packaging test | the `force-include` destination changed to `akashi/schema` |
| the wheel build | `schemas/` empty, which turned every CI job red |
| the floor gate's exit code | a `Breach` injected into `check_floors` |

**Not watched failing:**

- `generate_cases.py --check-only`
- *"Assert nothing came with it"* — the zero-dependency claim itself
- *"The contract is inside what was installed"* — seen passing against a real
  install; never seen fail
- **`akashi eval --gate` on a real floor breach.** The exit code is covered by an
  injected `Breach`, so the wiring is proven. What has never happened is a score
  actually falling through a bound and stopping a build. **The floors exist to
  stop a regression and no one has seen them stop one.**

The last one is left as it is rather than manufactured. Producing a genuine
breach means degrading the extractor on purpose, and a number reached that way
would be a number about the degradation. The honest position is to say the gate
has not been fired in anger, and this is where that is said.

**Two things went wrong during the audit itself**, which is the argument for
writing it down rather than trusting the summary:

- `python -m importlinter.cli lint` exits **0 with no output at all**, even with
  a live violation. CI uses the console script and is unaffected — but that
  module form was run earlier in this project, produced nothing, and was passed
  over. The console-script rerun that caught it was luck.
- The first attempt to read `lint-imports`' exit code read `$?` after a pipe,
  which is the exit code of `tail`. An exit code is evidence only once you have
  also checked whose it is.

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

## What the grounded share does on the three failures rivals are built for

Five answers, each isolating one thing, run through `evaluate()` on the default
matcher. The evidence is chosen so that only the named failure is present.

| case | answer | evidence | akashi |
| --- | --- | --- | --- |
| subject swapped | `The tent weighs 2.4kg.` | `The stove weighs 2.4kg.` + `The tent weighs 3.1kg.` | **1.0** |
| date on the wrong event | `...signed on 2024-03-01.` | `...terminated on 2024-03-01.` | **1.0** |
| negated predicate | `The warranty does not cover water damage.` | `The warranty covers fire only.` | none |
| inverted relation | `Alice reports to Bob.` | `Bob reports to Alice.` | none |
| honest paraphrase | `The tent weighs 2.4 kilograms.` | `Tent mass: 2.4kg.` | **0.0** |

**Two fabrications score 1.0 and one correct answer scores 0.0.** On these five
the number is not merely a weaker signal than an entailment model's -- it points
the wrong way on three of them and is absent on the other two.

None of this contradicts what `limits` already says. It is the size of it that
was never measured: *"a statement about strings, not about truth"* is true, and
a reader who sees 1.0 on row 1 will not conclude that the tent might weigh
3.1kg. The line describes the mechanism; it does not price the consequence.

Rows 1 and 2 are #83 -- a `Particular` is a value with no subject, so `find_all`
never asks whether the sentence the value turned up in is about the same thing
the answer's sentence is about. Every rival decomposes into a claim carrying a
subject and a predicate, which is the part akashi drops.

Rows 3 and 4 bear nothing at all, and until #84 they were also the rows the
judge never saw: `claims_for` walked particulars, so a segment with none
produced no claim. The escape hatch built for *"akashi cannot check this"*
covered only the sentences where akashi found something and failed to place it.
Row 5 is what the judge was always for.

**What this does not license.** Not a similarity threshold. The contradiction
rule was already priced here at 47% on drifted digits against 12/12 on intact
ones, and rows 1 and 2 are drifts. #83 proposes reporting the rival value as a
fact with offsets and leaving the verdict alone.

## What four bounds did without saying so

Three of akashi's four bounds changed the answer and reported nothing. Measured
on the code as it stood, before `domain/bounds.py`:

| bound | input | what happened | what the report said |
| --- | --- | --- | --- |
| `LOCATION_LIMIT` (32) | a particular occurring 40 times in one document | 32 places reported | nothing |
| `MAX_CLAIMS` (64) | an answer with 200 floating particulars | 64 claims sent, 64 judgements | nothing |
| `MAX_RUN` (256) | a 301-digit number | **the number vanished** | nothing |

The third is the one that matters. `evaluate()` returned `grounded_share=None`
-- *akashi looked and there was nothing to check* -- for a sentence that plainly
contained a number. Nothing raised, nothing was slow, and the report was wrong
and looked fine. The cliff is between 257 and 300 digits, which is a shape a
release will meet: an identifier, a hash, a base64 blob, a serial number.

`MAX_DEPTH` was the fourth and was already correct: it refuses the document by
name rather than truncating it.

**The bounds themselves were not changed and are not settable.** A caller who
could raise `MAX_RUN` could restore the quadratic blow-up it exists to prevent,
on input akashi is built to receive from strangers. What a caller gets instead
is a receipt: every bound that bit produces a line in `limits` and an entry in
`bounds[]`, naming itself, its value, and what it left out.

Writing the detector for `MAX_RUN` produced a defect of its own, found by the
test asserting the receipt does **not** fire at the bound: the scan counted the
full stop closing a sentence as part of the number, so a run of exactly 256
digits measured as 257 and produced a receipt for a figure akashi had read
correctly. A run must end on a digit.

## Whether a deterministic rule can see a swapped subject (#83)

The corpus already plants the defect. `entity_swap` (18 cases) is *a particular
replaced by one of the same kind from a different item -- it still resolves, so
akashi passes it*, and `cross_document_stitch` (9) is *subject from one item,
predicate from another, both verbatim*. Both are marked `expect_detected: false`,
which is the corpus declaring #83 in advance.

**A first attempt filtered the population on `expect_detected` and measured 108
grounded particulars of which 0 were planted.** That filter selected against
exactly the thing being measured. Corrected, the population is 27.

The candidate signal: character bigram overlap between the answer's sentence and
the evidence sentence the value was found in, with the value itself removed from
both sides. Characters rather than words because a word boundary in Japanese is
a model's opinion and this must not depend on one.

| overlap | faithful | swapped |
| --- | --- | --- |
| exactly 0 | 2 | **5** |
| 0.00 – 0.10 | 3 | 0 |
| 0.10 – 0.25 | 8 | 2 |
| 0.25 – 0.50 | 22 | 8 |
| 0.50 – 1.00 | 46 | 12 |

Zero overlap looks like a finding: 5 swapped against 2 faithful, 71% precision.
It is not one.

| | faithful | swapped | faithful at 0 | swapped at 0 |
| --- | --- | --- | --- | --- |
| en | 22 | 9 | **0** | **0** |
| ja | 32 | 9 | 1 | 3 |
| zh | 27 | 9 | 1 | 2 |

**The rule never fires in English at all**, on a population where swaps are
evenly spread across the three languages (9/9/9). English sentences share
function-word bigrams — `th`, `he`, ` t` — whatever the subject, so the overlap
cannot reach zero; Japanese and Chinese have no such floor. The measure is
reading the script, not the subject.

The medians agree: 0.609 faithful against 0.500 swapped. There is no threshold
anywhere on that scale worth having.

**So no deterministic rule ships for #83.** What ships instead is
`--judge-grounded`: akashi already had a judge that could answer this and
structurally never showed it the case, because `claims_for` skipped every
grounded particular. The reason it skipped them — *akashi already knows where
that string is* — is true and incomplete. Knowing where a string is does not say
whether the sentence it landed in is about the same thing.

`tools/measure_subject_agreement.py` reproduces every number above.

## What vocabulary from another head trapped (#55)

`proposals/0002` §7 lists *"the corpus measures its own author"* as a
falsification condition. Every genre here was written by whoever was writing the
extractor, so the way a quantity is *spelled* came from one head.

`tools/draft_genres.py` asks a local model (`qwen2.5:14b-instruct`, ollama, on
this machine) for subjects, attributes and — the part that matters — **values
written the way a trade actually writes them**. Nothing it produces reaches a
fixture: a person reads and commits. CI calls no model and ADR-0003 is untouched.

Twenty-four drafts, three languages, one batch each:

| | drafts | malformed | well-formed | akashi could not extract |
| --- | --- | --- | --- | --- |
| en | 8 | 5 | 3 | 1 |
| ja | 8 | 1 | 7 | 4 |
| zh | 8 | 0 | 8 | 4 |
| **total** | **24** | **6** | **18** | **9 — 50%** |

**Nine of eighteen, and they are one defect.**

| written | akashi extracted | what changed |
| --- | --- | --- |
| `320 km/h` | `320 km` | a speed became a distance |
| `10mg/mL` | `10mg` | a concentration became a mass |
| `20,000 m³` | `20,000 m` | a volume became a length |
| `120 m²` | `120 m` | an area became a length |
| `320 公里/小时` | `320 公里` | a speed became a distance |
| `1:45.32` | `1:45` | a different lap time |
| `40' x 8'6"` | `40`, `8`, `6` | feet and inches, unrecognised |

The quantity rule ended in a lookahead for a letter or a digit, and `/` is
neither. **A particular cut at the slash grounds against a document that says
something else and is reported `grounded`** — the same harm as #83, arriving
deterministically and fixable deterministically.

`docs/measurements.md` had recorded 99% extraction recall. That number was true
of the corpus and the corpus contained none of this notation.

**Fixed for `/` and for `²`/`³`.** Not for `1:45.32` or for feet-and-inches:
those are new kinds rather than a wider unit, and they are recorded here rather
than guessed at. Only the superscript characters count — `m2` in running text is
`m` followed by a number as often as it is a square metre, and guessing would
trade a miss for a wrong answer.

After the fix: 30 cases, fabrication recall 42/42, false positives 0/42,
reproducibility 30/30 — unchanged. The corpus could not see the defect and
cannot see the repair either, which is the point being made.

### Three versions of the check, and two of them were wrong

The tool decides whether a drafted value is extractable, and that check was
wrong twice before it was right.

1. **Exact equality.** Called all five English drafts a miss, including three
   where akashi was right: `5.2%` out of `5.2% ABV` is the value, and `ABV` is
   what the value is *of*.
2. **Compare the digits.** `fold` is NFKC, which turns the superscript in `m³`
   into a digit — so it reported a real defect for a reason that was not true.
   A check that reaches the right answer by the wrong route is one input away
   from the wrong answer.
3. **Look at what was left behind.** A leftover separated by a space or a comma
   is a different word; one glued directly on changed the token. This is the
   rule that ships.

### Six more batches, and what the first fix left behind

72 drafts in nine batches, three languages, same model. The rate against the
extractor as each fix landed:

| | well-formed | akashi could not extract | |
| --- | --- | --- | --- |
| before any fix (first 3 batches) | 18 | 9 | **50.0%** |
| after the `/` and superscript fix | 54 | 10 | **18.5%** |
| after the CJK denominator and trade units | 51 | 7 | **13.7%** |

**The second round found that the first fix was half a fix.** `320 km/h` was
repaired and `320 千米/小时` was still cut at the slash, because `_UNIT_TAIL`
took a Latin denominator only. So was `50mg/日` — a Japanese document writing a
Latin unit over a local one, which the shared SI rule matches before either
language pack gets a turn. A test written for the Japanese katakana units then
found the same omission a third time, in the rule beside the one that was fixed.

That is the argument for running more than one batch: **a repair is written
against the examples that prompted it**, and the examples that prompted it are
the ones the first batch happened to contain.

`psi`, `rpm`, `kWh`, `Nm`, `bar`, `kPa`, `dB`, `kcal`, `hp` and the rest were
missing outright. The unit list was written by the person who wrote the corpus,
so the corpus contained no unit the list was missing.

The well-formed count *falls* between rows two and three because the tool
learned to tell two failures apart. `每次25毫克，每日三次` is a clause in a field
that asked for a value; akashi took `25毫克` out of it, which is the quantity in
it. Counting that against akashi was flattering the drafts and slandering the
extractor. Which side the leftover sits on decides it: glued on the **right** is
akashi cutting a unit short, glued on the **left** is a draft that is a phrase.

**The seven that remain, and none of them is a wider unit:**

| | |
| --- | --- |
| `40' x 8'6"`, `25' x 50'`, `12フィート6インチ` | feet and inches — a new kind |
| `5.5%vol` | a word after a percent sign |
| `M号`, `纯棉` | a size and a material — akashi has no kind for either |

Recorded rather than guessed at. The corpus evaluation is unchanged by every
fix above: 42/42 fabrication recall, 0/42 false positives, 30/30
reproducibility.

## Whether a deterministic rule can see two sources disagreeing (#88)

The candidate: **same kind, same shape, different digits, in a different item**.
`3.1kg` and `2.8kg` both reduce to `#kg`, so a document giving one where another
gives the other looks like a disagreement.

Over the corpus, 108 grounded particulars, 6 protected cases skipped:

| | |
| --- | --- |
| grounded particulars with at least one rival | **16 of 108 — 14.8%** |
| rival pairs in total | 32 |
| cases with any rival | 11 of 24 |

**Every one of them is a false positive.** Not most — all of the sixteen:

| value | rival | what they actually are |
| --- | --- | --- |
| `30 days` | `45 days`, `60 days` | notice period, payment terms, renewal period |
| `68` | `128`, `82` | diastolic, systolic, pulse |
| `第12条` | `第30条` | two different articles |

A contract holds several time periods; a clinical note holds several
measurements; a statute holds several article numbers. **A document that
contains many values of one shape is not a document disagreeing with itself, it
is a document.** Shape is a property of the notation, not of the subject.

Twelve of the 32 pairs sit on a value the case marks as planted, and that is an
artefact of matching plant text by string rather than evidence of the rule
working: the plant is a digit drift, and the rival relationship is not what was
planted.

**So no deterministic rule ships for #88 either, and it is the same wall as
#83.** Both need to know what a sentence is *about*, and
`tools/measure_subject_agreement.py` already showed the deterministic route to
that reads the script rather than the subject.

**What does reach it is already shipped.** `--judge-grounded` (#89) turns a
grounded particular into a claim, and a judge handed the whole evidence — both
documents — is being asked exactly the right question:

```
(about: 3.1kg, found verbatim in: itm_01)  The tent weighs 3.1kg.
evidence: [The tent weighs 3.1kg., Tent, revised spec: 2.8kg.]
```

`tools/measure_source_conflict.py` reproduces every number above.
