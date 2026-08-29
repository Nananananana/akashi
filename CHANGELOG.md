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
- Three ADRs written while building, each correcting something the pre-code
  design got wrong: [0011](docs/adr/0011-the-script-is-decided-at-the-boundary.md)
  (the script is decided per boundary, not per document),
  [0012](docs/adr/0012-an-omission-is-a-receipt-not-a-source.md) (an omission
  carries no text, so it can never be searched) and
  [0013](docs/adr/0013-a-restoration-akashi-did-not-watch-is-a-claim.md) (the
  absence of a placeholder is not evidence of restoration).
- The design: [`docs/proposals/0001-the-design.md`](docs/proposals/0001-the-design.md),
  written before any code and left as written afterwards.
- Thirteen architecture decision records, [`docs/adr/`](docs/adr/README.md).
  ADR-0004 — the particular is the unit of verification — is the one the rest is
  arranged around.
- The conceptual model, [`docs/concept.md`](docs/concept.md).
- Tooling: `ruff`, `mypy --strict`, five `import-linter` contracts, `pre-commit`,
  and a CI workflow whose `dependencies` job asserts that the runtime dependency
  count is zero.
