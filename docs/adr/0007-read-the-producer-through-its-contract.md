# 7. Read the producer through its contract, and import nothing

**Status:** accepted

Taken from `tsumugi`'s handling of `kiseki`, which reads an export as JSON and
imports nothing. The same trick, one seam further downstream.

## Context

akashi needs a ContextPackage. `tsumugi` produces one. The obvious move is to
depend on `tsumugi`, import its `ContextPackage` dataclass, and be done.

That would put a runtime dependency in the middle of an auditor (ADR-0001), and
it would couple akashi's release cycle to a sibling's. Worse, it would quietly
narrow the product: akashi would audit answers produced by `tsumugi`, rather
than answers produced by anything that can emit a package.

The contract already exists and is already frozen. `tsumugi.context-package/1`
is a published JSON document with a published schema, deliberately written so
that a program that has never heard of Python can produce one.

## Decision

**akashi reads a ContextPackage as JSON, against the published contract, and
imports `tsumugi` nowhere — not even in an adapter.**

The reader checks `contract` first and refuses a value it does not recognise.
Fail closed: an unrecognised version is not guessed at, and `1-draft` is
accepted because refusing evidence over a version string would be the wrong
trade.

`tsumugi` appears in one place in this repository: the `siblings` extra, which
exists so that `tests/test_seam_tsumugi.py` can build a real package with the
reference producer and audit an answer against it. Those tests skip when it is
absent. An import-linter contract asserts that no module under `src/` mentions
it.

## Consequences

akashi works with any conforming producer, including one written in another
language, and that is a bigger market than `tsumugi`'s installed base.

The seam is testable without either project being installed: a package is a
fixture file.

If the contract gains a field, akashi ignores it until it has a reason not to.
If the contract takes a new major version, akashi refuses it loudly and a
release adds support. Neither is a silent failure.

## What it costs

The dataclasses on akashi's side are a second reading of somebody else's
contract, and the two can drift. The `siblings` test suite is what catches that,
and it is the reason those tests are worth their setup cost — the interesting
failures are at the seams, and a seam only exists when something real is on both
sides.

akashi cannot use anything `tsumugi` knows and does not publish. If a check
turns out to need it, the fix is a field in the contract, negotiated across the
seam, rather than an import.
