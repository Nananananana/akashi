# Vendored contracts

Schemas published by other projects, copied here so that akashi's fixtures can
be checked against the real contract without installing anything.

| File | Source | Licence |
|---|---|---|
| `context-package-1.json` | [`tsumugi`](https://github.com/Nananananana/tsumugi), `schemas/context-package-1.json` | Apache-2.0 |

These are **test material, not runtime material**. Nothing under `src/` reads
them: akashi's reader checks the contract field itself, in plain Python,
because a consumer validating a package should not need a package in order to
do it (ADR-0001). What these are for is the other direction — proving that the
fixtures akashi tests against are documents `tsumugi` would actually produce.

A copy can go stale. It is refreshed by hand, and the thing that will catch a
drift for real is the v0.5 seam test, which builds a package with the reference
producer rather than reading one somebody typed.
