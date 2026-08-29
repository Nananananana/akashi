# akashi — the design, and the order it gets built in

**Status: proposed.** Nothing in this document exists yet. It is the plan, written
before the code, and it stays as written once the code disagrees with it — the
current-state documents are where the code is described. See
[docs/README.md](../README.md) for why that separation is structural.

Decisions already taken are in [docs/adr](../adr/README.md) and are not
re-argued here. This document is about *shape and order*.

---

## 1. What akashi is, in one paragraph

akashi takes a language model's answer and the context package that produced it,
and separates what the answer took from its evidence from what it made up. It
does this deterministically, with no model in the path, at the level of the
things that actually get falsified — numbers, dates, names, dosages, article
numbers, units — and it reports, on the same page as the score, everything it
was not able to check.

The name is 証: proof, evidence, the mark that something was witnessed.

## 2. The problem, stated so that the design follows from it

The upstream half of retrieval-augmented generation is solved infrastructure in
2026. Context windows are enormous, retrieval is commoditised, and `tsumugi`
already produces a package that says exactly which spans of which documents were
sent and which were withheld.

The return path is not. What comes back is prose. The dominant way to check it is
to decompose it into claims with a model and score each claim with another model,
and the field's own numbers say what that costs: judges disagree with each other,
disagree with humans, and — the property that disqualifies it here — **produce a
different answer on the same input next quarter**. A compliance artefact that
changes when nobody changed anything is not a compliance artefact.

So the design question is not "how do we detect hallucinations as well as
possible". It is:

> What can be established about a generated answer with a deterministic,
> reproducible, dependency-free procedure — and can that subset be made large
> enough to be worth buying?

[ADR-0004](../adr/0004-the-particular-is-the-unit-of-verification.md) is the
answer: yes, if the unit is the particular rather than the sentence. The evident
half of the field's own hallucination taxonomy is a string comparison. The subtle
half is not, and akashi says so on every report rather than guessing at it
([ADR-0005](../adr/0005-say-what-could-not-be-checked.md)).

### Where the line falls

Using RAGTruth's four categories as the map:

| | Deterministically checkable | akashi's behaviour |
|---|---|---|
| **Evident conflict** — 2.4kg → 2.6kg, 第30条 → 第13条 | yes | `contradicted`, with the source span |
| **Evident baseless info** — a name or figure present nowhere | yes | `floating` |
| **Subtle conflict** — meaning shifted, particulars intact | no | reported in `unchecked[]` |
| **Subtle baseless info** — inference, subjective addition | no | `unbearing`, counted separately |

The two rows akashi covers are the two that get people sued. The two it does not
are the two where trained human annotators agree only 78.8% of the time.

## 3. What akashi is not

Stated first, because the boundary is the design.

- **Not a truth checker.** A `grounded` particular means the string is in the
  text that was sent. A model can quote a document perfectly and reason from it
  disastrously.
- **Not a retrieval evaluator.** Whether the right documents were selected is
  `tsumugi`'s question, measured by `tsumugi eval`.
- **Not a second implementation of `tsumugi verify`.** That resolves citations a
  model *declared*, on a model that cooperated. akashi audits the whole answer,
  including every sentence the model never mentioned, on a model that did not
  cooperate at all. Section 8 has the seam in full.
- **Not a guard rail.** akashi runs after the answer exists. It does not block,
  rewrite, or re-prompt. A caller may use its report to do any of those.
- **Not a scorer of style, tone, helpfulness or safety.**

## 4. Architecture

The layering is `mamori`'s and `tsumugi`'s, unchanged, because it is asserted by
a test in both and both were right to.

```text
interfaces ──> application ──> domain
                    │              ▲
                    │              │
                    └──> ports <───┴── infrastructure
```

