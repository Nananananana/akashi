# 14. akashi emits a signable statement, and signs nothing

**Status:** accepted

From [proposals/0002](../proposals/0002-what-building-it-taught.md) §4.

## Context

An audit report is meant to be believed by someone who was not there. Sooner or
later somebody asks the obvious question: how do I know this report was produced
by akashi and not edited afterwards?

`recheck` answers a different and more useful question — *does this report
re-derive from its inputs* — and it answers it without any cryptography at all.
But it needs the inputs. A reader holding only the report, months later, in a
filing, has no way to tell whether the file was altered.

The tempting move is to sign it: generate a key, put a signature field on the
report, ship a `verify` command. Every part of that is a mistake.

**It costs ADR-0001.** Signing needs a crypto library, and akashi's whole
proposition is that a buyer in a regulated industry does not have to audit
anything it pulled in. Trading zero dependencies for a feature `cosign` already
provides is the worst trade in the project.

**It invents a format.** A signature field of akashi's own design means a
verifier of akashi's own design, a key distribution story of akashi's own
design, and a revocation story akashi does not have. None of those would be as
good as the ones that exist.

**And the shape already exists.** An in-toto Statement names a *subject* by
digest and carries a *predicate* about it, and is wrapped for signing in a DSSE
envelope. An audit report is precisely a predicate about a subject: the answer,
by its hash. This is not an analogy — it is the same structure, and the
ecosystem around it (in-toto, SLSA, Sigstore, `cosign`) is tooling that security
teams already run.

## Decision

**akashi emits an in-toto Statement. akashi signs nothing.**

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{"name": "answer.txt", "digest": {"sha256": "e5a3b0ba…"}}],
  "predicateType": "https://akashi.dev/audit-report/v1",
  "predicate": { … the report, unchanged … }
}
```

`akashi audit --attestation` produces this instead of the bare report. It is
**unsigned**, and the documentation says so wherever it appears, because an
envelope read as an attestation is worse than no envelope.

The subject digest is the `response_hash` the report already carries, taken from
the same field, so the two cannot disagree.

Keys, trust roots, revocation and verification are the caller's, with tooling
they choose. akashi's contribution is the shape.

## Consequences

Zero runtime dependencies survives, exactly, and the interoperability is free —
the whole feature is one serializer.

A report can go into a pipeline that already signs artefacts, next to the SBOMs
and provenance those pipelines already carry, and be verified with the same
command.

The predicate is the report unchanged, so `recheck` works on the `predicate`
field of a statement exactly as it works on a bare report. There is one shape,
wrapped or not.

If in-toto's Statement version changes, akashi emits a new `predicateType` and a
new `_type` and both are visible in the file. Nothing about akashi's own
contract moves.

## What it costs

**A caller who does not sign gets nothing they did not have.** The envelope
alone proves nothing, and a reader who sees `_type: in-toto` may assume
otherwise. That is a real hazard created by this decision and the mitigation is
wording, which is weaker than a mechanism.

**akashi cannot answer "who produced this report".** It can only put the report
in a shape where somebody else's signature answers it. For a caller with no
signing infrastructure, that is a worse experience than a built-in `--sign`
would be — and it is still the right trade, because the alternative is a
key-management story written by an auditing library.

C2PA was the other candidate and is the wrong fit: it is media-centric, its
model is metadata embedded in an asset that travels, and a JSON audit record is
not that. Worth revisiting if its text story matures.
