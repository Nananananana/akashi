# 8. Restore before you audit, or refuse

**Status:** accepted

Inherited from `tsumugi`'s ADR-0009, which inherited the shape of the problem
from `mamori`. It arrives here in a harder form, because akashi reads the
*answer* rather than the package.

## Context

In the intended pipeline, `mamori` replaces sensitive values with placeholders
before the prompt leaves the machine, and puts them back when the answer comes
home. The window in between is where the answer is generated, and an answer
generated inside that window talks about `<PERSON_001>` and `<AMOUNT_003>`.

If akashi audits that text, every particular it extracts is a placeholder, and
no placeholder occurs in the source documents. The report comes back with
everything `floating` — a perfect score for a fabrication detector, and complete
nonsense. The user is being told that an honest answer is a pack of lies, in the
component whose whole job is to be believed.

Unknown and false are different, and an auditor that conflates them teaches its
user to ignore it.

## Decision

**akashi detects placeholder residue before it audits, and refuses rather than
reporting.**

The check runs first, on both the answer and the package. If the package's
`provenance.protection` is non-null, or the answer contains text matching a
placeholder shape, akashi will not produce an ordinary report. It produces one
of two things:

- a **refusal**, naming what it found and what would be needed to proceed —
  `protected_and_no_restorer`; or
- an **audit of the restored text**, when a restorer was supplied, with
  `provenance.restored_by` on the report saying who did it.

Where the protection was irreversible — a value masked or blocked rather than
pseudonymised — the affected segments are `unverifiable` with the reason, and
never `floating`. `mamori`'s policy allows both, so both have to be handled.

The restorer is a port. akashi defines the interface; the `mamori` adapter is
optional and lives in `infrastructure/adapters/`, and an import-linter contract
keeps that knowledge from spreading upward. A caller who has already restored
the text hands akashi plain text and needs none of it.

## Consequences

The most damaging possible misreport — an honest answer scored as fabricated,
in bulk — is structurally unreachable rather than merely unlikely.

The failure is loud. `provenance.protection` in the package exists precisely to
make this detectable, and akashi is the consumer it was put there for.

## What it costs

A placeholder-shaped string in a genuine answer triggers a refusal on an
unprotected package. The shape is distinctive enough that this is rare and
cheap; a refusal is recoverable, and the opposite error is not.

akashi has to know what a placeholder looks like without importing `mamori`,
which means a small amount of duplicated knowledge in a pattern. A seam test
against the real redactor is what keeps it from rotting.