| Layer | May import |
|---|---|
| `domain/` | **stdlib only** — and never `tsumugi`, `kiseki` or `mamori` |
| `errors.py` | nothing |
| `ports/` | `domain`, `errors` |
| `application/` | `domain`, `ports`, `errors` |
| `infrastructure/` | `domain`, `ports`, `errors` |
| `config.py` | everything above |
| `interfaces/` | everything above |

Enforced twice: `tests/test_architecture.py` parses every module and asserts the
table, and `import-linter` asserts the direction plus four forbidden-import
contracts. A diagram that stops matching the code turns the build red rather
than quietly becoming fiction.

```text
src/akashi/
├── domain/
│   ├── text.py            # normalization with offsets preserved
│   ├── segment.py         # the answer, cut into segments that tile it
│   ├── particular.py      # what a load-bearing token is, and its kinds
│   ├── extraction.py      # finding particulars — rules are data
│   ├── matching.py        # strict resolution, NFKC + casefold + whitespace
│   ├── evidence.py        # the sent text as a searchable closed world
│   ├── verdict.py         # grounded / floating / contradicted / unbearing
│   ├── coverage.py        # the denominators, and unchecked[]
│   ├── report.py          # AuditReport as values
│   └── hashing.py         # report_id over exactly the inputs
├── ports/
│   ├── restorer.py        # ADR-0008 — a protected answer needs one
│   └── renderer.py
├── application/
│   ├── audit.py           # the one use case
│   └── recheck.py         # re-derive a report from its own inputs
├── infrastructure/
│   ├── packages/          # ContextPackage reader — JSON, no import (ADR-0007)
│   ├── languages/         # en / ja / zh packs: segmentation + extraction rules
│   ├── rendering/         # JSON, text, and the human-readable certificate
│   └── adapters/
│       └── mamori.py      # optional; the only module that knows it exists
├── evaluation/            # the corpus, the metrics, the floors
└── interfaces/
    ├── cli/
    └── mcp/
```

Two notes on that tree.

`domain/evidence.py` is where the closed world of
[ADR-0006](../adr/0006-audit-against-what-was-sent.md) lives: `items[]` becomes
a normalized, offset-preserving searchable form, built once per audit, and
`omissions[]` becomes a *separate* index that can be searched but never grounds
anything. Keeping them as two objects rather than one with a flag is what makes
"grounded in something that was deliberately withheld" impossible to write by
accident.

`domain/extraction.py` holds the algorithm; `infrastructure/languages/` holds the
rules it runs. That split is `mamori`'s ADR-0008 and it is what makes a fourth
language a data change.

## 5. The core algorithm

Six stages. Every one is a pure function of its inputs.

1. **Admit.** Read the package. Check `contract` and refuse an unknown version.
   Check `provenance.protection` and the answer for placeholder residue; refuse
   or restore ([ADR-0008](../adr/0008-restore-before-you-audit.md)). Nothing
   past this point has to think about redaction.

2. **Build the world.** Normalize every `items[].text` into a search form that
   keeps a map back to original offsets, and remember which item and which
   anchor each came from. Do the same for `omissions[]`, into a separate index
   that cannot ground.

3. **Segment.** Cut the answer into segments that tile it exactly, by script,
   with offsets ([ADR-0009](../adr/0009-segment-by-script-and-record-the-segmenter.md)).
   Mark non-prose structure as itself.

4. **Extract.** Find the particulars in each segment. Each carries its kind, its
   span in the answer, and its normalized form. A segment with none is
   `unbearing` and stops here.

5. **Resolve.** For each particular, find every occurrence in the world. The
   comparison is exact after NFKC, case-folding and whitespace collapse, and
   nothing else. Zero occurrences and it is `floating`; one or more and it is
   `grounded`, with every location reported — ambiguity is information, not an
   error.

6. **Explain a miss.** For each `floating` particular, look for a *sibling*: a
   particular of the same kind, in the same neighbourhood of the same source
   item that the segment's grounded particulars pointed at. A sibling turns
   `floating` into `contradicted` and attaches what the source actually says.
   Also check the omission index, and the derivation heuristic, so that
   `omitted_source` and `derived_value` are named rather than lumped in.

