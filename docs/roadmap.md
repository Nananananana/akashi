# Roadmap

Ordered by what a reader of a report is most likely to be misled by, not by
what is easiest to build. Every item names the measurement that put it here;
an item with no measurement under it is not on this list yet.

`docs/measurements.md` is the evidence. This file is the ordering.

## What akashi is, stated once so the list below reads correctly

akashi compares **strings**, deterministically, offline, with no model, and every
claim it makes is an offset a reader can open. That is the whole of its
guarantee and the source of both its value and every item in section 1.

Rivals (RAGAS, DeepEval, TruLens, RefChecker) decompose an answer into *claims*
carrying a subject and a predicate and pass them to an NLI model or an LLM.
They answer a question akashi cannot, and they cannot tell you the byte offset
of the thing they judged. These are different tools and the roadmap does not
try to turn one into the other.

## 1. Where the current approach does not hold

### 1.1 A value grounded against the wrong subject scores 1.0 — #83

`The tent weighs 2.4kg.` against evidence saying the *stove* weighs 2.4kg **and
the tent weighs 3.1kg** reports a grounded share of **1.0**. A `Particular` is a
value with no subject (ADR-0004), so `find_all` never asks whether the sentence
the value turned up in is about the same thing the answer's sentence is about.

This is the most common RAG failure there is, and it is the one akashi scores
perfect. It is first on this list for that reason.

The proposal is **not** a similarity threshold — the contradiction rule was
already priced at 47% on drifted digits against 12/12 on intact ones. It is to
report the rival value as a fact with offsets and leave the verdict alone.

**Blocked on measurement**, as contradiction was: the corpus has to price how
often a rival is named on an answer that was right.

### 1.2 The grounded share is anti-correlated on the cases that matter

Two fabrications at 1.0, one correct paraphrase at 0.0, on five hand-built cases
(`docs/measurements.md`). `limits` says *"a statement about strings, not about
truth"*, which is true and does not convey this.

Not a code change on its own. It is the reason 1.1 is first, and the reason the
certificate should carry an example rather than only the sentence.

### 1.3 About 30% of segments bear nothing

Measured on the corpus. akashi looks at them and has nothing to compare. #84
now forwards them to a judge when there is one; **without `--judge` they remain
a silent third of the answer**, counted honestly as `unbearing` and checked by
nobody.

### 1.4 Bounds are reported now, and that was the audit worth doing

akashi has four bounds and **three of them changed the answer silently** until
they were audited. `MAX_RUN` was the one that mattered: a 301-digit number was
not partly seen, it was not seen at all, and `evaluate()` returned *"nothing to
check"* for a sentence that plainly contained one. Nothing raised. Nothing was
slow. The cliff is between 257 and 300 digits, which is a shape a release meets
on day one — an identifier, a hash, a base64 blob, a serial number.

Fixed (`domain/bounds.py`): every bound that bites produces a line in `limits`
and an entry in `bounds[]`, which is in the published schema. The bounds
themselves did not move and are still not settable — a caller who could raise
`MAX_RUN` could restore the quadratic blow-up it exists to prevent.

**The general form of the finding is worth more than the three fixes.** A
constant is safe to add and unsafe to leave: the code that introduces it knows
what it is protecting, and the code that eventually hits it does not. Anything
added here that caps, truncates or samples has to produce a receipt in the same
commit.

### 1.4 When the evidence disagrees with itself, nobody is told — #88

akashi grounds a particular against whichever evidence item contains it. If the
retrieved set holds two documents that disagree, the answer grounds against one
and the report says `grounded`, share 1.0.

akashi is the only thing in the pipeline positioned to see this: it has already
extracted every particular from every source, with offsets, deterministically,
and since #87 that index is grouped by `(kind, digits)` so the scan is cheap.

Blocked on the same measurement as 1.1, and for the same reason: the obvious
rule is the drift rule already priced at 47%.

### 1.5 The default matcher's tolerance is measured by nothing

`normalized` lets a particular's internal spacing vary and the corpus cannot
tell it from `exact` — 102 grounded / 52 floating under both, across all 30
cases. 45 spaced quantities appear in evidence and no answer re-spaces one.

The tolerance is probably right for CJK and the argument for it is in
`domain/matching.py`; what is missing is a case in the corpus where the two
answers differ. ADR-0018 point 5.

