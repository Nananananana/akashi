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
  particular that resolves only in the instructions or only in the wider corpus
  is still floating (ADR-0006). `omissions[]` is counted and reported and
  **never searched** — it does not carry the omitted text (ADR-0012).
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
- **Floors, not targets.** The gate is deliberately looser than the current
  scores, and `src/akashi/evaluation/floors.py` refuses a floor set *at* its
  measurement — the rule is enforced at construction rather than left to
  whoever writes the next one. Every bound prints beside the score it was set
  against, because a floor that has crept up to meet its measurement has become
  a target and the gap is what makes that visible.
  - Two bounds *are* their measurement and say so: refusing a protected
    response and producing the same report twice are invariants (ADR-0008,
    ADR-0003), not quality metrics. There is no honest experiment that trades
    either away.
  - Three metrics are deliberately **ungated**. Gating `declared misses passed`
    would forbid akashi from ever catching a cross-document stitch, which is a
    goal. Gating a number you want to move is how a measurement becomes a cage.
- **CI runs `akashi eval --tier ci --gate`** on every push.
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

- Version `0.1.0.dev0`. **v0.1 is done**; nothing is released and the public API
  is not stable.
- **License: Apache-2.0. Python: 3.12+. Runtime dependencies: 0**, checked in CI
  by installing without extras and asserting nothing came along.
- 1,290 tests, 97% coverage. `ruff`, `mypy --strict` and six `import-linter`
  contracts all green. The two that were parked in `.importlinter` went live
  when `evaluation/` appeared, which is what `tests/test_layering_config.py`
  exists to force.
- **Built:** `domain/span`, `domain/text` (the one normalization tolerance, with
  the map back to original offsets), `domain/language`, `domain/segment`
  (structure pass then sentence pass), `domain/particular`, `domain/extraction`,
  `domain/anchor`, `domain/matching`, `domain/evidence` (the closed world),
  `infrastructure/packages` (the ContextPackage reader), `domain/package`,
  `domain/verdict`, `domain/coverage`, `domain/protection`, `domain/report`,
  `ports/restorer`, `application/admit`, `application/audit`,
  `domain/contradiction` (what the source says instead),
  `infrastructure/rendering` (text and JSON), `interfaces/cli`, and the
  `und`/`en`/`ja`/`zh` packs in `infrastructure/languages/`. All ten particular
  kinds have rules; `proper_noun`'s are structural and the limit is standing.
- **One command: `akashi audit`**, with `--json`, `--language`, `--restored-by`
  and `--fail-on-findings`. Exit codes: `0` audited, `1` refused, `2` misused,
  `3` audited-with-findings (only under `--fail-on-findings`). Finding things is
  what an auditor does, so it is not a failure by default.
- **The text rendering has a `Traced` section**, and it is not decoration. The
  README promises a reader *this figure comes from your document, at this
  offset*; a report that printed only what went wrong would not deliver it, and
  for a compliance artefact the traceable half is the half somebody signs.
- **`ContextPackage` is a domain value; only its *parsing* is infrastructure.**
  The application layer may not import infrastructure (the table above), and the
  audit is a function of the package — so the value lives in `domain/package.py`
  and `infrastructure/packages/` produces it.
- **Six verdicts, and three of them mean "nothing wrong" differently.**
  `grounded` / `floating` / `contradicted` / `unbearing` (looked, nothing to
  check) / `unchecked` (did not look) / `unverifiable` (could not look).
  `contradicted` is defined and produced by nothing until v0.4, and a test
  asserts it cannot ship by accident. `grounded_share` is `None` rather than
  `1.0` when nothing was checkable — a number there would be read as a pass.
- **Fixture offsets are computed, never typed.** Three of the four hand-written
  fixture anchors were wrong on the first run, which is `mamori`'s dataset rule
  earning its keep. `tests/test_contract_conformance.py` validates every fixture
  against the vendored `tsumugi` schema *and* checks that each anchor's length
  matches its own text — the schema cannot express the second and every reported
  offset rests on it.