Stage 6 is where the product is. Stages 1–5 tell a user that something is wrong;
stage 6 tells them what it should have said and where to look. It is also the
stage most able to be wrong, so it is the one with the tightest evaluation gate
and the one whose confidence rules are written down as data.

### Normalization tolerance, stated once

NFKC, case-folded, runs of whitespace collapsed to one space. Full-width `２.４`
and half-width `2.4` are the same particular; `2.4` and `2.40` are not; `2.4kg`
and `2.4 kg` are, because whitespace collapses; `2.4kg` and `2400g` are not, and
ADR-0004's cost section owns that.

Unit-aware comparison is deliberately **not** in v0.1. It is a real feature and
it is also the first step onto a slope that ends in fuzzy matching, so it gets
its own ADR, its own trap kind, and a measurement before it ships.

## 6. The report

`akashi.audit-report/1`, a JSON document
([ADR-0002](../adr/0002-the-audit-report-is-a-document.md)). Sketch, not schema —
the schema is written with the code that produces it.

```json
{
  "contract": "akashi.audit-report/1",
  "report_id": "sha256:...",
  "created_at": "2026-08-30T14:22:10+09:00",

  "audited": {
    "package_id": "sha256:9f2c...",
    "response_hash": "sha256:...",
    "response_length": 1840,
    "segmenter": "akashi.segmenter/ja@1",
    "extractor": "akashi.extractor/ja@1",
    "akashi_version": "0.1.0"
  },

  "segments": [
    {
      "segment_id": "seg_004",
      "span": [312, 361],
      "text": "テントは 2.6kg で、前回より 300g 軽い。",
      "verdict": "contradicted",
      "particulars": [
        {"kind": "mass", "text": "2.6kg", "span": [317, 322],
         "status": "floating",
         "contradicts": {
           "found": "2.4kg",
           "item_id": "itm_01",
           "anchor": {"document_id": "doc_4b1e",
                      "source_path": "notes/design/gear.md",
                      "start": 1204, "end": 1209},
           "why": "same kind, same sentence of the same item as the segment's grounded particulars"
         }},
        {"kind": "mass", "text": "300g", "span": [334, 338],
         "status": "grounded",
         "locations": [{"item_id": "itm_01",
                        "anchor": {"document_id": "doc_4b1e", "start": 1240, "end": 1244}}]}
      ]
    }
  ],

  "unchecked": [
    {"span": [402, 455], "rule": "no_particulars",
     "reason": "the segment asserts a relation with no load-bearing token"},
    {"span": [520, 528], "rule": "derived_value",
     "reason": "4.8 is the sum of two grounded values; akashi does not check arithmetic"}
  ],

  "coverage": {
    "segments": 22, "bearing": 17, "unbearing": 5,
    "particulars": 41, "checked": 39, "kinds_not_extracted": ["legal_citation:en"]
  },

  "findings": {"grounded": 34, "floating": 4, "contradicted": 1},

  "limits": [
    "A grounded particular is a statement about strings, not about truth.",
    "A sentence assembled from two documents, each quoted correctly, is reported grounded.",
    "A meaning reversed without changing a particular is not detected."
  ],

  "provenance": {"restored_by": null, "protection": null}
}
```

Three things about it are non-negotiable and are why it looks like this.

`limits` is in the document, not in the documentation. The artefact travels; the
documentation does not.

`coverage` publishes the denominator. `findings` alone would let a reader compute
a ratio against the wrong total, and they would.

`contradicts.why` states the rule that produced the strongest claim on the page.
A finding that cannot say why it is a finding is a finding nobody can appeal.

The **certificate** rendering — the human-readable artefact from the commercial
case — is the same document with the answer printed, every particular underlined
in place, and the unchecked account at the top rather than the bottom. Single
HTML file, no scripts, no fonts, no network, following `kiseki`'s view.

