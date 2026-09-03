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
- **`empty_parameter_set_mark = "fail_at_collect"`.** pytest's default marks an
  empty parameter set as a **skip** -- the same sentence akashi wrote by hand
  and was caught by, except nobody wrote this one. Point a discovery constant at
  a renamed directory and every rule parametrized over it collects nothing and
  stays green. Measured on akashi's own architecture tests: with the setting,
  one collection error; without it, five silent skips, same code. akashi's
  `_modules()` already refuses at collection time so nothing changes today,
  which is why it is set now rather than after the next one. Found by
  `iriguchi` (#44).

- **A guard that sat behind the mistake it was written for.** Passing a
  `mamori` session to `audit(restorer=...)` **without** the adapter raised
  `TypeError: expected string or bytes-like object` four frames in, out of a
  regular expression. The adapter carried a message about exactly that case --
  and only a caller who had already wrapped their session could ever read it.
  The check is now in `admit`, in front of the thing it guards, and names the
  wrapper rather than only refusing. Found by the seam repository running the
  real chain; neither akashi's unit tests nor its own seam test had a caller
  who passed the session raw.

- **`--restored-by` is not a lesser `restorer`.** A restorer is a live object
  holding a mapping and argv carries names, so it is the only restoration the
  command line can reach -- and the report says *asserted* because that is the
  truth of what happened. The help now says where the boundary is, because the
  seam repository read the two report lines as better and worse and went looking
  for a flag that does not exist.

- **The seam against the real redactor (#59).** A CI job installs `mamori` by
  pinned git reference and runs the adapter against the library rather than
  against a reading of it. Every claim #76 made from a stand-in holds against
  the class: `isinstance(session, Restorer)` is **True**, `restore` returns a
  `RestorationResult`, and without the adapter the failure is
  `TypeError: expected string or bytes-like object` from inside a regular
  expression, three layers from the mistake.

  Four ways the job could have been green and proved nothing, three of them
  observed in sibling repositories, are closed and each is watched failing:
  the direct reference lives in a **step** and never in `pyproject.toml` (one
  line of it in an extra makes the whole distribution unpublishable); identity
  is checked through PEP 610's `direct_url.json`, so an index install fails
  rather than passing; `continue-on-error` is on no step and no job; and the
  seam file imports `mamori` at the top, so absence is an error and not a skip.

  **`mypy` catches what `runtime_checkable` does not.** Type-checking the real
  library through that file gives *"Subclass of `PrivacySession` and `Restorer`
  cannot exist: would have incompatible method signatures"*. The mismatch is
  statically visible; only the runtime check says yes -- which makes
  `runtime_checkable` worse than no check here, since it answers the question a
  reader asked with the answer to a narrower one.

  A marker was not enough on its own: markers deselect at *selection* time and
  collection happens first, so the file is also gated out of collection. The
  job cannot pass by collecting nothing either -- `pytest -m siblings` exits 5
  on an empty set.

- **A test of akashi's own that would have passed having read nothing.**
  `test_the_adapter_imports_nothing` walked `adapters/*.py` and asserted only
  inside the loop, so a renamed package makes it green with zero modules read.
  It now checks its population first, and a scan of every test file for that
  shape is a test -- narrowed to loops over what the *filesystem* handed back,
  which is the collection that silently becomes empty.

  Same family as the skipping guard above, different spelling: `for x in []`
  spells an empty population *"all passed"*, `if not found: skip` spells it
  *"not applicable"*. Reported by the cross-repository review, which found
  fourteen in another project. akashi's architecture tests were already safe --
  `_modules()` refuses at collection time -- and pointing `SRC` at a renamed
  directory was measured to confirm it rather than assumed.

- **What akashi cannot decide about a placeholder, said out loud (#52).**
  `<PERSON_001>` is a string a person can type, and akashi cannot tell a token a
  redactor minted from one an author quoted. The refusal now names the limit and
  the way out rather than only saying no.

  **#52 asked for a mechanism that its own companion contract has since ruled
  out.** It said to branch on `mode`, because `placeholders` was absent under
  `surrogate`. `mamori.protection-scope/1` now makes `placeholders` **required**
  and says `mode` is *"a summary of how values were substituted, **not a switch
  selecting which array to read**"* -- the signal is the contract identifier,
  `/1` against `/1+surrogate`. Implementing #52 as written would have built the
  exact misreading that contract is worded to prevent.

  And it is not decidable here at all: the enumeration would have to reach
  akashi through `tsumugi`'s `provenance.protection`, which carries three fields
  with `additionalProperties: false` in a version that is now closed. A test
  pins that premise, so a v2 that carries it reopens the question instead of the
  reasoning quietly going stale.

- **The document rule is now structural rather than remembered.** *Prose
  degrades, a document does not* held today because every document path was
  found and changed by hand; a fourth one -- a new `--json`, a new export --
  would be written as `print(json.dumps(...), file=out)` and would go out in the
  console's encoding on the machine that has one, with every test passing. A
  test walks the CLI's AST and requires a serialized document to reach the
  caller through `_document` or not at all.

  Prompted by the cross-repository review's third column: **structural** (you
  cannot break it without deleting code), **disciplined** (a person is keeping
  it), **accidental** (true, and nobody designed or maintains it). This rule was
  in the second column and is now in the first.

- **Which strings count as the same string is a choice now, and it has a
  name.** `domain/matching.py` answered the question the whole audit turns on
  and never said which answer it gave. `audited.matcher` names it, `--matcher`
  and the MCP `matcher` argument select it, and **it is in `report_id`** — for
  the same reason the language packs are: it changes every count, and two audits
  that answered differently must not be able to carry one id. `recheck`
  re-derives with the matcher the report *names*, not with whatever the process
  defaults to.

  Two ship, and the second is not decoration — a port with one implementation is
  a port nobody has tried to satisfy, which is what `Restorer` taught (#76).
  `normalized` is the default and what every published number was measured with;
  `exact` applies the same boundary rules with no spacing tolerance. Both fold
  the text: turning that off as well would report a full-width `２.４kg` against
  a half-width one as fabricated, which is not stricter but broken.

  **And the corpus cannot tell them apart.** Over all 30 cases they ground
  identically, particular for particular. The evidence holds 45 quantities
  written with a space and no answer ever re-spaces one, because the generator
  quotes the evidence verbatim — so the tolerance this module argues for at
  length is worth nothing any published number measures. A test asserts the
  agreement so the gap is visible, and says to delete itself when the corpus
  grows the case.

- **Two particulars did not resolve back into the text they were extracted
  from.** Found by the round-trip property test, both pre-existing, both the
  same shape — a comma between digits that reads as a thousands separator and is
  not. It is the dangerous direction: akashi reporting an honest citation as
  fabricated.

  ```text
  2026-08-30，300g   the `30` before the comma is a day, so `30,300` is no number
  45,000，300g       the number's separator is half-width and the pause full-width;
                     NFKC folded both to `,` and lost the author's own distinction
  ```

  `_is_number_tail` reads what is in front of the run before calling it a
  number. `_same_width` requires a separator to have been written the way the
  digits around it were — so a fully full-width `４５，０００` still binds, and a
  half-width number beside a full-width pause does not. Both counterexamples are
  pinned as `@example`, captured as strings before the tests were touched, per
  the rule added with #60.

- **A deeply nested document reached the user as a traceback, and killed the
  MCP server.** `json.loads` recurses; a `RecursionError` is not a
  `json.JSONDecodeError`, so it went past every reader akashi has. On the CLI it
  printed a traceback — which akashi's own rule calls the wrong answer, because
  a traceback reads as a bug in the tool rather than as a fact about the file.
  On the MCP surface the exception left the request generator, left the loop and
  **ended the process**: stdout empty, no reply, no reason. That loop exists so
  that one bad message is not the end of a session.

  `infrastructure/documents.py` counts nesting depth before parsing rather than
  catching the failure after. Catching would depend on a recursion limit a
  caller can change and on a C stack that differs by build — and where the stack
  runs out first there is no exception to catch. Counting is arithmetic: it
  cannot exhaust anything and gives the same answer everywhere, which an audit
  needs (ADR-0003).

  `MAX_DEPTH = 64`, set the way a floor is: the deepest JSON in this repository
  is **10** (the two published schemas) and a real package is **5**.

- **Extraction was quadratic in the length of an answer, and the answer is
  text somebody else wrote.** akashi audits what a model produced and `akashi
  mcp` lets the model choose the arguments, so the length and shape of an answer
  are attacker-controlled. Measured end to end:

  ```text
  16,000 characters of ordinary prose    0.09 s
  16,000 characters of digits           38.09 s     x4.0 per doubling
  ```

  Quadratic to three digits, across five sizes — 420x the cost of prose the same
  length, and an hour at ten times the length. The cause is the ordinary
  "long prefix matches, short suffix fails" shape: `\d[\d,.]*\d` followed by a
  unit that is not there. Read with `re`'s own parser, **32 of the 40 shipped
  rules** have an unbounded repetition.

  `MAX_RUN = 256` bounds every repetition at compile time — **a bound and not a
  timeout**, because an audit is reproducible (ADR-0003) and a run that gives up
  after a second gives a different report on a slower machine. Set the way a
  floor is: the longest particular in the corpus is 21 characters.

  ```text
  unbounded repeats   102 -> 0        particulars from the corpus   412 -> 412 identical
  16,000 digits       38.09 s -> 1.60 s, and linear
  ```

  Every measured score is unchanged. The structural test reads what `_compiled`
  actually produces rather than what the helper would return — written the other
  way round first, and unwiring the bound left it green.

- **The family diagram, with an honest dead end (#48).** Counting mentions
  across the six repositories, the `iriguchi` column was entirely zero: it
  referenced `mamori` 36 times and nothing referenced it. The library named
  *entrance* was the one nobody could see, and it is the first thing a prompt
  touches. akashi's README now draws all six, its own box heavily.

  **The last arrow is drawn as a dead end because it is one.** Nothing in the
  other five repositories reads `akashi.audit-report/1-draft` -- measured across
  their `src/` trees, not assumed -- which is the same fact as the contract
  still saying `-draft` (ADR-0002's freeze condition is a second program that
  has produced *and consumed* a report).

  Every label was checked against the sibling's code rather than copied from
  the proposal. The cross-repository review had just found three arrows in its
  own diagram that named a contract nobody writes or reads, one of them
  justified by a diagram in another README that carried the same arrow.

- **`akashi mcp`, the agent-facing surface.** JSON-RPC over stdio on the
  standard library -- which is not a preference: ADR-0001 forbids a runtime
  dependency and the import-linter contract forbids `socket`, `http`, `urllib`
  and `asyncio`, all of which an MCP SDK brings. Three tools -- `audit`,
  `recheck`, `explain` -- as thin over `akashi.application` as the CLI is.

  **It takes no paths.** The CLI opens a file the user named, because the user
  is the person holding the files; here the *model* chooses the arguments, and a
  tool that opened a path would be a file-read primitive with a report as the
  channel out, since a report quotes the answer verbatim. Read-only, checked by
  taking the filesystem away and calling a tool.

  Speaks the **2026-07-28** revision -- stateless, no handshake, every request
  carrying its version in `_meta`, every result naming its `resultType` -- and
  also answers `initialize`, because the specification's own compatibility
  matrix says a legacy client against a modern-only server *fails with no
  fall-forward*, and most clients shipped today are legacy. Every protocol fact
  was read from the specification rather than inferred from a client that
  happened to work.

  The transport binds UTF-8 both ways with `errors` left strict. Third place
  today's rule applied: prose degrades, a document does not, and a `?` in a
  protocol message is corruption.

- **`akashi doctor`, and the schema moved to where one route reaches it
  (#57).** `doctor` reports the running installation: akashi's version, the
  contract it ships and its `sha256`, the language packs, what this console
  will do to prose and to documents, and which siblings are importable. **It
  decides nothing** -- a function returning "healthy" would be a second place a
  verdict comes from, and a reader would take the word instead of the facts. It
  exits non-zero only when something akashi *promised* to ship is absent; a
  missing sibling is a fact about the machine, not a fault.

  It never imports a sibling to report on it -- `find_spec` answers the
  question and runs none of that package's code, which is not something a
  diagnostic should do to a machine its user is already suspicious of.

  `schemas/` moved to `src/akashi/schemas/` and the `force-include` block is
  gone. `force-include` does not apply to an editable install, so the path only
  existed after a real install and nothing local could look at it; one route
  now works in a checkout, an editable install and a wheel. #57 asked for a
  reader before the move, and `doctor` is one.

  **The guard on the old arrangement skipped itself when the directory moved.**
  It began `if not (ROOT / "schemas").glob("*.json"): pytest.skip(...)`, so it
  stopped running the moment its subject changed. Replaced with one that fails.

- **`akashi certificate`.** A report as one self-contained HTML file, for
  somebody who will sign it: the answer with every particular marked where it
  stands, what was not checked first, and `Traced` promoted to the middle of
  the page because that section is what a signer is signing. It reads the
  report and nothing else, and it is a **pure function of it** -- no timestamp,
  no host name -- because a signature is over bytes and a certificate that
  differed between runs would mean a signature over one copy did not verify the
  other. No scripts, no network, no fonts; a test asserts the absence rather
  than the intention. Standing is carried by underline shape and a mark, never
  by colour alone, so the page still says which particulars are grounded when
  it is printed in monochrome. Answers #53: a span into the answer points at
  text on the page, a location points at a document the holder does not have,
  and the certificate says which is which rather than letting a signer assume
  one status for both.

- **`--json` was not UTF-8 on the machine that needed it most.** Redirected on
  a Japanese Windows console, `akashi audit --json > report.json` wrote
  `cp932`: not valid JSON (RFC 8259), refused by `recheck`, `explain` and
  `certificate`, and carrying a `response_hash` taken over UTF-8 bytes the file
  did not contain. **akashi could not read the document akashi had just
  written**, and it had been so since `--json` shipped.

  `_read` had said the rule for input all along -- *UTF-8 either way and never
  the platform encoding* -- and nothing said it for output, so akashi read
  deliberately and wrote by accident. A document now leaves through the buffer
  underneath the stream; prose still goes through the console's encoder, because
  losing a character beats losing the audit and a `?` in a *document* is
  corruption rather than a concession. [`docs/audit-report.md`](docs/audit-report.md)
  now names the encoding as a **pin against repeating this**, not as a repair:
  RFC 8259 §8.1 already required UTF-8 of exchanged JSON and the contract
  already said the report is JSON, so the requirement was in force and akashi
  violated it. (This entry first blamed the contract for being silent.
  `tsumugi` pointed out that it was not, and was right -- the other way round
  excuses the producer, and the producer was akashi.)

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
- **The `mamori` adapter, and the reason it is not zero lines.**
  `ports/restorer.py` said `mamori`'s `PrivacySession` *"already satisfies"* the
  port. It does not: `restore` returns a `RestorationResult`, and the difference
  between an object carrying `.text` and the text is the whole adapter.
  `runtime_checkable` would not have caught it — `isinstance` against a
  `Protocol` checks that the method is **present**, not what it returns — so a
  session passes and akashi runs a regex over the result object three layers
  away. `MamoriRestorer` checks at the seam, where the message can name what
  went wrong, and **imports nothing**: akashi installs and runs without the
  library.
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
