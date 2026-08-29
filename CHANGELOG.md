# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Nothing has been released. The public API is not stable and there is no public
API yet.

## [Unreleased]

### Added

- The design: [`docs/proposals/0001-the-design.md`](docs/proposals/0001-the-design.md),
  written before any code and left as written afterwards.
- Ten architecture decision records, [`docs/adr/`](docs/adr/README.md). ADR-0004
  — the particular is the unit of verification — is the one the rest is arranged
  around.
- The conceptual model, [`docs/concept.md`](docs/concept.md).
- Tooling: `ruff`, `mypy --strict`, five `import-linter` contracts, `pre-commit`,
  and a CI workflow whose `dependencies` job asserts that the runtime dependency
  count is zero.
