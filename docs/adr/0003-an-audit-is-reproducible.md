# 3. An audit is reproducible, and no model runs inside one

**Status:** accepted

Related: `tsumugi`'s ADR-0003, which asks the same of a package.

## Context

Every mainstream approach to this problem in 2026 puts a language model in the
verification path: decompose the answer into atomic claims with a model, then
score each claim against the context with an entailment model or a judge. The
field's own benchmarks are built that way, and its own literature reports that
the judges disagree with each other and with humans. RAGTruth, the corpus that
defined the span-level task, reports 78.8% agreement between two human
annotators at the span level — on the *labels*, before any system is involved.

That design has a defect that is disqualifying here and is rarely named: **the
audit is not reproducible.** Run it twice and the verdicts move. Run it next
quarter, after the judge model has been updated, and they move again — on a
report that has already been filed. An audit trail that changes when nobody
changed anything is not an audit trail.

It also has a circularity. The thing being checked is a language model's
tendency to assert what it cannot support. Checking it with a language model
inherits the failure mode being measured.

## Decision

**No model runs at audit time. Ever.**

Given the same response, the same package and the same akashi version, the
report is byte-identical, and its `report_id` is a hash over exactly those
inputs. Two runs produce one id.

This is a stronger rule than "the default is deterministic". There is no flag
that turns a model on. A model may be used at *authoring* time to generate
evaluation fixtures (ADR-0010); those fixtures are committed and read as files,
and CI calls nothing.

The consequence for capability is deliberate, and is the subject of ADR-0004 and
ADR-0005: akashi does less than a model-based checker and says so, rather than
doing more and being unable to say how much of it is real.

## Consequences

An audit runs in milliseconds, offline, on a laptop, inside a hospital network
with no egress. There is no API key, no rate limit, no cost per report, and no
vendor who can deprecate a verdict.

`akashi recheck` is meaningful: a third party can re-derive the report from the
inputs and compare hashes. Under a model, "re-running the audit" would be a
different audit.

Every ordering in the report is total and every iteration is sorted. A report
produced twice must be byte-identical, and a property test asserts it.

## What it costs

akashi cannot detect a hallucination that changes meaning without changing any
particular — the *subtle* half of the field's taxonomy. That is not a limitation
to be fixed later; it is what was traded for reproducibility, and ADR-0005
requires it to be printed on the report rather than left for the user to
discover.

A model-based judge will score higher on any published benchmark. That
comparison is worth making honestly, and is planned as a measurement rather than
avoided.