## 7. The command line

```bash
akashi audit --package pkg.json --response answer.txt          # human-readable
akashi audit --package pkg.json --response answer.txt --json   # the document
akashi recheck report.json --package pkg.json                  # re-derive, compare ids
akashi certificate report.json --out audit.html                # the artefact
akashi eval --tier ci                                          # the floors
akashi explain report.json --segment seg_004                   # one finding, in full
akashi doctor                                                  # what is installed, what is missing
```

`recheck` is the command the whole design is for. It takes a report someone else
produced, re-derives it from the inputs the report names, and reports whether the
`report_id` matches. It is the difference between an audit and an opinion.

## 8. The seams

```text
[ kiseki ]   personal context, as facts / measures / interpretations
     ↓
[ tsumugi ]  selection ➔ a ContextPackage: what was sent, what was withheld
     ↓
[ mamori ]   pseudonymization ➔ out to the model, and restoration on the way back
     ↓  (the answer)
[ akashi ]   ➔ which particulars of the answer are traceable, and which are floating
```

### With `tsumugi`

akashi consumes `tsumugi.context-package/1` as JSON and imports nothing
([ADR-0007](../adr/0007-read-the-producer-through-its-contract.md)). The package
is already exactly the right shape: `items[]` with anchors and hashes is the
closed world; `omissions[]` with rules is what makes "the model reproduced
something we withheld" a detectable event, which no other system in this
category can see at all.

**The seam with `tsumugi verify`, precisely.** `tsumugi verify` answers *did the
citation the model declared resolve?* — its input is a structured claim list, and
a model that declines to cite is invisible to it. akashi answers *of everything
this answer asserts, which particulars are traceable?* — its input is prose, and
nothing the model chose to omit can hide from it. They are complementary and they
overlap in one place: an answer that both cites well and is audited will have its
quotations resolved twice by two implementations of the same strict matcher.
That duplication is accepted rather than factored out, because factoring it out
means one of the two projects importing the other, and both zero-dependency
promises are worth more than the shared function.

Anything akashi turns out to need from the package that is not in the contract is
negotiated as a contract change, across the seam, and never as an import.

### With `mamori`

[ADR-0008](../adr/0008-restore-before-you-audit.md). Restore first or refuse.
The adapter is optional and isolated; a caller who restores their own text needs
nothing from it.

`mamori` also supplies three things akashi takes as method rather than code: the
language-pack shape, the dataset convention that computes offsets rather than
trusting hand-written ones, and ADR-0022's finding that a model reports values
and never offsets — which is the same finding as ADR-0004, arrived at from the
other end.

### With `kiseki`

None, directly. `kiseki`'s `fact` / `measure` / `interpretation` layer survives
into the package, and akashi reads it: a particular grounded in an item whose
`provenance.layer` is `interpretation` is grounded **in an interpretation**, and
the report says so rather than flattening it. An audit that launders an
interpretation into a fact would undo the one thing `kiseki` is most careful
about.

## 9. The order it gets built in

Each milestone is shippable, is gated by the checks that exist when it ships, and
ends with something that can be demonstrated. One issue, one PR, squash merge.

### v0.1 — the spine

*The question it answers: given a package and an answer, which numbers are not
in the sources?*

- `domain/`: text normalization with offsets, segmentation for `en`/`ja`/`zh`,
  particular extraction for the numeric kinds, strict matching, the closed world,
  verdicts, coverage.
- The ContextPackage reader: JSON, contract-gated, fail-closed.
- `akashi audit` and `--json`.
- `tests/test_architecture.py`, the five `import-linter` contracts, the
  zero-dependency CI job, `mypy --strict`.
- Property tests for the two invariants that everything else rests on: segments
  tile the answer exactly, and `answer[p.start:p.end] == p.text` for every
  particular.

