# AuditReport

**Contract:** `akashi.audit-report/1`
**Status: draft.** akashi emits `akashi.audit-report/1-draft` and will keep
emitting it until a second program has **produced and consumed** a report. The
freeze is that condition, not a date
([ADR-0002](adr/0002-the-audit-report-is-a-document.md)).

`akashi audit --json` produces this. The schema is
[`schemas/audit-report-1.json`](../schemas/audit-report-1.json) and ships inside
the wheel; the conformance suite is `tests/test_report_conformance.py`.

*This document is the contract, for producers and consumers alike. It is not a
description of akashi's internals, and a change to akashi that is not visible
here is not a change to the contract.*

---

## What it is

An audit report is everything a reader needs to check one answer against the
context that produced it: which load-bearing strings of the answer are in the
text that was sent, where each one was found, and — with equal prominence —
everything akashi did not check.

It is a **document**, not an object. JSON, portable, versioned, readable by a
program that has never heard of Python. A compliance record that can only be
read by importing the library that wrote it is a record that depends on that
library still existing.

A consumer holding a report needs nothing else. `answer` is in it verbatim and
every span indexes that string, so a finding can be followed without the
package, the corpus, or akashi.

**akashi is the reference producer and is not required to be the only one.**

---

## What it does not say

Said first, because the omissions in a contract matter more than the fields.

- **Nothing about truth.** `grounded` means a string is where the answer implies
  it is. A model can quote a source perfectly and reason from it disastrously.
- **Nothing about influence.** Whether the cited passage actually shaped what
  the model wrote — *causal faithfulness* — is a stronger claim, needs the
  model's internals, and akashi never runs a model.
- **Nothing about the subtle half.** A meaning reversed with every particular
  intact, or a true-looking sentence assembled from two documents each quoted
  correctly, are reported `grounded`. `limits[]` says so on every report.
- **No signature.** A report is unsigned. `akashi audit --attestation` wraps it
  in an [in-toto Statement](adr/0014-akashi-emits-a-signable-statement-and-signs-nothing.md)
  that `cosign` can sign and verify; the keys, the trust root and the revocation
  are the caller's. **The envelope alone proves nothing**, and a reader who sees
  `_type: in-toto` should not assume otherwise.
- **No corpus.** akashi never reads the documents, only the spans that were
  sent, so an anchor here is a pointer and not a copy.

### What a reader who does not hold the package may conclude

A report travels. It is signed by somebody else, forwarded, filed, and read by a
party who was not there and who does not have the ContextPackage beside them.
That reader can confirm strictly less than one who does, and the difference is
worth stating rather than leaving to be discovered.

| in a report | with the package | without it |
|---|---|---|
| `answer` | the text audited | **the same**: the answer is in the report |
| a particular's `span` | an offset into `answer` | **checkable**: slice `answer` and look |
| `segments[].text` | a slice of `answer` | **checkable**, the same way |
| `counts`, `coverage` | arithmetic over the above | **checkable** |
| `locations[]` — `source_path`, `section`, `span` | open the document and look | **an assertion**. Nothing in the report holds that document |
| `contradiction.found` | likewise | **an assertion** |
| `provenance.withheld[]` | what the producer said it left out | **an assertion**, and it was one for akashi too |

**The dividing line is not importance, it is direction.** Every offset pointing
*inward* — at the answer, which travels with the report — is something the
reader can settle for themselves. Every offset pointing *outward* — at a
document akashi read and they did not — is akashi's word.

That does not make the outward half worthless: it is precisely what makes a
finding actionable, since it tells a reader which file to open. It makes it a
**claim to be checked rather than a fact on the page**, and a reader who cannot
tell the two apart will believe the wrong one.

`akashi explain` prints this distinction under any segment carrying an outward
claim, and prints nothing where a segment carries none — because there, nothing
is being taken on trust.

