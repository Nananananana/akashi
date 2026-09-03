# 17. A judge annotates an audit; it does not make one

**Status:** accepted
**Amends:** [ADR-0003](0003-an-audit-is-reproducible.md)

ADR-0003 says: *"No model runs at audit time. Ever. This is a stronger rule than
'the default is deterministic'. There is no flag that turns a model on."*

There is now a flag. This is what it does and what it may not do.

## Context

ADR-0003's reasoning was right and is unchanged:

> Run it twice and the verdicts move. Run it next quarter, after the judge model
> has been updated, and they move again — on a report that has already been
> filed. An audit trail that changes when nobody changed anything is not an
> audit trail.

And the circularity was real: checking a model's tendency to assert what it
cannot support, with a model, inherits the failure being measured.

What ADR-0003 got wrong is the step from *"a verdict must not come from a
model"* to *"nothing a model says may appear on the artefact"*. Those are
different sentences, and only the first follows from the argument.

**The cost of the second one is measured, not hypothetical.** akashi decides by
comparing strings, so a claim the answer *paraphrased* out of the evidence is
reported `floating` — correctly, and uselessly. `docs/measurements.md` records
`verdict correctness 30 of 51 — 59%`, and the gap is largely this: text that the
evidence supports in other words. Every competing tool answers that question,
and every one of them answers it with a model:

| tool | how it decides faithfulness |
| --- | --- |
| RAGAS | LLM-as-judge |
| DeepEval | LLM-as-judge |
| TruLens | LLM-as-judge |

akashi's answer was to not answer. That is defensible as a claim about
reproducibility and indefensible as a claim about usefulness, and the two do not
have to be traded against each other.

## Decision

**akashi audits. A judge annotates the audit. They are two objects and the
artefact says which is which.**

Six rules, each of them a thing that would have made this a mistake:

**A judgement is never a verdict.** akashi's verdicts are `grounded`,
`floating`, `contradicted`, `unbearing`, `unverifiable` and `unchecked`. A
judgement says `supported`, `unsupported` or `unclear`. **No word is shared**,
so a reader cannot mistake one for the other by skimming.

**They never share a section.** `judged[]` on the document, a `Judged` block in
the text rendering, and nothing in `Findings`, `Traced` or `Coverage` changes
when a judge runs.

**`report_id` does not move.** The id hashes the deterministic inputs. The same
audit with and without judgements carries one id, and `recheck` re-derives it
without a network. **The audit stays reproducible; the annotation says it is
not.**

**A judge only sees what akashi could not settle.** Grounded particulars are not
sent: akashi already knows the string, the document and the offset, and
replacing a fact with an opinion could only make the report worse. Contradicted
ones are not sent either, for the same reason.

**Every judgement names its model.** Required by the schema. Two runs against
two model versions are two different answers, and a report read a year later is
read one line at a time.

**The artefact says what a judgement is.** Three sentences join `limits` when
one is present, because the artefact travels and the documentation does not
(ADR-0005).

## What it costs

**One dependency and one door.** `akashi[claude]` installs an SDK.
`pip install akashi` still installs nothing and reaches nothing, and the CI job
that checks that opens the built artefact rather than reading this file.

`akashi.infrastructure.adapters` deliberately **does not re-export** the judge,
so `import akashi` reaches no HTTP client even where the extra is installed. The
import-linter contract is what found that it did.

**A contract that was quietly weaker than its name.** `no-network` forbids
akashi to import `socket`, `ssl`, `http`, `urllib`, `asyncio` — and measurement
shows it does not see through a dependency:

```text
a module here writing `import socket`      BROKEN
a module here writing `import anthropic`   KEPT      (anthropic opens sockets)
```

While akashi had zero dependencies, that contract and the sentence *"nothing in
akashi touches the network"* were the same statement. They stopped being the
same statement the day this shipped. The contract has been renamed to what it
checks, and a second one keeps the SDK to one module.

**A part of the report that cannot be re-derived.** That is the honest cost and
it is why the boundary is drawn where it is: everything a `recheck` compares is
still a function of the inputs, and the part that is not is in its own field,
under somebody else's name.

## What was rejected

**Merging judgements into verdicts** — a `supported` particular counted as
grounded. This would make the score better and the report worthless: the
grounded count is the number a reader takes away, and a number that means two
different things depending on a flag is a number nobody can compare.

**Making it the default.** A tool whose behaviour depends on whether an API key
happens to be set is a tool with two products and one name.

**A local entailment model, as the first step.** It is the more interesting
option — pinned weights are far closer to reproducible than an API — and it is a
larger dependency and a separate decision. The `Judge` port takes either, which
is the point of having a port.
