# What building it taught, and the roadmap that follows

**Status: proposed.** This revises the roadmap in
[`0001-the-design.md`](0001-the-design.md), which stays exactly as it was
written. Nothing here is built. A proposal is never evidence that something
exists.

`0001` was written before any code. This is written after v0.1 and v0.3, with
the measurements in [`../measurements.md`](../measurements.md) in hand, and it
exists because three things changed: the design was wrong in three places, the
numbers said something the plan did not anticipate, and the world outside the
repository moved.

---

## 1. What got built, and what it cost

v0.1 and v0.3. v0.2 was deliberately skipped past — freezing a report contract
around a method whose extraction recall was unmeasured would have been fixing a
shape before knowing it works, and
[ADR-0002](../adr/0002-the-audit-report-is-a-document.md) does not object
because the freeze waits for a second consumer rather than for a date.

`akashi audit` reads a ContextPackage and an answer and reports which
particulars of the answer are in the text that was sent. `akashi eval` runs 42
generated cases and nine hand-marked answers against floors. Zero runtime
dependencies, no model anywhere, six layering contracts.

The estimate in `0001` was that v0.1 was "the spine" and the rest followed. That
held. What did not hold is *what the spine turned out to need*, which is the
next section.

---

## 2. Four places the design was wrong

Each is an ADR, each was found by writing the code rather than by thinking
harder about it, and each is the reason those ADRs exist rather than a
correction to `0001` in place.

**[ADR-0011](../adr/0011-the-script-is-decided-at-the-boundary.md) — the script
is decided at the boundary.** `0001` inherited ADR-0009's "rules selected per
script", which reads as: detect the language, choose the pack. It does not work.
In `テントは軽い。The tent is light. 重さは 2.4kg。` the dominant script is
Japanese, the Japanese pack does not claim `.`, and the English sentence never
ends — so one verdict covers two sentences and one floating particular condemns
a grounded one. Per-paragraph detection moves the problem; per-sentence
detection is circular. A pack claims *characters*, and every pack is always
loaded.

**[ADR-0012](../adr/0012-an-omission-is-a-receipt-not-a-source.md) — an
omission is a receipt.** `0001`'s stage 6 searched an omission index, and
[ADR-0006](../adr/0006-audit-against-what-was-sent.md) promised the report would
say which omission a particular matched. There is nothing to match against: a
ContextPackage omission carries an anchor and a reason and **not the omitted
text**, deliberately. This was found by building the index and looking for the
field to put in it, which is a good argument for building a seam before writing
about it.

**[ADR-0013](../adr/0013-a-restoration-akashi-did-not-watch-is-a-claim.md) — the
absence of a placeholder is not evidence of restoration.** `0001` assumed a
caller who had already restored their text hands akashi plain text and needs
nothing. `mamori` can substitute *surrogates* — plausible fake values — so
restored text and unrestored text are indistinguishable, and the inference is
false in the dangerous direction. The caller may assert; the assertion is
recorded as an assertion.

**[ADR-0015](../adr/0015-the-digits-are-the-evidence.md) — the digits are the
evidence.** `0001`'s stage 6 said a floating particular could be explained by
"one of the same kind, where the others point". The first run reported that an
answer's `2.6kg` contradicted the source's **`300g`**: both were quantities, both
were in the sentence the segment's grounded particular landed in, and there was
exactly one candidate. Every clause was satisfied and the output was nonsense,
because *same kind and nearby* is not a relation between two values but a
coincidence of layout. The repaired rule was then measured and was right about
half the time, and what shipped is roughly a third of what was specified.

The first three make a pattern: **every one was a claim about somebody else's
contract or somebody else's behaviour**, each survived being reasoned about and
died on contact, and the lesson was to build the seam early rather than specify
it more carefully.

**The fourth breaks that pattern and is the more uncomfortable one.** It was a
claim about akashi's own output, in the part of the design that was thought
about hardest, and it did not die on contact with anyone else's system — it died
on contact with a number. Building the seam early would not have caught it.
Only the corpus did, which is the argument for having built the corpus in v0.3
rather than v0.6.

---

## 3. What the measurement changed

The numbers are in [`../measurements.md`](../measurements.md). Four of them
change what should be built next.

**Extraction recall is 100% over the kinds akashi claims and 91% over
everything a person marked, and the entire gap is `proper_noun`.** `0001` listed
proper nouns as a particular kind and then left them unbuilt as an aside. They
are now the *whole* coverage gap, and closing them is the single highest-value
extractor change available. Crucially, the structural cases are evidence rather
than a guess: a token in front of `株式会社`, `Inc.`, `氏`, `医師`, `Dr.` is a
name because of what follows it, not because a model thinks so. That fits
ADR-0001 and ADR-0003 exactly, and it should have been in v0.1.