**akashi stops at the package.** It never held the owner's original file, and a
report must not read as though it did. Resolving a `source_path` further back —
through whatever produced the corpus — is possible for somebody holding those
records, and is not akashi's: the coordinates here are chosen to be resolvable,
which is a different thing from being resolved
([#53](https://github.com/Nananananana/akashi/issues/53)).

---

## Shape

```json
{
  "contract": "akashi.audit-report/1",
  "report_id": "sha256:c65e88b9...",

  "audited": {
    "package_id": "sha256:aa11bb22...",
    "response_hash": "sha256:e5a3b0ba...",
    "response_length": 140,
    "segmenters": ["akashi.segmenter/en@1", "akashi.segmenter/ja@1"],
    "extractors": ["akashi.extractor/en@1", "akashi.extractor/und@1"],
    "packs": ["en", "ja", "und", "zh"],
    "akashi_version": "0.1.0"
  },

  "unchecked": [
    {"segment_id": "seg_004", "span": [402, 455], "rule": "no_particulars",
     "reason": "the segment asserts something with no load-bearing token in it"}
  ],

  "coverage": {
    "segments": 22, "bearing": 17, "unbearing": 4, "unexamined": 1,
    "particulars": 41, "checked": 41,
    "kinds_not_extracted": ["proper_noun"]
  },

  "limits": [
    "A grounded particular is a statement about strings, not about truth. ..."
  ],

  "counts": {
    "segments": {"grounded": 12, "floating": 5, "contradicted": 0,
                 "unbearing": 4, "unchecked": 1, "unverifiable": 0},
    "particulars": {"grounded": 34, "floating": 7},
    "grounded_share": 0.829
  },

  "segments": [
    {
      "segment_id": "seg_002",
      "span": [312, 361],
      "text": "Liability is capped at 45,000 dollars.",
      "kind": "prose", "script": "en", "boundary": "terminator",
      "verdict": "grounded",
      "particulars": [
        {"kind": "money", "text": "45,000 dollars", "span": [334, 348],
         "standing": "grounded",
         "in_an_interpretation": false,
         "locations": [
           {"item_id": "itm_02", "document_id": "doc_c001",
            "source_path": "contracts/2024-msa.md", "section": "Liability",
            "span": [8844, 8858], "layer": "fact"}
         ]}
      ]
    }
  ],

  "provenance": {
    "restored_by": "", "restoration_asserted": false,
    "protection_by": "", "withheld": [{"rule": "budget_exhausted", "count": 2}]
  },

  "answer": "…the whole text that was audited…"
}
```

---

## Field rules

### `contract`

Required, first. **A consumer that does not recognise the value refuses the
report** rather than guessing at it. Fail closed.

### `report_id`

`sha256` over exactly what determined the report: the response hash, the
package id, the akashi version, the segmenters, the extractors and the language
pack set.

Three things are deliberately **not** in it.

- **`created_at`**, and anything else that moves without the inputs moving. A
  hash that changes when nothing changed is a hash nobody can compare.
- **`response_length`**, which is derived from a response that is already
  hashed.
- **The findings.** A report whose id covered its own findings could not be used
  to check that they were re-derived correctly: it would always agree with
  itself.

The **pack set is in it** and this is the part a reimplementation will miss.
Narrowing the language packs changes the segmentation and therefore every count,
so two audits that hashed the same either way could claim one id for different
findings.

`akashi recheck` re-derives the id from the inputs the report names. That is the
difference between an audit and an opinion.

### `unchecked[]`

**Required, and empty only when nothing was skipped.** Every span akashi did not
examine, with the rule that caused it: `not_prose`, `no_particulars`,
`protected`. A reason is required and non-empty
([ADR-0005](adr/0005-say-what-could-not-be-checked.md)).

### `coverage`

The denominators. A ratio whose denominator is not visible is a ratio a reader
supplies their own for, and they supply the generous one.

`bearing + unbearing + unexamined == segments`, always. The three are kept apart
because **a check that treats "I looked and found nothing wrong" the same as "I
did not look" lies by omission.**

`kinds_not_extracted` names kinds in the vocabulary that no loaded rule finds.
`proper_noun` is there today.

### `limits[]`

Required, non-empty, and **fixed wording**. What the method cannot do, on the
artefact rather than in the documentation — the artefact travels and the
documentation does not. A caller who could reword it could soften it.

### `counts.grounded_share`

**`null` when nothing was checkable.** Not `0` and not `1`. An answer with
nothing to check has not scored well and has not scored badly, and a number
there would be read as one of the two. A renderer must say it in words.

### `segments[].verdict`

| | |
|---|---|
| `grounded` | every particular in the segment is in the text that was sent |
| `floating` | at least one is not |
| `contradicted` | one is not, and akashi can name the source value it replaced |
| `unbearing` | akashi looked and there was nothing to check |
| `unchecked` | akashi did not look |
| `unverifiable` | akashi could not look, and says so |

`because` is present **exactly when** the verdict is `unchecked` or
`unverifiable`, and absent otherwise: a reason on an examined segment reads as
an excuse for a finding.

`contradicted` was in the vocabulary and produced by nothing before v0.4. It
is produced now, and rarely on purpose — see `contradiction` below.

### `segments[].particulars[]`

`locations[]` and `in_an_interpretation` are present **exactly when** the
standing is `grounded`. A floating particular resolved nowhere, so there is
nothing to point at; reporting an empty list would invite a reader to think one
was looked for and not found in a particular place.

More than one location is **information, not an error.** A short particular
genuinely occurs in several, and picking one would imply a precision that is not
there.

`contradiction` is present only on a particular whose standing is `floating`,
and is forbidden on a grounded one: a particular that is in the source cannot
also be a corruption of it. It carries the source's text verbatim, the document
coordinates to open, and `why` — the rule that produced the finding, in words,
because a finding that cannot say why it is a finding is one nobody can appeal.

**`found` is not a correction.** akashi does not know which of the two values is
right; it knows they differ and that one of them is in the text that was sent.

**Expect it to be absent far more often than not, including on findings where a
source obviously exists.** akashi emits it only where the answer kept the
source's digits *exactly* and changed the text beside them — `5 grams` for
`5mg`, `1,200億円` for `1,200万円`. A value whose digits drifted is left
`floating` with no explanation, because an invented figure, a value derived by
arithmetic, and a corrupted one are the same thing to anything that reads
structure. Naming a source for those was right 47% of the time and akashi does
not ship a finding that is wrong half the time. [ADR-0015](adr/0015-the-digits-are-the-evidence.md)
has the measurement.

A consumer should treat `contradiction` as a bonus on a finding it already has,
never as the definition of one. Filtering reports down to particulars that carry
it would hide most of what akashi found.

`layer` is `kiseki`'s distinction and it survives the crossing. A particular
grounded only in an item whose layer is `interpretation` has
`in_an_interpretation: true`, and a report that flattened that would launder a
judgement into a fact.

### `provenance.restoration_asserted`

`true` when `restored_by` is the caller's word rather than something akashi
watched happen ([ADR-0013](adr/0013-a-restoration-akashi-did-not-watch-is-a-claim.md)).
**A renderer must keep the two apart in wording as well as in data**: *asserted
restored by X; akashi did not verify it* is a different sentence from *restored
by X*, and the artefact carries the one that is true.

### `provenance.withheld[]`

How many candidates the package held back, per rule. **Context for the reader
and never an explanation of any finding.** An omission carries an anchor and a
reason and not the text, so akashi cannot check an answer against one
([ADR-0012](adr/0012-an-omission-is-a-receipt-not-a-source.md)).

Four floating particulars beside nine candidates dropped for budget points at a
retrieval problem; four beside none points at a model problem. A reader with
both numbers can tell which they have. A reader given only the first will guess.

### `answer`

The audited text, verbatim. This is what makes a report complete on its own —
and it is also why **a report is as sensitive as the corpus it was audited
against.** It quotes the answer, and the answer quotes the documents.

---

## Conformance

`tests/test_report_conformance.py` checks every report the corpus can produce
against:

1. The JSON Schema.
2. Every span indexing the `answer` the report carries.
3. `bearing + unbearing + unexamined == segments`, and `segments` matching the
   array.
4. Every verdict counted, including the zeroes.
5. Every `unchecked` entry naming a segment that exists, with a non-empty reason.
6. `limits[]` present on every report.
7. `locations` present exactly on grounded particulars.

Plus seven checks that are about the *repository* rather than a report: the
verdicts, standings, particular kinds, skip rules, segment kinds, boundaries and
scripts in the code are asserted to be exactly those in the schema. There is no
pydantic here to derive one from the other
([ADR-0001](adr/0001-the-domain-depends-on-nothing.md)), so **those tests are
the only thing keeping the two representations in step.**

A producer that is not akashi passes the same suite. That is the whole point of
writing the contract down.


---

## The attestation envelope

`akashi audit --attestation` emits the same report as an **unsigned** in-toto
Statement ([ADR-0014](adr/0014-akashi-emits-a-signable-statement-and-signs-nothing.md)).

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{"name": "answer.txt", "digest": {"sha256": "e5a3b0ba…"}}],
  "predicateType": "https://github.com/Nananananana/akashi/audit-report/v1-draft",
  "predicate": { … the report above, unchanged … }
}
```

The subject digest is taken from the report's own `response_hash`, from the same
field, so the envelope and the predicate cannot disagree about what was audited.
The predicate is the report **unchanged** — one shape, wrapped or not — so
`recheck` works on `predicate` exactly as it works on a bare report.

`predicateType` is versioned apart from the report contract on purpose: a
consumer selects on that URI before it reads a field, and a URI that moved when
the contract did not would break the selection for nothing.

**akashi signs nothing.** Signing needs a crypto library and a key-management
story, and both already exist outside akashi and are better than anything an
auditing library would write. The shape is akashi's contribution; the signature
is yours.
