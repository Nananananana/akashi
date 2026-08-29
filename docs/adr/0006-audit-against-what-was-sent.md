# 6. Audit against what was sent, not against the corpus

**Status:** accepted

## Context

A particular in an answer can be checked against two different things: the
context that was actually put in front of the model, or the whole corpus the
context came from.

Checking against the corpus is more generous and it is wrong. If a model asserts
a figure that is in the corpus but was *not* in the package, the model did not
read it — it guessed, and it happened to guess a number that exists somewhere in
the archive. Marking that `grounded` rewards a lucky fabrication and teaches the
user that the check works when it did not.

The corpus is also not stable. It changes between the moment the answer was
generated and the moment someone re-examines the report, so an audit against it
is an audit that can change its own verdict retroactively.

## Decision

**The evidence set is exactly `items[]` of the ContextPackage that produced the
answer. Nothing else is evidence.**

A particular that resolves nowhere in `items[]` is `floating`, even if it is
demonstrably present in the corpus, in the omitted candidates, or in the
instructions.

Two consequences are specific enough to state as rules:

- **`omissions[]` is a signal, not a source.** A particular that resolves in an
  omitted candidate is still `floating` — the text was deliberately not sent —
  but the report says which omission it matched and under which rule. A model
  reproducing content that was withheld from it is a finding, not a pass.

- **The instructions are not evidence.** Text in `instructions`, `constraints`
  or `output_schema` is part of the prompt, not part of the corpus, and a
  particular resolving only there is `floating`. Otherwise a rule that happens to
  contain an example number would ground every answer that echoes it.

The package is identified in the report by its `package_id`, and `akashi
recheck` refuses a package whose id does not match the one the report names.

## Consequences

The audit is a closed-world check with a stated world, which is what makes it
reproducible (ADR-0003). The world is a document, and the document is hashed.

akashi never reads the corpus, never opens a database, and never needs to know
where the documents live. It needs one JSON file and one string.

## What it costs

An answer that is right for reasons outside the package scores badly, and the
user has to understand why. This is genuinely counter-intuitive to a first-time
reader and it belongs in the README rather than only here.

A caller who audits against the wrong package gets a report full of `floating`
that means nothing. The `package_id` check catches the case where the report and
the package disagree; it cannot catch the case where the caller had the wrong
package all along, and nothing can.