**`unbearing` is 35% on realistic answers, and most of it is the model
hedging.** `0001` §10 named this as a falsification condition and it did not
fire. What it did do is reframe the number: twenty-two of twenty-eight
unbearing segments were prose, and most were *"the document does not say"*
rather than a claim akashi could not check. That is a better result than the
bare figure, and it means the reporting should keep the two apart where it can.

**A unit the extractor does not know makes a unit swap undetectable.** Two such
gaps were found and closed (`℉`, `percentage points`), and the general fact is
not fixable by lengthening a list. But it suggests a check that needs no list at
all: if a number grounds and the token *immediately after it in the answer*
differs from the token immediately after the matched number *in the source*,
something was swapped. That is deterministic, table-free, and it is a new idea
the measurement produced.

**The corpus is 177 prose segments and nothing else.** It does not exercise the
structure pass — tables, list items, headings — at all. The nine marked answers
are the only material that does, and they are nine.

---

## 4. What changed outside the repository

`0001` argued the commercial case from first principles. Since it was written,
the case stopped being an argument.

**The EU AI Act's record-keeping obligations for high-risk systems became
enforceable on 2 August 2026** — four weeks ago. Article 12 requires high-risk
systems to automatically record events so that the functioning of the system can
be reconstructed, and Article 18 requires those records to be kept. Law,
medicine and employment are named high-risk uses.

**Japan's AI事業者ガイドライン reached version 1.2 on 31 March 2026**, and the
reported direction of the revision is from principle to practice: the core of
transparency and accountability is *logs and documentation of the inputs, the
outputs, and the grounds for the judgement*.

akashi does not make anyone compliant with either, and this document should not
be read as saying it does. What it produces is one artefact of the kind both
regimes ask for: a record, reconstructable from its inputs, of which parts of a
generated answer were traceable to the material the system was given. That is a
narrower claim than a compliance product and it is one akashi can actually
stand behind — and `akashi recheck`, which was a nice-to-have in `0001`, is the
feature that makes it worth anything, because a record nobody can re-derive is
a record on trust.

**in-toto attestations, DSSE and Sigstore are the shape this artefact should
take.** An in-toto Statement names a *subject* by digest and carries a
*predicate* about it, wrapped in a signing envelope. akashi's report is exactly
a predicate about a subject: the answer, by its hash. Emitting one means the
report can be signed and verified with `cosign` — tooling that exists, that
security teams already run, and that akashi does not have to write.

**And akashi takes no crypto dependency to do it.** The Statement is a JSON
shape; the signing is the caller's, with their own keys and their own trust
root. That preserves ADR-0001 exactly and gets the interoperability for free.
It is a much better answer than inventing a signature format, and the fact that
it needs no code in akashi beyond a second serializer is the strongest argument
for it.

C2PA 2.3 was considered and is the wrong fit: it is media-centric, its trust
model is about assets that travel with embedded metadata, and a JSON audit
record is not that. It is worth revisiting if C2PA's text story matures.

**The field moved towards causal faithfulness** — from "is this citation
attachable" to "did the cited passage actually influence generation", measured
from model internals. That is a strictly stronger form of attribution than
akashi's and akashi will never do it: it requires the model, which
[ADR-0003](../adr/0003-an-audit-is-reproducible.md) refuses. Worth naming in
the README as a thing akashi is not, because a reader who wants it should not
find out three months in.

---

## 5. The revised order

Changed from `0001`: proper nouns move from "later, in rough order of appetite"
into v0.4; the in-toto envelope joins v0.2; the certificate is promoted because
the `Traced` section turned out to be the product rather than a nicety; and
latency joins the measurements because production RAG deployments run to
SLAs and akashi has never been timed.

### v0.2 — the report becomes a contract

- `akashi.audit-report/1`, `schemas/audit-report-1.json`, the conformance suite.
- `report_id` over exactly the inputs, and the reproducibility property test.
- `akashi recheck`: re-derive a report from the inputs it names and compare ids.
  **Promoted from useful to load-bearing** by section 4.
- `--attestation`: the same report as an in-toto Statement, unsigned. akashi
  emits, the caller signs.
- The freeze condition is unchanged and is not a date: a second program has to
  have produced and consumed a report.

### v0.4 — explaining a miss, and the coverage gap

Two things that were separate in `0001` and belong together, because both are
about making a finding say more.

- Stage 6: siblings, `contradicted`, source localisation. **Shipped, narrowed
  to about a third of what was specified.** The false-positive rate governed,
  exactly as this said it would, and it is what cut the feature down: verdict
  correctness 35% -> 59%, source localisation 0 of 33 -> 12 of 33, source
  misdirection 0 of 12. akashi explains a swapped unit and refuses to explain a
  drifted digit ([ADR-0015](../adr/0015-the-digits-are-the-evidence.md)).