### 1.6 An audit was quadratic in answer x package — done

**Done.** Two axes met and neither was bounded, so an audit of 60 KB against 400
documents took 8.6 s and 32 MiB, and doubling both multiplied the cost by 4.1.
Now 1.0 s and 4.7 MiB, and doubling both multiplies by 2.05. Same verdicts on
every measured row.

Three things, and the first is the one worth carrying forward: **`LOCATION_LIMIT`
capped how many places a particular is reported in within one document, and
nothing capped how many documents it was cited from.** The comment giving the
reason -- a particular that occurs everywhere carries no more information for
being listed everywhere -- was written for the axis that prompted it. A package
of contracts that all cite the same date produced one location per contract.

`SOURCE_LIMIT` is now that bound, with a receipt saying the document count is a
floor. `required_run` lets `Evidence.locate` skip an item that provably cannot
hold a particular, and the truncation receipt is counted once per particular
rather than once per document per particular.

Full table, the measurement that was wrong, and the poison that found a *test*
rather than the code: `docs/measurements.md`, "Where an audit's time and memory
actually went".

### 1.7 The remaining superlinearity is the answer axis

Bounded now on the package axis and not on the answer's: an answer of *n*
particulars still asks every one of them of every item, and the prefilter makes
that cheap rather than absent. Measured, doubling the answer alone against a
fixed package is ×3.1.

An inverted index over the evidence would make it a lookup. It is **not**
proposed yet, and the reason is the one this file keeps making: nothing has been
measured that says the remaining cost is anybody's problem. An answer long
enough to matter is an answer no reader reads, and akashi has no user reporting
it. The measurement to take first is what real answers and real packages are
sized like -- `bench` owns that -- not another structure.

### 1.8 Reducing text was a third of an audit -- done

**Done.** With the locations work of 1.6 finished, the cost moved: `search_form`
and `_fold` were 34% of an audit and `extraction._candidates` 29%.

Folding ran a Python loop iteration and two `unicodedata.normalize` calls per
character. Memoizing `_fold` was the obvious move and measured **0.84x** on
English -- 36 distinct characters produced 472,996 calls, so the hit rate was
99.99% and `lru_cache` still cost about what the two `normalize` calls cost. It
was not the call that was expensive; it was calling it per character at all.

Ordinary text is not moved by any step of the reduction, and three C calls find
that out. 1.42x on a batch of English samples, 1.54x with more contexts per
sample, 1.19x on Japanese, and **neutral** on a single audit that reuses one
package -- which is the row worth keeping, because it says where the win is not.

Full numbers, the five conditions and the disagreement that put each one there:
`docs/measurements.md`, "The reduction that moves nothing".

### 1.9 What is measured and not taken

Two, both real, both behind a question rather than behind effort.

**The offset map.** `origin` and `extent` are `tuple(range(n))` when the map is
the identity, and they are 18% of what a 400x400 audit traces. A `range` object
would be free -- and `range(3) == (0, 1, 2)` is `False`, so `SearchForm.__eq__`
would stop agreeing between the fast path and the definition, which is exactly
what the property test permitting the fast path compares.

**The rules that cannot match.** 46 rules run against every segment, and 87% of
them cannot match an English sentence. The cost is genuine C-level scanning --
0.139 ms of `_candidates`'s 0.167 ms -- so the only way to remove it is not to
run the pattern, which needs a literal that any match must contain. The same
argument as `required_run`, one level up. It is not taken because deriving that
soundly from an arbitrary regex needs `re`'s private parser, and a prefilter
that is *nearly* sound drops findings silently. Restricting rules by the
segment's script would be sound to implement and would **change the answer**,
which is a different proposal and belongs in an ADR, not in a speed section.

## 2. Where akashi is harder to adopt than it needs to be

### 2.1 One sample at a time — done

**Done.** `evaluate_samples()` takes a list, a generator, a HuggingFace
`Dataset` or a `pandas.DataFrame`. The share counts particulars rather than
rows; a refused row is kept as a refusal; `describe()` will not hand over a bare
number.

### 2.2 No pytest integration — done

**Done.** `akashi.testing.assert_grounded`. The failure names every floating
particular, what was skipped, and the limits. `allow_floating` waives one, and a
waiver for something that stopped floating fails too.

### 2.3 The word everyone searches for is `faithfulness`