Deliberately **not** in v0.1: `contradicted`. Stage 6 needs the evaluation corpus
to be built responsibly, and shipping the strongest claim on the page before
there is anything to measure it against is how a tuned-to-a-threshold detector
happens. v0.1 reports `floating` and says it does not yet explain misses.

### v0.2 — the report becomes a contract

- `akashi.audit-report/1`, `schemas/audit-report-1.json`, the conformance suite.
- `report_id` over exactly the inputs, and the reproducibility property test.
- `akashi recheck`.
- **The freeze condition:** the contract is frozen once a second program has
  produced and consumed a report — not on a date. The MCP surface in v0.5 is the
  likely second program; if something else gets there first, that counts.

### v0.3 — the corpus, and the floors

- The generator, the ten planted kinds, the manifest format,
  `--check-only` re-derivation of every offset.
- `akashi eval`, the six metrics, per language and per kind.
- Floors in CI, set deliberately below the measured scores.
- `docs/measurements.md`: extraction recall per kind per language, segmenter
  disagreement against hand-segmented fixtures, and the residual each number
  does not cover.

This is the milestone that decides whether the thesis is true. If extraction
recall on Japanese figures is 70%, ADR-0004 is not wrong but the product is not
sellable, and the roadmap after this point gets rewritten from the measurement
rather than from the plan. `tsumugi`'s proposal 0002 exists because that happened
there, and it is expected to happen here.

### v0.4 — explaining a miss

- Stage 6: siblings, `contradicted`, source localisation, `omitted_source`,
  `derived_value`.
- Gated on v0.3's corpus, with the false-positive rate as the number that
  governs. A `contradicted` finding that is wrong is worse than no finding, and
  the corpus's `faithful_paraphrase` and `derived_value` plants exist to price
  that.
- `akashi explain`.

### v0.5 — the artefact and the surfaces

- `akashi certificate`: the single-file HTML rendering, no scripts, no network.
- The MCP server, on the standard library, following `tsumugi`'s ADR-0012.
- The `mamori` adapter and the seam test against the real redactor.
- `akashi doctor`.

### v0.6 — the honest comparison

- A run against a public human-labelled corpus, reported separately from the
  generated one, with the annotator-agreement ceiling stated.
- The comparison against a model-based judge on the same inputs, with the
  reproducibility difference measured rather than asserted: run both twice.

Publishing a benchmark on which akashi loses to a judge, next to a
reproducibility measurement on which the judge cannot compete, is the strongest
honest claim this project can make. It is a milestone rather than a footnote.

### After that, in rough order of appetite

Unit-aware comparison, behind its own ADR and its own traps. Arithmetic
derivation checking, which converts the largest false-positive class into a real
check. Cross-document stitch detection as a *flag* rather than a verdict — the
signal is that a segment's grounded particulars point at two items that share no
anchor, and it is a heuristic, so it lands as a warning with a measured
precision or it does not land. A fourth language. Streaming audit, so a long
answer can be checked as it arrives.

## 10. What would falsify this design

Written down now, while it is still cheap to be wrong.

- **Extraction recall is low on real answers.** If akashi finds four particulars
  in a paragraph that contains nine, the coverage number is honest and the
  product is not useful. Measured in v0.3.
- **`unbearing` dominates.** If most sentences of a real answer carry no
  particular, akashi is silent about most of the answer, and the interesting
  question becomes whether the *distribution* of unbearing sentences is where the
  risk is. Measured in v0.3, and it changes the roadmap if it is bad.
- **`contradicted` is too eager.** If the sibling rule fires on paraphrases, the
  strongest feature is a liability. Priced in v0.4 against the corpus's
  deliberate non-hallucinations.
- **The closed world is too strict for real callers.** If users routinely audit
  against packages that do not match the answer, every report is noise. The
  `package_id` check makes this loud; if it turns out to be common, the fix is in
  the pipeline, not in loosening ADR-0006.

Each of these has a measurement attached and a milestone it is measured in. A
design whose falsification conditions are not written down is a design that will
be defended instead of tested.
