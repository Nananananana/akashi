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