And akashi must not use it. `grounded_share` is not faithfulness and naming it
so would be the exact dishonesty this project exists to refuse. The reconciling
move is documentation — a table saying which akashi number answers which rival's
question, and which ones it does not answer at all — not an alias.

## 3. Deliberately not doing

**An NLI model in the *default* path.** Not because entailment is wrong -- the
previous version of this file said akashi would not ship one at all, and that
was too strict. It is available now as `--judge nli` (`akashi[nli]`,
HHEM-2.1-Open, Apache-2.0, ~600MB, runs on a CPU and needs no network after the
download), because refusing it left akashi weaker than the tools people already
have at the question they ask most.

What stays out of the default is the *dependency*, not the capability. `pip
install akashi` still brings nothing and opens no socket, and a verdict is still
computed by comparing strings. A judgement is an annotation with a named model
on it (ADR-0017) and it does not move `report_id`.

**A `faithfulness` alias.** See 2.3.

**Extraction by an NER model by default.** Measured: it closes 1 of the 5
extraction misses on the corpus and none of the 30% unbearing, because those
segments carry no name, figure or date to find. GLiNER v1 is CC-BY-NC-4.0 and
unusable commercially; v2.1 is Apache-2.0. Worth an optional engine on the same
pattern as the judge, not a default (#67).

### 3.1 A deterministic library — measured, and the door stayed shut (#67)

The owner allowed libraries to be tried. #67 split that into two doors and asked
for each to be priced separately; the decision rule went into the issue **before**
the numbers.

**Door A does not open.** Extraction recall is 99.0% and the single remaining
miss is a company name with no legal form — Door B by construction. Of the seven
drafted-vocabulary misses, four were feet-and-inches, and **two lines of stdlib
`re` closed all four**, which is the middle clause of the rule answering itself:
a library that does what `re` already does is a dependency bought for nothing.
`regex`, a segmenter and a date parser each had nothing to buy (43 rules compile
under stdlib, segmenter cut-in-two is 0, dates 9/9).

Cost of the four that closed: extraction 8.27 → 10.01 ms, about +5% of a whole
audit. `docs/measurements.md` has the full table.

**Door B — a model at audit time — is still ADR-0003 and `proposals/0002` §6**,
and stays with `bench`. Nothing here moves it.

### 3.2 Two kinds akashi does not have

`M号` and `纯棉` — a size and a material — are not a quantity, a date or a name.
Drafted vocabulary found both. Adding a kind is a vocabulary decision with a
report contract behind it, not an extraction rule, and neither has been seen
twice yet.

`5.5%vol` is deliberately not closed for the same reason: **one observation from
one batch, and a closed set of percent suffixes chosen from a single draft is
fitting a rule to the sample** — the exact failure the drafting exercise exists
to expose.

## 3.5 Rejected from the original specification

`akashi_specification.md` is the design this was started from. ADR-0018
reconciles it with what shipped; three of its proposals are deliberately not
built:

- **an adapter that reads tsumugi's SQLite directly.** A private schema is not
  a contract. akashi reads the published `tsumugi.context-package/1` and imports
  tsumugi nowhere, enforced by an import contract and a nightly drift job.
- **`confidence_score: float` on every claim.** On an exact comparison that is
  1.0 or 0.0, and a float where a boolean lives is how a threshold arrives.
- **`verified` / `dangling_unsupported` / `partially_supported`.** Three words
  merge what the shipped six keep apart: *found nothing to check*, *did not
  look*, and *could not look* are different facts about an audit.

## 4. Adopted rather than written

The rule is: **the domain depends on nothing but the standard library, and
everything outside it may depend on whatever is good and commercially
licensed.** akashi is not a place to reimplement other people's work.

| what | where | licence |
| --- | --- | --- |
| HHEM-2.1-Open (entailment) | `adapters/nli_judge.py`, `akashi[nli]` | Apache-2.0 |
| transformers / torch | same | Apache-2.0 / BSD-3 |
| Anthropic SDK | `adapters/claude_judge.py`, `akashi[claude]` | MIT |
| DeBERTa-v3 zeroshot-v2.0-**c** (alternative NLI) | selectable by name | MIT, commercially-licensed training data |

Every one of them sits behind a port the domain defines and an extra a caller
opts into. That `NliJudge` needed **no change to the port, to `claims_for`, or
to anything that decides a verdict** is the test of whether the seam was drawn
in the right place.
