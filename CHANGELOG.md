# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Nothing has been released. The public API is not stable and there is no public
API yet.

## [Unreleased]

### Added

- **v0.1, the spine.** `akashi audit` reads a ContextPackage and an answer and
  reports which particulars of the answer are in the text that was sent, where
  each one was found, and everything that was not checked. Text and JSON
  output; `en`, `ja` and `zh`; zero runtime dependencies; no model anywhere.
- **v0.2, the report becomes a contract.** `report_id` over exactly the inputs;
  `akashi.audit-report/1-draft` published as a JSON Schema that ships in the
  wheel, with [`docs/audit-report.md`](docs/audit-report.md) as the contract;
  `akashi recheck` to re-derive a report from the inputs it names; and
  `akashi audit --attestation` to emit it as an unsigned in-toto Statement that
  `cosign` can sign. akashi signs nothing
  ([ADR-0014](docs/adr/0014-akashi-emits-a-signable-statement-and-signs-nothing.md)),
  so zero runtime dependencies survives a signing story intact.
- **The roadmap was revised from evidence**, in
  [`docs/proposals/0002-what-building-it-taught.md`](docs/proposals/0002-what-building-it-taught.md).
  `0001` stays exactly as it was written.
- **v0.3, the corpus and the floors.** `akashi eval` runs 42 generated cases
  with 177 planted spans and nine hand-marked realistic answers, and gates on
  floors set deliberately below what was measured.
  [`docs/measurements.md`](docs/measurements.md) carries every number with the
  command that produced it and what it does not say. The headline:
  **extraction recall is 100% over the kinds akashi claims and 91% over
  everything a person marked**, and about a third of a realistic answer is
  prose akashi has nothing to check in — so ADR-0004 survives both of its
  stated falsification conditions.
- **v0.4, names and the first thing akashi can say about a source.** Structural
  `proper_noun` rules -- a title before a name, an honorific or professional
  title after one, a legal form on an organisation -- took extraction recall
  over everything a person marked from 91% to 95% and unbearing segments from
  35% to 30%.
- **A package that does not conform is audited, and the report says so.**
  `tsumugi.context-package/1` closed while akashi was not looking: it used to
  promise that *"a field may be added"* and now says nothing may be, with
  `additionalProperties: false` on every object. akashi's reader had been
  ignoring unfamiliar keys and citing that promise as its reason. It now reads
  past them and writes them down -- `provenance.unrecognised` on the report,
  and three lines in the Provenance block naming the paths. Unknown is not
  wrong, so akashi does not refuse; unknown is not nothing, so akashi does not
  stay quiet. See
  [ADR-0016](docs/adr/0016-an-unrecognised-field-is-a-fact-about-the-document.md).

  **Nothing in the test suite failed.** Every conformance test checked that
  akashi reads what the contract permits, and it still does. The daily job that
  hashes the vendored copy against upstream was the only thing in the
  repository able to notice, and its whole output on a good day is that two
  hashes match.

- **`contradicted` ships, and it is a third of the feature it was specified
  as.** akashi now names the source value an answer replaced -- `the source
  says '5mg'` with the offset to open -- but only where the answer kept that
  source's digits *exactly* and changed the text beside them. Source
  localisation went from a structural 0 of 33 to 12 of 33, with **0 of 12
  misdirected**.

  The wider rule was built first and measured: naming a source for a value
  whose digits had drifted was right 47% of the time, because an invented
  figure, a value derived by arithmetic and a corrupted one are the same thing
  to anything that reads structure. 15 findings were given up to hold
  misdirection at zero.
  [ADR-0015](docs/adr/0015-the-digits-are-the-evidence.md) has the numbers, and
  `source misdirection` is now a gated floor while `source localisation`
  deliberately is not -- a floor under a number you are willing to trade is a
  cage, and this trade would have been a build failure under one.
- **A malformed `protection` block is refused rather than read charitably.**
  The ContextPackage contract requires `by`, `scope` and `reversible`, the
  first two with `minLength: 1`; the reader took `scope` as optional and
  `reversible` through `bool()`, so a block missing them was audited as
  "irreversible, scope unstated" — and `bool("false")` is `True`, which is the
  unsafe direction for the field [ADR-0008](docs/adr/0008-restore-before-you-audit.md)
  turns on. Nothing on the wire exercised it, because `tsumugi` writes all
  three. Refusing it is the house rule everywhere else here, and this was an
  accident rather than a decision.
- **A vendored contract that goes stale is a test failure rather than a
  discovery.** `tests/contracts/upstream.json` records where each copied schema
  came from — repo, path, commit, `sha256`, date, licence — and two checks watch
  it: an offline one on every run, catching a copy edited here, and a
  `network`-marked one in its own daily workflow, catching a copy the producer
  has moved past. Both were watched failing before being trusted.
- **The seam with `tsumugi`.** Every other test in this repository reads a
  package somebody here typed, which proves akashi is self-consistent and
  nothing more. `tests/contracts/context-package-seam.json` is real output from
  `tsumugi context --json`, vendored beside the schema it instantiates, and
  `tests/test_seam_tsumugi.py` puts the two implementations of that contract in
  front of each other — including the three cases the producer widened the
  fixture to carry: an omission, a superseded passage sent rather than dropped,
  and `protection: null` rather than absent.
