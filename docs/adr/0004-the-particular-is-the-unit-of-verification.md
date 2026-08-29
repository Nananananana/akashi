# 4. The particular is the unit of verification

**Status:** accepted

This is the decision the rest of akashi is arranged around.

## Context

The obvious unit is the sentence. Split the answer into sentences, and check
each one against the context that was sent.

It does not work, and it fails in a way that looks like it is working. Checked
by exact match, almost no sentence of a real answer resolves: a model that was
told to answer in its own words does exactly that, and a faithful paraphrase of
a source shares no long substring with it. A `supported_ratio` computed that way
is near zero for a *correct* answer and near zero for a fabricated one, which
makes it a number that cannot distinguish the two.

The escape hatch everyone reaches for is similarity — edit distance, embeddings,
an entailment model. Each of them buys sentence-level recall by giving up the
property that made the check worth having. `tsumugi`'s ADR-0004 says why exact
matching stops where it stops, and it is right: past that line every step trades
a false negative for a false positive, and only one of those two is safe in an
audit.

So the sentence is the wrong unit. It is too big to match and too small to
reason about.

Look at what actually goes wrong instead. The field's own taxonomy, from
RAGTruth, splits hallucination four ways along two axes — conflict with the
source versus baseless addition, each either *evident* or *subtle*. The
expensive failures in law, medicine and patents are almost all in the evident
half, and they are almost all one kind of thing: a number, a date, a name, a
dosage, an article number, a unit. 2.4kg becomes 2.6kg. 第30条 becomes 第13条.
The tent from a different document becomes this tent. The surrounding prose is
fluent, plausible, and structurally identical to a correct answer.

Those are not paraphrases. **They are strings, and a string either occurs in the
context that was sent or it does not.**

## Decision

**akashi verifies particulars, not sentences.**

A *particular* is a load-bearing token: a quantity, a number, a date, a duration,
a unit, a currency amount, a percentage, an identifier, a proper noun, an
enumerated reference (`第30条`, `Section 4(b)`, `Fig. 2`). The extractor is
deterministic, rule-based, script-aware, and its rules are data — a language
pack, in `mamori`'s sense.

For every particular in the answer, akashi asks one question with a yes-or-no
answer: **does this string occur in the text that was actually sent?** The
comparison is the strict one — NFKC, case-folded, whitespace runs collapsed, and
nothing else — and it resolves to an offset in a source document, or it does
not resolve.

A segment is then classified by what its particulars did:

| Verdict | Meaning |
|---|---|
| `grounded` | every particular in the segment resolved |
| `floating` | at least one particular did not resolve anywhere in the package |
| `contradicted` | a particular did not resolve, and a *sibling of the same kind* did — the answer says 2.6kg where the source says 2.4kg |
| `unbearing` | the segment contains no particulars at all |

`contradicted` is the finding worth paying for, and it is available only because
the unit is the particular. A sentence-level checker sees one unsupported
sentence; akashi sees which number was changed, what it was changed from, and
where the original is.

`unbearing` is not a pass. A sentence with no particulars asserts something that
akashi cannot check, and it is counted separately and reported as such
(ADR-0005). Folding it into either `grounded` or `floating` would be a lie in
one direction or the other.

## Consequences

The headline number is honest. `grounded` over *particulars* is a ratio whose
denominator is the set of things that could be checked, and it is high for a
good answer and low for a bad one, which is what a metric is for.

Recall on the evident half of the taxonomy is, by construction, complete: a
changed number cannot escape a string comparison. akashi's error is entirely in
the other direction, and ADR-0005 is about naming it.

The check works on unstructured prose. The model does not have to emit JSON, or
cite anything, or cooperate at all. That is what makes akashi applicable to a
response that came back from a vendor endpoint, which is the case that motivated
the project.

Extraction quality becomes the whole game. A particular that is not extracted is
never checked, and a silent miss is worse than a loud one — so the extractor's
recall is measured against labelled fixtures and gated in CI (ADR-0010), and the
kinds it does not extract are listed on the report.

## What it costs

**akashi cannot see the subtle half.** A sentence that reverses a conclusion
while keeping every number intact passes. A causal claim invented between two
correctly quoted facts passes. Negation is only caught where a negation marker
is itself treated as a particular, which is a narrow and language-specific
device and is not a solution.

**A number that is genuinely derived is a false positive.** "The two tents come
to 4.8kg" is arithmetic over two grounded facts, and 4.8 occurs nowhere in the
source. It is reported as `floating`, correctly under the definition and
uselessly for the reader. ADR-0005 requires this class to be visible as its own
kind rather than mixed into the fabrication count, and derivation checking is
scoped as later work rather than pretended away.

**Cross-document stitching is invisible.** A subject taken verbatim from one
document and a predicate taken verbatim from another produce a false sentence in
which every particular resolves. akashi reports `grounded`, and is wrong. This
is the sharpest limit in the design; it is named on every report and it is the
first thing a later ADR should attack.

A supported particular is not a true sentence. `tsumugi`'s ADR-0004 says a
verified citation is not a true claim, and the same sentence has to be said here
one level down. Any wording that blurs it is a defect, not a style choice.
