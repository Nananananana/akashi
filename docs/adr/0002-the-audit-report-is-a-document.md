# 2. The audit report is a document, not a type

**Status:** accepted

Taken, with thanks, from `tsumugi`'s ADR-0002.

## Context

The natural shape for a result in Python is a dataclass. Callers import it, hold
it, and read attributes off it. It is convenient, and it is invisible to
everything that is not Python.

An audit report is the one artefact of this whole system that outlives the
process that made it. It is the thing attached to a filing, handed to a
reviewer, stored for seven years, and re-examined by someone who was not there.
A compliance record that can only be read by importing the library that wrote it
is a compliance record that depends on that library still existing.

## Decision

**The audit report is a versioned JSON document, `akashi.audit-report/1`.**

It is complete on its own: the answer that was audited, every segment of it,
every particular found in each segment, what each one resolved to, the anchors
back into the source documents, and the account of what could not be checked. A
reader holding one needs nothing else — no database, no package, no second
request.

The schema is published in `schemas/audit-report-1.json` and ships inside the
wheel. A consumer validating a report does not fetch a schema from the internet.

The dataclasses still exist and are still the internal representation. They are
not the contract. A change to them that is not visible in the schema is not a
change to the contract; a change visible in the schema is a version.

Following `tsumugi`: **the contract is frozen once a second program has produced
and consumed a report**, not once the calendar says so.

## Consequences

akashi is the reference producer of audit reports and is not required to be the
only one. Someone else's auditor emitting a conforming report is a success, not
a threat.

`akashi recheck` becomes possible: a report and the package it names are enough
to re-run every assertion in the report offline, with no model, no network, and
no trust in whoever produced it. That is the property a regulated buyer is
actually asking for, and it exists only because the report is a document.

## What it costs

Two representations of the same thing, and a test suite whose job is keeping
them in step. There is no pydantic here (ADR-0001), so nothing derives one from
the other, and a test is the only thing standing between them.

Every field is forever. A JSON document with an outside consumer cannot be
refactored, only versioned.
