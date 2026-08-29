# 10. Label the response, not the ideal answer

**Status:** accepted

Taken, with thanks, from `tsumugi`'s ADR-0013, and from `mamori`'s dataset
convention that computes offsets rather than trusting hand-written ones.

## Context

An evaluation set for an auditor has to say what the right report is. The
tempting way to build one is to collect real answers, have a person or a model
say which sentences are hallucinated, and score akashi against those labels.

That dataset measures the annotator. RAGTruth — the corpus that defined this
task — reports 78.8% agreement between two annotators at the span level, and
those were trained annotators working to a written taxonomy. A system scored
against labels that two humans agree on four times in five has a ceiling made of
noise, and it is impossible to tell an improvement from a relabelling.

There is a second problem, particular to a deterministic auditor. akashi is
allowed to be *silent* on the subtle cases (ADR-0004). Scored against a corpus
of human-judged hallucinations, it loses points for exactly the cases it
declares it does not handle — which measures its documentation rather than its
implementation.

## Decision

**The evaluation set is generated, the ground truth is constructed rather than
judged, and no label describes an ideal answer.**

One case is a folder: a ContextPackage, a response, and a manifest saying what
was planted. The response is built by taking grounded sentences and applying a
named mutation to a named span, so the truth is known by construction:

```json
{
  "case_id": "ja-0142-mountaineering",
  "language": "ja",
  "package": "package.json",
  "response": "response.txt",
  "plants": [
    {"kind": "digit_drift", "span": [104, 109],
     "was": "2.4kg", "became": "2.6kg",
     "expect_verdict": "contradicted",
     "expect_source_span": {"document_id": "doc_4b1e", "start": 1204, "end": 1209}},
    {"kind": "faithful_paraphrase", "span": [210, 268],
     "expect_verdict": "grounded"},
    {"kind": "derived_value", "span": [300, 305],
     "expect_unchecked_rule": "derived_value"}
  ]
}
```

Two rules make this worth more than a hallucination benchmark:

- **`expect_verdict` is checked, and so is the reason.** A case that akashi
  flags as `floating` when the answer is `contradicted` got the right outcome
  for the wrong reason, and the difference is the whole value of ADR-0004.

- **Half the plants are not hallucinations.** `faithful_paraphrase`,
  `correct_quotation`, `rounded_but_grounded` and `derived_value` are planted
  precisely to catch false positives. An auditor that flags everything scores
  perfectly on a corpus of only lies.

A model runs at authoring time to write the prose. **CI calls nothing.** The
generator, the seed and the model are recorded with the fixtures, and a
`--check-only` mode re-derives every offset from the manifest so that a broken
fixture fails the build rather than failing a correct implementation.

## The planted kinds

| Kind | What it plants | What it exercises |
|---|---|---|
| `digit_drift` | one digit of a grounded number changed | `contradicted`, and that the original is found |
| `unit_swap` | kg→g, 万円→億円, % → percentage points | that the unit is part of the particular |
| `entity_swap` | a proper noun from another document in the same package | resolution is per-particular, not per-package |
| `invented_particular` | a number or name present nowhere | `floating` |
| `omitted_source` | a particular that appears only in `omissions[]` | ADR-0006: still `floating`, and the omission is named |
| `negation_flip` | "does not" ↔ "does" with particulars intact | a declared miss — must appear in `unchecked[]`, not as a pass |
| `cross_document_stitch` | subject from A, predicate from B, both verbatim | the sharpest declared miss (ADR-0004) |
| `faithful_paraphrase` | a true restatement with no shared substring | false positives |
| `derived_value` | a correct sum of two grounded numbers | that derivation is `unchecked`, not `floating` |
| `placeholder_residue` | a `mamori` placeholder left in the answer | ADR-0008: refusal, not a report |

The last four are the ones that keep the project honest, and the two declared
misses are in the corpus *on purpose*: a miss that is measured is a known
quantity, and a miss that is untested is a surprise.

## What is measured

All of it is arithmetic. No grader, no rubric, no model.

| Metric | Definition |
|---|---|
| Fabrication recall | planted `floating`/`contradicted` spans akashi flagged |
| False-positive rate | grounded spans akashi flagged anyway |
| Verdict correctness | flagged spans whose verdict matches `expect_verdict` |
| Source localisation | `contradicted` findings whose reported source span is the labelled one |
| Declared-miss rate | planted misses that appeared in `unchecked[]` rather than as a pass |
| Reproducibility | one case audited twice, one `report_id` |

Reported per language and per kind as well as in aggregate. An aggregate hides
that extraction is strong on Japanese figures and weak on English legal
citations, and those are different problems.

## Consequences

The gate is on the numbers, and the numbers are **floors, not targets**. A gate
set at today's score makes every honest experiment a build failure, and tuning
to reach a threshold is what `mamori`'s ADR-0023 records the cost of.

Anything that changes extraction or segmentation is gated on `akashi eval`. Run
it before and after.

## What it costs

A generated corpus is not a real one. The prose is model-written, the
distribution of hallucinations is chosen rather than observed, and a score on it
is not a score on production traffic.

The honest complement is to also run against a public corpus with human labels —
RAGTruth is the obvious one — and to report that score separately, with its
disagreement ceiling stated. That is planned as a measurement, not as a gate,
and it is where akashi's declared misses will show up as a lower headline number
than a model-based judge's. Publishing that comparison is the point.