- **`docs/proposals/0002-what-building-it-taught.md` is the current roadmap.**
  `0001` is the design as written before any code and stays that way; `0002`
  revises its plan from what building cost, what the measurements said, and what
  changed outside the repository. Read `0002` first.
- **A restoration akashi did not watch is a claim** (ADR-0013). An answer with
  no placeholders in it is *not* evidence of restoration — `mamori` can
  substitute surrogates, which are designed to look like real values — so a
  package declaring reversible protection is refused unless a restorer runs or
  the caller passes `restored_by=...`. That assertion goes on the report as an
  assertion, attributed, and changes no verdict.
- **The first eval run found things, which is what a first run is for.** Two
  genuine extractor gaps (`℉` was not in the SI alternation; `percentage points`
  was not an English unit) and three plants in the genre specs that were
  mislabelled `entity_swap` when they were inventions. akashi was right about
  those three and the corpus was wrong. Both classes are fixed.
- **`akashi eval` scores 42/42 fabrication recall and 0/42 false positives on
  the generated corpus.** That number is evidence the method does what it says
  on material written against its stated design — not evidence about production
  traffic. The corpus was authored for it.
- **Extraction recall on nine hand-marked realistic answers: 91 of 96 (95%),
  precision 100%, every span exact.** Five misses, all names with no title,
  honorific or legal form beside them. **ADR-0004 survives its falsification
  condition.**
- **akashi reads structure, not names.** The proper-noun rules are three
  families — a title, an honorific, a legal form — and nothing else. A
  capitalised-word heuristic would put a particular on every sentence-initial
  word in English, and akashi would be guessing rather than reading. `mamori`'s
  much larger Japanese name detector is **recall-first by policy** (its
  ADR-0013) and most of it must not be copied: here a false name is a floating
  particular on every report that mentions an ordinary word.
- **`様` is deliberately not an honorific here.** It ends 仕様, 模様, 多様 and
  同様 — words that live in exactly the specification and contract documents
  akashi is aimed at — and it put a name on `筐体仕様` on the first measured run.
  Dropping it costs `佐藤様`. A precision-first extractor that is not precise is
  worth nothing at all.
- **`unbearing` is 30% on realistic answers and 13% on the generated corpus.**
  The generated one was written to carry particulars; the 30% is the honest
  figure. It was 35% before the structural name rules shipped, and that fall is
  the clearest evidence that coverage and extraction are the same question asked
  twice. What remains is mostly the model hedging or reporting what it could not
  find, which is a different thing from a claim it cannot check.
- **Marking those answers found three more extractor defects**, and one of them
  mattered: the sign was being dropped from `-20℃` and `±0.02mm`, so a flipped
  sign would have grounded against the value it was flipped from. Also a
  year-month date (`August 2026` read as `August 20`) and a digit inside a word
  (`HbA1c` yielding a `1`). The digit-in-word fix then broke `350kPa` in the
  corpus, which is why the rule forbids a letter *before* a bare number and not
  after: a letter before a digit is a word carrying a digit; a letter after one
  is a unit the extractor does not know yet.
- **v0.3 was done ahead of v0.2, deliberately.** v0.3 is the milestone that
  decides whether ADR-0004 holds; freezing a report contract around a method
  whose extraction recall was unmeasured would have been fixing a shape before
  knowing it works. ADR-0002 does not object — the freeze waits for a second
  consumer, not for a date. **Both of ADR-0004's falsification conditions were
  checked and neither fired.**
- **The case format is `akashi.case/1`.** A manifest carries each plant's text
  *and* its span, and the loader refuses a case where they disagree. Deriving
  the text from the span would make the check vacuous: an edited response would
  move every plant onto different words and the manifest would agree with itself
  all the way down.
- **42 generated cases**, `tests/cases/`, three languages and four genres, 177
  plants across ten kinds. `tools/generate_cases.py --check-only` re-derives
  every one and runs in CI on every push: a generated case that is broken fails
  a *correct* implementation, so the oracle is checked as often as the code.
- **The prose is authored and the labels are computed.** A spec says what a
  sentence *is*; `generation.py` derives what should follow. A spec that could
  state its own expectations would be an annotation, and an annotated corpus
  measures the annotator.
