# AGENTS.md

Context for AI assistants (and future humans) working on akashi. Read this whole
file before proposing or writing any change.

This file is current state and current rules. It is not a history: why a thing is
the way it is lives in `docs/adr/`, and what might happen next lives in
`docs/proposals/`. `docs/README.md` explains that separation and why it matters.
**A statement here that disagrees with the code is a defect.**

## What akashi is

A local-first Python library that takes a language model's answer and the context
package that produced it, and separates what the answer took from its evidence
from what it produced on its own. Deterministic, offline, zero runtime
dependencies, and **no model anywhere in it**.

The constitution, to be enforced by construction rather than by promise:

- **The particular is the unit.** Not the sentence. akashi checks numbers, dates,
  names, units and identifiers against the text that was sent, because those are
  strings and a string is either there or it is not (ADR-0004).
- **No model at audit time, ever.** Same inputs, same report, byte for byte.
  There is no flag that turns one on. A model may run at fixture-authoring time;
  CI calls nothing (ADR-0003).
- **A grounded particular is not a true sentence.** It means the string is where
  the answer implies it is. Any wording that blurs this is a defect, not a style
  choice (ADR-0004).
- **Say what you did not check.** `unchecked[]`, `coverage` and `limits` are
  required on every report. A partial check reported as a single number reads as
  a total check (ADR-0005).
- **The world is what was sent.** `items[]` of the package and nothing else. A
  particular that resolves only in `omissions[]`, only in the instructions, or
  only in the wider corpus is still floating (ADR-0006).
- **Fail closed.** An unrecognised contract version is refused. A protected
  answer with no restorer is refused rather than audited into nonsense
  (ADR-0007, ADR-0008).
- **The report is a document.** Versioned JSON, complete on its own,
  re-derivable by anyone holding the inputs (ADR-0002).
- **Label the response, not the ideal answer.** Ground truth is constructed by
  planting named mutations, never judged. Half the plants are deliberately *not*
  hallucinations (ADR-0010).
- **A report is as sensitive as the corpus.** It quotes the answer, and the
  answer quotes the documents. Treat every `*.audit.json` as if it were the
  notes themselves.

## Architecture map

There is no `docs/architecture.md` and there will not be one until there is an
architecture to describe. The plan is `docs/proposals/0001-the-design.md` — all
of it, still.

```text
interfaces ──> application ──> domain
                    │              ▲
                    │              │
                    └──> ports <───┴── infrastructure
```

| Layer | May import |
|---|---|
| `domain/` | **stdlib only** — and never `tsumugi`, `kiseki` or `mamori` |
| `errors.py` | nothing |
| `ports/` | `domain`, `errors` |
| `application/` | `domain`, `ports`, `errors` |
| `infrastructure/` | `domain`, `ports`, `errors` |
| `config.py` | everything above |
| `interfaces/` | everything above |

This table is executable: `tests/test_architecture.py` parses every module and
asserts it, and `import-linter` asserts the direction across five contracts. A
diagram that stops matching the code turns the build red rather than quietly
becoming fiction.

Two of those five contracts are worth knowing by name. **Nothing in akashi
imports `tsumugi` or `kiseki`** — the ContextPackage is read as JSON against a
published contract (ADR-0007), and the `siblings` extra exists only so the seam
tests can run against the reference producer. **Only `infrastructure/adapters/`
may import `mamori`** (ADR-0008).

## Conventions

Taken from `kiseki`, `mamori` and `tsumugi`, which paid for them.

- **Everything in the repository is English.** Conversation language may differ;
  committed text may not.
- TDD. One issue, one PR, squash merge, close the issue after.
- **All tests must pass before any commit.** One failure means stop and
  investigate, not proceed.
- Test file names are unique across the repository — tests are not a package and
  duplicate basenames break collection.
- Any test that invokes the CLI isolates itself: chdir to `tmp_path` and strip
  `AKASHI_*`. A CLI test that writes into a developer's real working directory is
  a bug waiting in every future test file.
- Checks before every green commit: `uv run pytest -q`, `uv run mypy src`,
  `uv run lint-imports`, `uv run ruff check --fix .`, `uv run ruff format .`,
  `uv run pre-commit run --all-files`. If pre-commit rewrites anything,
  `git add` and run it again — a commit whose hooks failed did not happen.
- Windows: set `PYTHONUTF8=1`. This project handles Japanese and Chinese text in
  every test.
- Read-only dumps for an assistant go **outside** the working tree. Working
  notes, review history and experiments live in `akashi-work/` and are **never
  published**.

## Rules particular to this project

- **Never write an architecture document for code that does not exist.** ADRs
  before code are legitimate; a current-state document before code is fiction.
- **A number in a document is measured or it is not written.** If a claim needs a
  measurement, run it, record the script and the environment, and cite it.
- **State the residual.** Every measurement ships with what it does *not* say:
  the extractor names the kinds it misses, the segmenter names its fallback rate,
  the corpus names that it is generated and not observed.
- **The forbidden vocabulary.** `true`, `false`, `correct`, `factual`,
  `verified fact` never appear in rendered output. A particular is `grounded` or
  `floating`; a segment is `grounded`, `floating`, `contradicted` or `unbearing`.
  A test asserts this, and it is not a style rule — it is ADR-0004 made
  unavoidable.
- **Anything that changes extraction or segmentation is gated on `akashi eval`.**
  Run it before and after. Every count in the report has the segmenter in its
  denominator.
- **Floors, not targets.** The eval gate is deliberately looser than the current
  scores. A gate set at today's number makes every honest experiment a build
  failure, and tuning to reach a threshold is what `mamori`'s ADR-0023 records
  the cost of.
- **Every discarding path carries its reason to the end.** A skipped segment
  produces an `unchecked[]` entry naming the rule. This is invasive to retrofit,
  so it is done from the first filter.
- **Ordering discipline.** No unordered iteration reaching an output, no partial
  sort keys, no wall-clock in anything but `created_at`. A report produced twice
  must be byte-identical, and a property test asserts it.
- **Offsets are load-bearing.** `answer[p.start:p.end] == p.text` and the
  segments tile the answer exactly. Both are property tests, not unit tests. An
  offset that has drifted points a reader at the wrong sentence, which is the
  failure ADR-0004 rejects fuzzy matching to avoid.

## Current state

- Version `0.1.0.dev0`. **Nothing is built.** The repository contains the design,
  ten ADRs, and the tooling that will enforce them.
- **License: Apache-2.0. Python: 3.12+. Runtime dependencies: 0**, checked in CI
  by installing without extras and asserting nothing came along.
- **Built:** nothing beyond `akashi.errors` and the package skeleton.
- **Next:** v0.1, the spine — segmentation, particular extraction, strict
  matching, the closed world, `akashi audit`. `contradicted` is deliberately not
  in v0.1; it ships in v0.4, after there is a corpus to price its false positives
  against. `docs/proposals/0001-the-design.md` §9 has the order and §10 has what
  would falsify the whole thing.
- **Unmeasured, and the documentation says so:** extraction recall, segmenter
  disagreement, the share of real answers that are `unbearing`. All three are
  v0.3, and the third one can change the roadmap.
- Still open: which model generates the evaluation corpus and how genres are
  sampled — the seed and the model get recorded with the fixtures. Needed before
  the corpus is generated, not before then.
