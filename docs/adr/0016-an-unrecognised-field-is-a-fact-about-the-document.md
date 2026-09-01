# 16. An unrecognised field is a fact about the document

**Status:** accepted

Decides what akashi does with a field its producer's contract does not list,
now that [ADR-0007](0007-read-the-producer-through-its-contract.md)'s
premise has changed underneath it. The contract akashi reads has closed, and
the reason akashi's reader gave for ignoring unfamiliar keys stopped being true
without a line of akashi changing.

## Context

`tsumugi.context-package/1` used to describe itself like this:

> A field may be added; none will be removed or change meaning.

akashi's reader took it at its word and said so in its own docstring — *"the
contract promises that fields may be added inside version 1, so ignoring an
unfamiliar key is what conformance requires"* — with two tests pinning the
behaviour and quoting the promise as their reason.

The contract now says the opposite:

> v1 is closed: nothing may be added, removed, or change meaning. Every object
> sets `additionalProperties: false`, so a consumer validating against this
> schema rejects a package carrying any field it does not list — which makes an
> extension indistinguishable from corruption, correctly. Evolution means
> `tsumugi.context-package/2`.

That is tsumugi ADR-0022, and the reasoning is theirs to make. What it does to
akashi is the subject here: an unrecognised field no longer means *a newer
producer added something*. It means *this is not a conforming package*.

**Nothing failed.** akashi's conformance tests all passed, because they check
that akashi reads what the contract permits and akashi still does. The change
was caught by the daily job that hashes the vendored copy against upstream
(`.github/workflows/contracts.yml`) — a check whose entire output on a good day
is that two hashes match, and which on this day was the only thing in the
repository that could have noticed.

## What was measured

Against the real package tsumugi emits, vendored at
`tests/contracts/context-package-seam.json`:

| package | against the contract | akashi |
| --- | --- | --- |
| as vendored | valid | reads it |
| `+ one unlisted top-level field` | **invalid** | reads it, says nothing |
| `+ one unlisted field inside an item` | **invalid** | reads it, says nothing |

So akashi audited a document that does not conform to the contract it names,
produced a report, and left no trace of it anywhere on the report. A reader
holding that report cannot tell which of the three rows produced it.

This is the failure family akashi is built to refuse in answers, occurring in
akashi: a check that passes and proves nothing.

## Decision

**akashi reads the package, and the report says the package did not conform.**

Three options, and the middle one is what shipped by accident.

**Refuse it.** Consistent with how akashi treats an unrecognised `contract`
string, and wrong here. akashi would break on any producer that is not tsumugi
and on tsumugi's own version 2, and it would throw away an audit it is
perfectly able to perform in order to report a fact it can simply state. It
also flattens a distinction akashi draws everywhere else: an unfamiliar *value*
— a fourth `layer` — is a category akashi has no handling for and would
launder, while an unfamiliar *field* is one it has no need of.

**Ignore it.** What the withdrawn promise justified. Nothing justifies it now.

**Read past it and write it down.** A field akashi does not know is unknown,
not wrong — the same distinction [ADR-0008](0008-restore-before-you-audit.md)
draws between *unverifiable* and *floating*, applied to the document rather
than to a particular. Unknown is not a reason to refuse and it is not a reason
to be silent.

The paths land in `ContextPackage.unrecognised`, reach the report as
`provenance.unrecognised`, and print in the Provenance block:

```text
Provenance
  report sha256:...
  the package carries fields the contract does not list: items[0].invented
  version 1 is closed, so this package does not conform to it
  akashi read past them and audited the rest
```

**Beside `withheld`, and for the same reason.** It is context about the
document and never an explanation of a finding
([ADR-0012](0012-an-omission-is-a-receipt-not-a-source.md)). akashi cannot tell
an extension from a newer producer from a corrupted file, the contract is
explicit that it is not meant to be tellable, and a report that let
non-conformance drift next to a floating particular would be offering an
excuse for it. A test asserts the note appears in the Provenance block and
nowhere before it.

**akashi holds the contract's field names, not its own.** `budget`,
`constraints` and `output_schema` are listed by the contract and read by
nothing in akashi. A list of the fields akashi *consumes* would report the
contract's own fields as unlisted — causing the failure this exists to catch.
The names are transcribed rather than loaded, because the vendored schema is
test material and a released akashi that read it would turn a test fixture into
a runtime dependency (ADR-0007). A test compares the transcription against the
copy, so the two cannot drift apart quietly.

## What it costs

**A second copy of part of the contract**, and a transcription is a place to be
wrong. The expensive direction is a field tsumugi adds that akashi has not
transcribed: every conforming package would then be reported as non-conforming,
to every reader. That is what the comparison test is for, and it is why the
field lists sit next to the vendored copy in CI rather than being checked only
by eye.

**akashi now says something about a package that most readers will never see**,
because conforming packages produce an empty list and print nothing. That is
the intended shape — a note that appeared on every report would be a note
readers learn to skip — but it does mean the wording is exercised rarely, and
the encoding of it on a narrow console is pinned by its own test for exactly
that reason.

**It does not make akashi a validator.** akashi checks the objects the contract
names and does not walk deeper, because holding a second copy of the whole
schema would be a second implementation to keep in step and the value does not
rise with the depth: a package carrying an invented field anywhere carries one
where akashi looks, and one path is enough to say so. A caller who needs
validation should validate.