- **A plant carries three booleans, and they are three questions.**
  `expect_detected` (should akashi flag it), `is_hallucination` (is the span
  actually wrong), `declared_miss` (is akashi's silence a stated limit). The
  plants where they disagree are the reason the corpus is worth more than a
  hallucination benchmark.
- **Contract: `akashi.audit-report/1-draft`.** `schemas/audit-report-1.json`
  publishes it and ships inside the wheel; `docs/audit-report.md` is the
  contract for producers and consumers; `tests/test_report_conformance.py`
  checks seven rules against every report the corpus can produce, plus seven
  that assert the enums in the code and the enums in the schema are the same
  set. There is no pydantic (ADR-0001), so those are the only thing keeping the
  two representations in step.
  **Frozen when a second program has produced and consumed a report, not on a
  date.** A test asserts the string still ends in `-draft`, and it changes in
  the same commit that records why.
- **`akashi recheck` re-derives a report from the inputs it names.** It refuses
  *before* it works: a recheck against the wrong package or the wrong response
  would report a mismatch, and that mismatch would be a true statement that
  misleads. A version difference is named first and explicitly is not tampering.
  It re-derives with **the packs the report names**, not this machine's default.
  Exit codes: `0` identical, `1` could not run, `5` re-derived and different.
- **The report's *shape* is domain (`AuditReport.to_dict`) and only its
  serialization is infrastructure.** A report is a document (ADR-0002), and what
  a document contains is not a formatting decision — `recheck` lives in
  `application`, which may not reach infrastructure, and needed the shape.
- **`akashi audit --attestation` emits an unsigned in-toto Statement**, so a
  report can be signed and verified by `cosign` — tooling security teams already
  run. **akashi signs nothing** (ADR-0014): the Statement is a JSON shape and
  the keys are the caller's, which is how zero runtime dependencies survives a
  signing story. A test asserts no field anywhere invites the reading that it is
  already signed.
- **v0.2 is done.** Next is v0.4: `contradicted`, the unit check that needs no
  unit table, and structural proper nouns. Baselines to beat, measured: verdict
  correctness 35%, source localisation 0%, coverage over everything marked 91%.
- **The corpus does not exercise the structure pass.** Its 177 segments are all
  prose; the nine marked answers are the only material with tables and list
  items in it (53 prose, 15 table rows, 12 list items). Worth fixing when the
  corpus next grows.
- **`proper_noun` is declared and extracted by nothing.** Recognising a name
  without a dictionary or a model is guessing. It appears in every report's
  `kinds_not_extracted`; the structural cases — a token in front of `Inc.` or
  `株式会社` — are evidence rather than a guess and are worth building later.
- **Segmentation merges where it is unsure**, deliberately: an ellipsis and a
  terminator inside brackets are not boundaries. Merging two sentences moves a
  denominator; splitting one invents a segment, and only the second can invent a
  finding. Every such choice is a comment naming the trade, and they are the
  first thing to re-examine when the v0.3 corpus produces a segmentation number.
- **Extraction prefers a miss to a false find**, for the same asymmetry read the
  other way. A bare CJK numeral is not a quantity — `一部` is "a portion" far
  more often than "one copy" and `一个` is the indefinite article — so a kanji
  numeral is only admitted with a magnitude character in it, or between two
  markers like `第…条`. The price is that `三人` is missed, and a test asserts
  that price so it stays a known quantity rather than a surprise.
- **Measured, in `docs/measurements.md`:** extraction recall (91% over
  everything marked, 100% over the kinds akashi claims), the `unbearing` share
  (35% on realistic answers, 13% on the generated corpus), and the segmenter's
  fallback share (1.1%). Still owed: a hand-segmented reference set, so there is
  a segmenter *disagreement* rate rather than only a fallback rate. ADR-0009
  asked for that one and it is not paid.
- Still open: which model generates the evaluation corpus and how genres are
  sampled — the seed and the model get recorded with the fixtures. Needed before
  the corpus is generated, not before then.
