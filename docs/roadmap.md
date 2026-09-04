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

## 2. Where akashi is harder to adopt than it needs to be

### 2.1 One sample at a time

`evaluate()` and `evaluate_sample()` take a single answer. Every rival takes a
dataset and returns a table. A person with 500 rows currently writes the loop,
the aggregation and the error handling themselves.

### 2.2 No pytest integration

DeepEval's `assert_test` is most of why people adopt it: the evaluation lives in
CI beside the unit tests. akashi has `fail_on_findings` on the CLI and nothing
for a test file.

### 2.3 The word everyone searches for is `faithfulness`

And akashi must not use it. `grounded_share` is not faithfulness and naming it
so would be the exact dishonesty this project exists to refuse. The reconciling
move is documentation — a table saying which akashi number answers which rival's
question, and which ones it does not answer at all — not an alias.

## 3. Deliberately not doing

**An NLI model in the default path.** It would make akashi a slower, less
accurate copy of tools that already exist, and would cost the one thing it has
that they do not: a report whose every claim is an offset.

**A `faithfulness` alias.** See 2.3.

**Extraction by a hosted NER model by default.** Measured: it closes 1 of the 5
extraction misses on the corpus and none of the 30% unbearing, because those
segments carry no name, figure or date to find. GLiNER v1 is CC-BY-NC-4.0 and
unusable commercially; v2.1 is Apache-2.0. Worth an optional engine, not a
default (#67).
