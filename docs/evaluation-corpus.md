# The evaluation corpus

**Status: current.** It exists, it is committed, and `akashi eval` runs it. The
decision behind it is
[ADR-0010](adr/0010-label-the-response-not-the-ideal-answer.md); what it
currently scores is [`measurements.md`](measurements.md).

*The one-line version: **the prose is authored, the labels are computed, and
half the plants are not hallucinations.** Every metric is arithmetic.*

---

## Two sets, measuring two different things

| | What it is | What it measures |
|---|---|---|
| `tests/cases/` | 42 generated cases, 177 planted spans | the **detector**: does akashi catch what it says it catches, and stay quiet where it says it will |
| `tests/marked/` | 9 realistic answers, 96 hand-marked particulars | the **extractor**: how much of an answer nobody wrote for akashi does akashi see |

The first is generated from authored material and its prose was written *for*
akashi. A high score there says the method works on material designed for the
method — which is worth knowing and is not the same as working. The second is
the harder one and it is where
[proposals/0001 §10](proposals/0001-the-design.md)'s falsification conditions
are checked.

---

## A case

```text
tests/cases/ja-contract-01/
├── case.json        # the manifest: what was planted, and where
├── package.json     # a real tsumugi.context-package/1
└── response.txt     # the answer to audit
```

Facts are marked in the source, **tightly** — a fact is exactly the particular,
not the clause around it — and the loader strips the markup and computes the
offsets.

```markdown
{{F:cap_clause}}第12条{{/F}}に定める賠償責任の上限額は{{F:cap_amount}}1,200万円{{/F}}とする。
```

A plant then carries **three booleans, and they are three questions**:

| | asks |
|---|---|
| `expect_detected` | should akashi flag this span? |
| `is_hallucination` | is the span actually wrong? |
| `declared_miss` | is akashi's silence here a stated limit rather than a defect? |

Most plants set the first two together. **The ones that do not are the reason
this is worth more than a hallucination benchmark.**

```json
{
  "kind": "digit_drift",
  "span": [8, 15],
  "text": "1,300万円",
  "was": "1,200万円",
  "source": {"document_id": "doc_msa_ja", "span": [98, 105]},
  "expect_detected": true,
  "is_hallucination": true,
  "declared_miss": false,
  "expect_verdict": "contradicted"
}
```

`expect_verdict` records what akashi should **ultimately** say. A digit drift is
`contradicted`; v0.1 reports `floating`. That gap is what verdict correctness
measures, and it is a number that should rise when v0.4 ships rather than a
failure to fix now.

The manifest carries each plant's `text` **and** its span, and the loader
refuses a case where they disagree. Deriving the text from the span would make
the check vacuous: an edited response would move every plant onto different
words and the manifest would agree with itself all the way down.

---

## The plants

| Kind | Count | Detected? | A hallucination? | Declared miss? |
|---|---:|---|---|---|
| `grounded` | 36 | no | no | — |
| `digit_drift` | 27 | yes | yes | no |
| `unit_swap` | 18 | yes | yes | no |
| `invented_particular` | 18 | yes | yes | no |
| `entity_swap` | 18 | no | **yes** | **yes** |
| `negation_flip` | 18 | no | **yes** | **yes** |
| `faithful_paraphrase` | 18 | no | no | — |
| `cross_document_stitch` | 9 | no | **yes** | **yes** |
| `derived_value` | 9 | **yes** | **no** | — |
| `placeholder_residue` | 6 | refusal | — | — |

Three of those rows carry the weight.

**`faithful_paraphrase` and `grounded` are controls.** They are not
hallucinations and flagging one is a false positive. An auditor that flags
everything scores perfectly on a corpus of only lies, and 54 of the 177 plants
exist to stop that.

**`entity_swap`, `negation_flip` and `cross_document_stitch` are declared
misses.** They *are* hallucinations and ADR-0004 says akashi cannot see them.
Passing them is correct behaviour, and the count is published rather than
improved. "akashi passed 42 of 42" is the most useful line a buyer will read,
and it exists only because the corpus deliberately plants things akashi cannot
catch.

**`derived_value` is an acknowledged false positive.** A correct sum of two
grounded numbers is in neither source, so it floats. That is on
`STANDING_LIMITS` on every report, and it gets its own number rather than
being hidden in the false-positive rate.

`omitted_source` is **not** a plant kind.
[ADR-0012](adr/0012-an-omission-is-a-receipt-not-a-source.md) withdrew it: an
omission carries no text to plant against, so a plant nothing can detect would
measure nothing. A test asserts its absence.

---

## Generation

```bash
python tools/generate_cases.py --seed 20260830 --out tests/cases
python tools/generate_cases.py --check-only        # runs in CI on every push
```

**A model ran at authoring time, once, to write the prose. CI calls nothing.**
The prose lives in `src/akashi/evaluation/genres/`, committed and readable, in
three languages across four genres — a contract, a clinical note, an
engineering specification, and a protected case that must be refused rather
than reported. The genres are chosen for where a wrong number costs money.

**The seed shuffles, it does not invent.** Every sentence a genre carries is
used exactly once across that genre's cases, so coverage is a property of the
data rather than of the draw: a corpus cannot lose a plant kind to an unlucky
seed. What the seed decides is which sentences sit together and in what order,
which is worth varying because a segment's neighbours are what a segmenter sees.
A test runs the generator under three values of `PYTHONHASHSEED` and asserts one
answer, because `hash()` is salted per process.

`--check-only` runs in CI, and that is not belt-and-braces. **A generated case
that is broken fails a *correct* implementation**, so the oracle has to be
checked as often as the code it is checking. Without it a bad fixture looks
exactly like a regression, and somebody spends an afternoon fixing the wrong
thing.

---

## The hand-marked answers

Nine realistic answers, in `tests/marked/`, with **every** particular marked.
The marking rule is ADR-0004's definition applied by hand: a particular is
marked where a person reading the sentence would say a wrong value there
changes what it means.

**So proper nouns are marked, and akashi extracts none of them.** That is why
recall is reported twice — over everything marked (coverage) and over the kinds
akashi claims (whether it does what it says). Publishing only the second would
score akashi against a boundary it drew for itself; publishing only the first
would count a declared limit as a defect.

---

## The splits

`train` is 30 cases and `held_out` is 12 — one per genre per language. Nothing
reads `held_out` unless it is asked for, because **a held-out split that
anything touches by default is a training split with a different name.**

`--tier ci` currently selects every case, because the whole corpus audits in
about a second and a tier that excluded nothing useful would be a distinction
pretending to be an optimisation. The field is there for the corpus this one is
a tenth the size of.

---

## What this cannot tell you

- **The generated corpus is generated.** The prose was authored for it, the mix
  of hallucinations was chosen rather than observed, and a score on it is not a
  score on production traffic.
- **Nine marked answers is a sample, not a distribution**, written by one model
  in one sitting about three genres.
- **The person who marked them wrote the extractor.** That is exactly the bias
  ADR-0010 warns about for a labelled corpus. The mitigations are the marking
  rule, the fact that proper nouns are marked at all, and that every marking is
  visible in the files so anyone can disagree with one. It is a mitigation and
  not an answer.
- **A public human-labelled corpus would say something this cannot.** RAGTruth
  is the obvious one, its span-level annotator agreement is 78.8%, and running
  against it is v0.6 — reported separately, never as a gate, and expected to
  show akashi's declared misses as a lower headline number than a model-based
  judge's. Publishing that comparison is the point.