- **The unit check was measured and did not ship**, which is what its issue
  asked for. The naive rule fires on 5 of the 7 grounded bare numbers in the
  corpus and every firing is noise: Japanese and Chinese have no whitespace, so
  the "token after a number" is a particle. A narrowing that consults the unit
  table on the source side only makes no noise and catches both motivating
  cases — and cannot tell a *swapped* unit from a *re-worded* one, which cannot
  be measured on material written by the author of the unit lists.
  [`docs/measurements.md`](docs/measurements.md) publishes it; the feature waits
  on the v0.6 public corpus.
- **`unverifiable` is produced.** It was in the vocabulary, handled in
  coverage, required by the report schema, promised by
  [ADR-0008](docs/adr/0008-restore-before-you-audit.md) and described in three
  docstrings — and no audit had ever emitted it. `admit()` computed the
  placeholder residue and `audit()` never passed it on, so a value `mamori`
  masked came back **`floating`**: an honest answer reported as probably
  fabricated, by the component whose job is to be believed. A segment whose
  value could not be restored is now `unverifiable`, says which token and why,
  carries no particulars, and counts as unexamined rather than as a finding.
  The rest of the answer is still audited.
- **A comma binds two numbers only when it is a thousands separator.** The
  boundary rule that stops `45` matching inside `45,000` treated every comma
  between digits the same way — and NFKC turns the fullwidth `，` into `,`, so
  `见第3，5，7条`, an ordinary Chinese enumeration, failed to resolve into the
  document it was extracted from. An honest answer quoting that list would have
  been reported as fabricated, in one of the three languages akashi claims to
  read. Found by the property test that says everything extracted from the
  evidence must ground back into it, and pinned there as the project's first
  `@example`.
- **The `predicateType` and the schema `$id` moved into a namespace akashi
  holds.** They were under `akashi.dev`, a domain anybody can buy. in-toto's
  guarantee for a `predicateType` *is* the namespace — *"TypeURIs are not
  registered. The natural namespacing of URIs is sufficient to prevent
  collisions"* — and a namespace only prevents collisions if it is yours. Since
  an attestation travels, is keyed on before a field is read, and cannot be
  recalled, a lapsed domain would let its next owner publish a different
  definition at the exact URI issued statements name. A repository URL is held
  by an account rather than by a renewal, so its worst case is a dead link,
  which the spec permits. Done now because nothing has been issued yet: after
  the freeze it would have cost the meaning of every certificate already
  carrying the old value.
- **`akashi explain` — one finding, in full, from the report and nothing else.**
  The segment, every particular, where each resolved, what the source says
  instead and why, and what the verdict means in the contract's own words.
  `--particular` narrows further; an unknown id is refused with the ids that
  exist; a bare report and an in-toto Statement are read alike. It takes no
  package and no response, which is how *a report is a document*
  ([ADR-0002](docs/adr/0002-the-audit-report-is-a-document.md)) gets exercised
  rather than repeated — and it ends by saying **which offsets a reader can
  check and which they cannot**, since an offset into a source document is an
  assertion to anyone who does not hold that document.
- **`--restored-by` is recorded even when the package declares no protection.**
  It was silently dropped: the report came back byte-identical to one made
  without the flag, so a caller who had asserted a restoration had recorded
  nothing and believed otherwise. The docstring called that *harmless and
  pointless* and it was neither — **the package does not always know.** A
  redactor that ran *after* the package was built cannot appear in
  `provenance.protection`, which makes that branch exactly where a real claim
  arrives. akashi still checks nothing: the claim goes on the report attributed
  to whoever made it ([ADR-0013](docs/adr/0013-a-restoration-akashi-did-not-watch-is-a-claim.md)).
- **Every printing command crashed on a Japanese console.** `audit`, `eval` and
  `explain` all raised `UnicodeEncodeError` on `cp932` — what a reader gets by
  typing `akashi` without setting anything — because akashi's own headings
  carried an em dash. akashi's prose is ASCII now, and the CLI asks its streams
  for `errors="replace"` so that text akashi *did not write* degrades instead of
  losing the audit. Not `encoding="utf-8"`: that makes the characters
  representable and the terminal decodes them as `cp932` anyway, turning the
  Japanese akashi most often prints into mojibake.
- Three ADRs written while building, each correcting something the pre-code
  design got wrong: [0011](docs/adr/0011-the-script-is-decided-at-the-boundary.md)
  (the script is decided per boundary, not per document),
  [0012](docs/adr/0012-an-omission-is-a-receipt-not-a-source.md) (an omission
  carries no text, so it can never be searched) and
  [0013](docs/adr/0013-a-restoration-akashi-did-not-watch-is-a-claim.md) (the
  absence of a placeholder is not evidence of restoration).
- The design: [`docs/proposals/0001-the-design.md`](docs/proposals/0001-the-design.md),
  written before any code and left as written afterwards.
- Fifteen architecture decision records, [`docs/adr/`](docs/adr/README.md).
  ADR-0004 — the particular is the unit of verification — is the one the rest is
  arranged around.
- The conceptual model, [`docs/concept.md`](docs/concept.md).
- Tooling: `ruff`, `mypy --strict`, six `import-linter` contracts, `pre-commit`,
  and a CI workflow whose `dependencies` job asserts that the runtime dependency
  count is zero.
