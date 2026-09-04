# 18. Where the shipped audit departs from its own specification

**Status:** accepted

## Context

`akashi_specification.md` (0.1.0 Draft) is the design this project was started
from, and a 2026-09-05 review compared it against what shipped. Five points
differ. A specification nobody reconciles becomes a document people quote
selectively, so each is decided here rather than left to whoever reads which
file first.

Three of the review's findings are **not** conflicts and are already true of the
shipped code: limits live on the report object, core and judge are separated,
and the deterministic score is reported apart from any model's opinion.

## Decision

### 1. Optional model extras are kept. The spec's "Runtime Dependencies: 0" is kept too, because they are not in conflict

The spec forbids LangChain, LlamaIndex, Pydantic, Pandas and NLTK in the core.
That still holds exactly: `pip install akashi` brings **nothing** and opens no
socket, and a CI job checks the built artefact rather than the declaration.

`akashi[nli]` and `akashi[claude]` are opt-in extras behind a port, reached only
through `--judge`, and a judgement never becomes a verdict (ADR-0017). The
review asks for precisely this in §3.2. What the spec was protecting — a core
that decides by comparing strings, offline, reproducibly — is not what an extra
touches.

### 2. akashi does not read tsumugi's SQLite. ADR-0007 wins

The spec proposes `infrastructure/adapters/tsumugi_store.py`, "tsumugi の SQLite
を直接引く決定論的アダプター", and says the two should be 密結合 sharing a
reverse index.

**Rejected.** A private database schema is not a contract: it changes without a
version, and a consumer reading it has no way to notice. akashi reads
`tsumugi.context-package/1` as a document, validates it against the published
schema, and imports tsumugi nowhere — enforced by an import-linter contract and
a nightly job that fetches the upstream fixture and fails when it moves. That
job has already caught one upstream change (2026-09-04) and answered "still
conforms" with a diff rather than a guess.

The coupling the spec wanted is real and valuable; the seam it proposed was the
expensive way to get it.

### 3. `confidence_score: float` is not added

The spec's `VerifiedClaim` carries `confidence_score: float  # 決定論的な一致率`.

**Rejected.** On an exact comparison that number is 1.0 or 0.0, and a float
where a boolean lives is an invitation: the first person who needs a few more
matches lowers it to 0.9, and the audit becomes a detector tuned to a threshold
that no measurement supports. `docs/measurements.md` records what that costs —
a digit-drift rule scored 47% against 12/12 for identical digits, and only the
second one shipped.

What a reader gets instead is the verdict, the offsets, and the name of the
matcher that decided (`report_id` includes it, so two runs answering the
question differently cannot be mistaken for one another).

### 4. The verdict vocabulary stays as shipped

The spec proposes `verified` / `dangling_unsupported` / `partially_supported`.
Shipped: `grounded`, `floating`, `contradicted`, `unbearing`, `unchecked`,
`unverifiable`.

**Shipped vocabulary wins.** It separates three things the spec's three words
merge: *akashi looked and found nothing to check* (`unbearing`), *akashi did not
look* (`unchecked`), and *akashi could not look* (`unverifiable`, ADR-0008). A
reader who cannot tell those apart cannot tell a clean answer from an unread
one. `audit-report/1` is published and the review asks for it to be a long-term
contract, which this also settles: the words do not move.

### 5. `normalized` is the default matcher, and the spec's strict character isolation is available under a name

The spec's §2.3 rules out fuzzy matching entirely: byte-exact or `unsupported`.
The shipped default folds width, case and combining marks, and lets a
particular's *internal* spacing vary — `2.4kg` finds `2.4 kg`.

**Both ship, and the choice is on the report.** `--matcher exact` is the spec's
rule. `normalized` is the default because half of what akashi reads is CJK,
where a full-width `２.４kg` and a half-width `2.4kg` are the same value written
by two editors, and reporting an honest citation as fabricated is not a stricter
audit — it is a broken one.

The honest part of this entry: **the corpus cannot currently tell the two
apart** (102 grounded / 52 floating under both, across all 30 cases), so the
spacing tolerance the default argues for is measured by nothing. That is
recorded in `docs/measurements.md` and is why the matcher name is in
`report_id` rather than a footnote.

## What this does not settle

The review's strongest new idea is **conflict-aware auditing**: when two sources
disagree, say so as a first-class finding rather than grounding against
whichever one matched. That is not a departure from the spec, it is absent from
both, and it is now roadmap item 1.4 — behind measurement, like everything else
that names a source.

## What it costs

**Two documents now have to be read together.** Anyone handed
`akashi_specification.md` alone will believe akashi reads tsumugi's database and
carries a per-claim confidence score. This file is the correction and nothing
forces a reader to it.

**Point 5 is an unpaid debt, not a settled question.** The default matcher's
spacing tolerance is argued for at length in `domain/matching.py` and measured
by nothing: the corpus produces identical numbers under both matchers. If the
argument is wrong, the default is wrong, and this ADR records that it was
decided on reasoning rather than evidence.

**Refusing the direct SQLite adapter costs speed and fidelity.** akashi reads a
serialized package instead of an index, so it re-extracts particulars from the
evidence on every audit rather than sharing tsumugi's. That is measurable work
(`SourceIndex.of` is 18 ms over 160 contexts) traded for a seam that survives an
upstream schema change without anyone noticing.

**Refusing `confidence_score` costs a shape people expect.** Every rival returns
a float per claim, and a consumer porting a dashboard to akashi has to change
their renderer rather than their field name.

## Consequences

- The specification is now a historical document plus this file, not a rival
  source of truth. Anyone reading it should read this beside it.
- Points 2, 3 and 4 are enforced by tests, not by agreement: an import contract,
  the published schema, and `tests/test_verdicts.py`.
- Point 5 is the one with an open measurement debt against it.
