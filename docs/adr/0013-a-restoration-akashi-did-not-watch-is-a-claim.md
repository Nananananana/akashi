# 13. A restoration akashi did not watch is a claim, and is reported as one

**Status:** accepted

Extends [ADR-0008](0008-restore-before-you-audit.md), which said *restore before
you audit, or refuse*, and left the ordinary case with no route through.

## Context

ADR-0008 assumed two situations: akashi is given a restorer and uses it, or it
is not and refuses. Building the admission stage turned up a third that is more
common than either.

A pipeline that used `mamori` already holds the session. By the time the answer
reaches akashi it has usually been restored — that is what `mamori` is for, and
restoring twice is not a thing you can do. The package still declares
`provenance.protection`, because the package records what happened to *it*, and
the answer is a different document.

ADR-0008 refuses that, which is correct and unhelpful. The tempting fix is to
admit any answer with no placeholder-shaped text in it, on the grounds that
restored text has no placeholders.

**That inference is false, and falsely in the dangerous direction.** `mamori`'s
ADR-0026 trades obviousness for readability: it can substitute *surrogates* —
plausible fake names, plausible fake amounts — instead of `<PERSON_001>`. A
surrogate is designed to be indistinguishable from a real value. An answer
written from surrogate-protected context contains no placeholders and no real
values either, and auditing it produces exactly the catastrophic misreport
ADR-0008 exists to prevent: every honest particular floating, in bulk, on an
answer nobody can defend.

So the absence of placeholders is not evidence of restoration, and akashi
cannot obtain that evidence. Nothing local can.

## Decision

**The caller may assert that they restored the answer, and the assertion is
recorded as an assertion.**

`admit(answer, package, restored_by="mamori@0.17.0")` proceeds. The report's
provenance then says *asserted restored by mamori@0.17.0; akashi did not verify
it* — not *restored by*. The two are different sentences and the artefact
carries the one that is true.

Three rules keep it from becoming a way round the check:

- **It is explicit.** There is no default that admits a protected package, and
  no flag named `force`. A caller has to name who restored it, which is the
  same thing they would have to write in an audit trail anyway.
- **It cannot be combined with a restorer.** Two answers to "who restored this"
  is one too many, and picking either would put a name on the report that
  nobody chose.
- **It is not laundering.** akashi still reports placeholder residue it finds
  afterwards, and the assertion changes no verdict. It changes what akashi is
  willing to look at, not what it concludes.

## Consequences

The common pipeline works without an adapter, which is what makes the `mamori`
dependency genuinely optional rather than nominally optional.

A reader of the report can tell the two provenances apart, which is the whole
point: an audit trail that recorded a claim as a fact would be a worse artefact
than one that refused.

## What it costs

akashi will audit an unrestored surrogate-protected answer if a caller asserts
otherwise. The result is a report full of floating particulars with a
provenance line saying who claimed it was restored — bad, and attributable,
which is the best available outcome when the check is impossible.

A caller who does not read the parameter's documentation may use it to silence
a refusal they did not understand. The naming is the defence: `restored_by`
asks *who*, and there is no honest answer to that for someone who has not
restored anything.