- **The unit check that needs no unit table**: a grounded number whose
  following token differs from the source's following token.
- **Structural proper nouns**: a token in front of an organisational or
  honorific suffix, in three languages. Evidence, not a guess. **Shipped**:
  extraction recall over everything marked 91% -> 95%, unbearing 35% -> 30%,
  precision held at 100%. It should have been in v0.1.
- `akashi explain`.

### v0.5 — the artefact and the seams

- `akashi certificate`: the single-file HTML rendering. Promoted: the `Traced`
  section is what a signer signs.
- The `mamori` adapter and the seam test against the real redactor.
- The `tsumugi` seam test: build a package with the reference producer and audit
  against it. **Section 2's lesson says do this earlier if anything else slips.**
- The MCP server.
- `akashi doctor`.

### v0.6 — the honest comparison, and the clock

- A run against a public human-labelled corpus, reported separately, with the
  annotator-agreement ceiling stated.
- The comparison against a model-based judge on the same inputs, with the
  reproducibility difference measured rather than asserted: run both twice.
- **Latency, at the lengths people send.** Never measured. `mamori`'s ADR-0025
  is the pattern.
- A hand-segmented reference set, so ADR-0009's disagreement rate stops being
  owed.
- The corpus grows to exercise the structure pass.

### After that

Unit-aware comparison behind its own ADR. Arithmetic derivation checking, which
converts the largest acknowledged false-positive class into a real check.
Cross-document stitch detection as a *flag* with a measured precision, never a
verdict. A fourth language. Streaming audit, so a long answer can be checked as
it arrives — the field's own numbers put end-to-end RAG latency at four to six
seconds and streaming is how that is hidden.

### What moved, and why

| | `0001` | Now | Why |
|---|---|---|---|
| `recheck` | v0.2, useful | v0.2, load-bearing | Article 12 is in force |
| in-toto envelope | absent | v0.2 | the artefact has a standard shape and akashi needs no dependency to emit it |
| proper nouns | "appetite" | v0.4 | they are the entire coverage gap |
| unit table-free check | absent | v0.4 | the measurement produced the idea |
| certificate | v0.5 | v0.5, promoted | `Traced` is the product |
| latency | absent | v0.6 | never measured, and deployments run to SLAs |
| `omitted_source` | corpus plant | withdrawn | ADR-0012 |

---

## 6. What is now explicitly out of scope

Written down because a boundary that is only implied gets crossed.

- **Causal faithfulness.** Whether the cited passage actually influenced
  generation requires the model. ADR-0003 refuses it, permanently.
- **Any model at audit time**, including a small local one, including behind a
  flag. There is no flag.
- **Reading the corpus.** akashi audits against what was sent (ADR-0006). An
  auditor that read the corpus would be auditing a different world from the one
  the answer was produced in.
- **Compliance as a product claim.** akashi produces one artefact of a kind two
  regimes ask for. It does not certify anything and the README must not imply it
  does.
- **Signing.** akashi emits a signable statement. Keys, trust roots and
  revocation are the caller's, and taking a crypto dependency would cost
  ADR-0001 for something `cosign` already does better.

---

## 7. What would still falsify this

`0001` §10 listed four conditions. Two were checked and did not fire —
extraction recall is not low, and `unbearing` is a third rather than most. **One
fired.** One remains, and one is new.

- **`contradicted` is too eager. This fired, and it is the most useful thing
  that has happened to this project.** The sibling rule did not fire on
  paraphrases — the `faithful_paraphrase` and `grounded` plants stayed at zero
  false positives throughout — but it fired on the wrong *source*, which `0001`
  had not thought to be afraid of. Naming a parent for a value whose digits had
  drifted was right 47% of the time, and a finding that sends a reader to a
  correct line and tells them their answer corrupted it is worse than saying
  nothing.

  The response was to ship a third of the feature and publish the other
  two-thirds as a measurement, which is what the condition was written to
  produce. What it changes for the rest of the roadmap: **a feature is now
  priced before its scope is fixed, not after.** v0.4's unit check below is the
  first to be planned that way, and it may not ship either.
- **The closed world is too strict for real callers.** If users routinely audit
  against packages that do not match the answer, every report is noise.
  Unchanged from `0001`.
- **New: the corpus measures its own author.** Every number in
  `measurements.md` comes from material written by the same model that wrote
  the extractor. The mitigations are real and they are not an answer. If the
  v0.6 run against a public human-labelled corpus scores far below the numbers
  here, the honest response is to say so in a third proposal and revise the
  roadmap from that measurement — which is what this document is for.
