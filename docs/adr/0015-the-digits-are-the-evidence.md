# 15. The digits are the evidence

**Status:** accepted

Decides how far [ADR-0004](0004-the-particular-is-the-unit-of-verification.md) may be pushed.
ADR-0004 says a particular that resolves nowhere is a finding. This says when
akashi may go further and name the value the answer replaced — and it turns out
to be a much smaller set of cases than the feature was specified for.

## Context

`floating` says *this figure is in none of your sources*. `contradicted` says
*this figure is wrong, and here is the one your source gives, at this offset*.
Only the second is a finding a reader can act on without opening the file
themselves, and it was held out of v0.1 deliberately: it is the strongest claim
akashi makes and therefore the one most able to be wrong.

It was specified like this. Take the segment's grounded particulars, find the
item sentences they resolved into, look there for a particular of the same kind
as the floating one, and if there is exactly one, that is what the source says.
A segment that grounded nothing would never be contradicted, on the reasoning
that without an anchor there is no way to know which document the sentence is
about.

The first run produced a false positive. Given a source reading
`テントは 2.4kg、二人用。前回より 300g 軽い。` and an answer reading
`テントは 2.6kg、前回より 300g 軽い。`, akashi reported that `2.6kg`
contradicted **`300g`**. Both are quantities, both were in the sentence the
grounded `300g` landed in, and there was exactly one candidate. Every clause of
the rule was satisfied and the answer was nonsense.

The diagnosis: *same kind and nearby* is not a relation between two values. It
is a coincidence of layout. What the rule was reaching for is that one value
**replaced** the other, and nothing in proximity says that.

## What was measured

A first repair defined a *shape sibling*: a value's shape is what is left when
its digits are taken out (`2.4kg` → `#kg`) and its digits are what is left when
everything else is (`2.4`). Two values are siblings when exactly one half
changed — same shape and different digits is a drifted number, same digits and a
different shape is a swapped unit. That fixed the `300g` case, which is a
sibling of neither kind.

Then it was priced against the corpus, over three widths of neighbourhood, with
the plants' declared sources as ground truth. The neighbourhood barely mattered.
Precision was **50%, 54% and 57%** for the segment, the answer's items, and the
whole package. Widening bought recall at a flat rate of wrongness.

Splitting by which half changed is what mattered:

| the relation | segment | answer | package |
|---|---|---|---|
| digits drifted, unit intact | 0 of 2 | 12 of 28 (43%) | 18 of 38 (47%) |
| unit swapped, digits intact | 2 of 2 | 7 of 7 | 12 of 12 |

Three plant kinds explain the top row, and none of them is distinguishable from
a drift by anything in the text:

- an **invented** figure. `250mg` beside a source's `5mg` is a number in the
  answer that is not in the source, sitting near a source number of the same
  shape. So is a drift.
- a **derived** value. `28回` sits beside the `2回` and the `14日` it was
  computed from. Reporting "the source says `2回`" is not merely unhelpful; it
  is false, because the source and the answer agree. akashi does no arithmetic
  and so cannot tell a product from a corruption.
- a **different** figure. A contract full of `60 days`, `90 days` and `30 days`
  offers a drifted `45 days` several equally good parents, and the uniqueness
  requirement only rejects the ones that happen to sit in the same scope.

## Decision

**akashi names the source only when the answer kept the source's digits exactly
and changed the text beside them.** A value whose digits differ from every
source value is left `floating` with no explanation, however close a source
value looks.

Identical digits are a *shared substring*. That is textual evidence rather than
resemblance, and ADR-0004 is built on the observation that a faithful
paraphrase does not have one. When `5` survives verbatim and the unit beside it
does not, the number was copied and the unit was got wrong. That is the only
case where akashi can point at a source and say the answer replaced it.

Three restrictions ride along:

1. **Same kind.** A quantity is never explained by a date.
2. **At least one digit.** Two names have the same digits — none — and
   different text, so without this guard every name would explain every other
   name and `entity_swap` would produce a finding pointing anywhere.
3. **Exactly one candidate**, taken from the tightest scope that has one: the
   item sentences the rest of the segment resolved into, then those whole items,
   then the package. Two candidates leave it `floating`.

The anchor requirement is **dropped**. A segment that grounded nothing can be
contradicted. It cost 10 findings in 12 and bought no precision, because real
answers — and the corpus's — put one figure in a sentence, so the anchor was
absent exactly when the finding was wanted. The neighbourhood now only breaks
ties, and identical digits do the anchoring that proximity was supposed to.

## What it costs

**The largest deliberate miss in the project.** `2.6kg` where the source says
`2.4kg` is a real hallucination, akashi finds it, and akashi will not say what
it replaced. Source localisation is 12 of 33 rather than 27 of 33 — and the 15
findings given up were wrong more often than not, which is the trade and not a
consolation.

**A reader gets less than the feature promised.** Digit drift is the most common
plant kind in the corpus and probably the most common in life, and it is exactly
the half akashi cannot explain. The report says `floating` and the reader opens
the file.

**A new number to keep at zero.** `source misdirection` — a source named that is
not the value replaced — is gated at 5%, which with twelve localisations means
one of them breaches. Source *localisation* is deliberately **not** gated: 27 of
33 of it was given up in an afternoon to hold misdirection at none, and a floor
under it would have forbidden the trade.

**The measurement is not independent of its generator.** Every one of the twelve
is a `unit_swap` plant produced by a rule that keeps the digits, so the recall
figure is partly circular — the fifth falsification condition in
`proposals/0002` naming itself. The *precision* figure is not: it is measured
against the `derived_value`, `invented_particular`, `digit_drift` and `grounded`
plants, which were generated independently and which the rule declines. Twelve
is a small number and this ADR should be revisited against material nobody here
wrote.

**A published contract grew a field.** `akashi.audit-report/1` gains an optional
`contradiction` on a particular, forbidden when the particular is grounded. It
is additive, so a reader of older reports is unaffected, but a consumer
validating against a cached copy of the schema will reject a v0.4 report until
it refreshes.
