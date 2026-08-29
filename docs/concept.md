# The concept

*This is the conceptual model. What is built lives in `docs/architecture.md`,
which does not exist yet; the plan lives in
[`proposals/0001-the-design.md`](proposals/0001-the-design.md).*

---

## The asymmetry

Everything built for generative AI in the last three years points one way. We
became very good at deciding what to send: retrieval, ranking, reranking, context
windows measured in millions of tokens, and — in this family of projects —
`tsumugi`, which records the exact span of the exact document that went out, and
the ones that did not.

What comes back gets read by a person, or by another model.

That asymmetry is not an oversight. The outbound half is a search problem, and
search has thirty years of technique behind it. The inbound half looks like a
truth problem, and truth is not a computable property of a string. So the field
did the reasonable thing and approximated: decompose the answer into claims with
a model, score each claim with another model, report a number.

The approximation has a property that is fine for a research benchmark and fatal
for a compliance record. **It is not reproducible.** The same answer, the same
sources, the same code, six months apart, and the number moves — because the
judge moved. Nobody can tell you why, and nobody can re-derive what you filed.

## The question akashi asks instead

Not *is this answer true*. That question has no local, deterministic answer, and
a system that claims otherwise is selling a judge with the branding removed.

akashi asks:

> **Which particulars of this answer occur in the text that was actually sent to
> the model, and where?**

That question has an exact answer, computed with string comparison, in
milliseconds, offline, with the same result forever.

It is a smaller question. The whole design is the argument that it is the useful
part of the larger one.

## Why particulars

Read a hallucination that cost someone money and it is almost never a beautiful
lie. It is a digit.

The dosage was 5mg and the answer says 50mg. The article was 第30条 and the
answer says 第13条. The tolerance was ±0.02 and the answer says ±0.2. The
contract was signed in 2019 and the answer says 2016. Everything around the digit
is fluent, well-sourced, and correct — which is exactly why it survives review.

Those are strings. A string is in the source or it is not, and no model is needed
to find out. Meanwhile the failures that genuinely require judgement — an
invented causal link between two true facts, a conclusion quietly reversed — are
the ones where trained human annotators agree only four times in five.

So akashi draws its line where the ground is hard, does that part completely, and
says on every single report exactly where the line was drawn. A partial check
whose boundary is printed on the artefact is worth more than a total check whose
confidence is unexaminable.

## What a verdict means, said carefully

- **grounded** — every particular in this segment occurs in the text that was
  sent. It does **not** mean the sentence is true. A model can quote your
  documents perfectly and reason from them disastrously.
- **floating** — a particular in this segment occurs nowhere in the text that was
  sent. It does **not** mean the sentence is false. It means there is nothing in
  front of the model that supports this number, so the model did not read it — it
  produced it.
- **contradicted** — a particular did not resolve, and one of the same kind, in
  the same place the segment's other particulars point at, did. This is the
  finding worth paying for.
- **unbearing** — the segment carries nothing akashi can check. This is not a
  pass, and it is counted separately, because a check that treats "I looked and
  found nothing wrong" the same as "I did not look" is a check that lies by
  omission.

The vocabulary is chosen to be hard to over-read. There is no `verified`, no
`true`, no `factual` anywhere in akashi's output, and a test enforces that.

## The four projects

```text
[ kiseki ]   turns a personal history into facts, measures and interpretations
     ↓                      — and never lets the three be confused
[ tsumugi ]  selects what bears on the question, keeps the evidence attached,
     ↓        and says what it left out
[ mamori ]   replaces what must not leave the machine, and puts it back after
     ↓
   (out to the model, and an answer comes home)
     ↓
[ akashi ]   separates what the answer took from the evidence
             from what it produced on its own
```

Read as one sentence: **know where it came from, choose what to send, protect
what must not leave, and check what came back.**

Each is a library, each stands alone, each has zero runtime dependencies, and
none imports another except through an optional adapter behind a published
contract. akashi reads a `tsumugi` package without importing `tsumugi`, and can
audit an answer produced by any pipeline that emits a conforming package.

The order matters in one direction only. akashi is last because it is the only
one that gets to see whether the other three were worth the trouble.

## Who this is for

The buyer is the person who has to sign something.

A lawyer attaching an AI-assisted summary to a filing. A hospital reviewing
discharge instructions a model drafted. A patent team where a wrong claim number
is a wrong claim. An auditor who is not allowed to send the documents anywhere,
and is not allowed to accept "the model said so", and needs the check itself to
be inspectable.

For them the deliverable is not a score. It is the sentence:

> *This figure comes from your document, at this offset. This one comes from
> nowhere. And here is everything I did not check.*
