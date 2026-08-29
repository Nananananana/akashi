# 12. An omission is a receipt, not a source

**Status:** accepted

Supersedes one clause of
[ADR-0006](0006-audit-against-what-was-sent.md), which claimed a capability the
ContextPackage contract makes impossible. The rest of ADR-0006 stands
unchanged, and this is the correction rather than a change of mind.

## Context

ADR-0006 said:

> **`omissions[]` is a signal, not a source.** A particular that resolves in an
> omitted candidate is still `floating` — the text was deliberately not sent —
> but the report says which omission it matched. A model reproducing content
> that was withheld from it is a finding, not a pass.

The first two sentences are right and are why the closed world is what it is.
The third cannot be implemented. From the contract:

> An omission carries an anchor and a reason but **not the omitted text**.
> Copying what was deliberately not sent into the thing being sent would defeat
> the point.

So there is nothing to match against. An omission names a document and a span;
it does not carry the characters. Detecting "the model reproduced what we
withheld" needs the withheld text, and the only place that exists is the corpus
— which akashi does not read, by the same ADR-0006 that asked for the feature.

This was found by building the evidence index and looking for the field to put
in it. It is a good argument for building the seam before writing about it.

## Decision

**akashi indexes `items[]` and nothing else. `omissions[]` is read, counted and
reported, and never searched.**

A floating particular is reported as floating, full stop. Alongside it the
report carries what the package withheld — how many candidates, under which
rules, from which documents — as *context for the reader*, and never as an
explanation of any particular finding.

That context is worth carrying. "Four particulars floating, and the package
withheld nine candidates under `budget_exhausted`" points at a retrieval
problem rather than a model problem, and a reader who has both numbers can tell
which one they have. Under the deleted design they would have got a stronger
claim that akashi cannot actually stand behind.

Anything that would need the withheld text — including the `omitted_source`
plant the evaluation corpus was going to use (ADR-0010) — is out of scope until
either the contract carries a hash of the omitted span or the caller supplies
the corpus. The first is a change to negotiate across the seam (ADR-0007). The
second is refused: an auditor that reads the corpus is auditing a different
world from the one the answer was produced in.

## Consequences

The evidence index has exactly one source, which makes "grounded in something
that was deliberately withheld" unrepresentable rather than merely unwritten.

The report gains a `withheld` summary, which is cheap, honest, and diagnostic of
the layer above akashi.

`omitted_source` leaves ADR-0010's table of planted kinds. A plant nothing can
detect is a plant that measures nothing.

## What it costs

The single most distinctive finding in the original design is gone. A model
reproducing content that was withheld from it is a genuinely interesting event,
and akashi cannot see it.

A reader may over-read the `withheld` summary — seeing four floating
particulars and nine withheld candidates and concluding the model read the
withheld ones. The rendering has to keep them apart in wording as well as in
data, and that is a presentation obligation this ADR creates and does not
discharge.

If the contract later carries a hash per omitted span, this becomes possible
again for exact reproductions and only those. That is worth asking for, and it
is worth asking for as a hash rather than as text: the hash makes the check
possible without putting the withheld characters back into the document that
was meant not to contain them.
