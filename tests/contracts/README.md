# Vendored contracts

Contracts published by other projects, and the documents that instantiate them,
copied here so that akashi can be tested against the real thing without
installing anything.

| File | Source | Licence |
|---|---|---|
| `context-package-1.json` | [`tsumugi`](https://github.com/Nananananana/tsumugi), `schemas/context-package-1.json` | Apache-2.0 |
| `context-package-seam.json` | [`tsumugi`](https://github.com/Nananananana/tsumugi), `fixtures/seam/context-package.json` | Apache-2.0 |

They are a pair and they answer different questions. The schema says what the
shape **may** be; the fixture is one instance of it that the producer really
produced. A consumer needs both, because a schema is satisfied by documents
nobody emits and contradicted by none that they do.

## One invariant lives in the reader, because it cannot live in the schema

JSON Schema 2020-12 cannot compare two properties of the same object, so
**`end >= start` on an anchor is not expressible** and a reversed anchor
validates cleanly. `tsumugi` refuses to construct one, so no real package
carries it — but a producer's invariant is not a consumer's guarantee, and
`infrastructure/packages/contextpackage.py` keeps its own copy of this check.

That check is not redundant with schema validation and must not be removed on
the grounds that every fixture here validates. That is what it is for.

[`upstream.json`](upstream.json) records, for each file, the repository, the
path, the commit it was taken at, its `sha256` and the date. That file is the
provenance; this one is the explanation.

These are **test material, not runtime material**. Nothing under `src/` reads
them: akashi's reader checks the contract field itself, in plain Python,
because a consumer validating a package should not need a package in order to
do it (ADR-0001). What these are for is the other direction — proving that the
fixtures akashi tests against are documents `tsumugi` would actually produce.

## A copy fails in two ways, and they need different checks

**It can be edited here.** Loosening a `required` to make a fixture pass would
leave akashi conformant to a contract nobody published, with every conformance
test in the repository green and saying nothing. `tests/test_vendored_contracts.py`
hashes each copy against `upstream.json` on every run, offline. Vendored
contracts are copies, not forks: to change one, change it upstream and refresh.

**It can go stale there.** The producer tightens the schema and this copy does
not move. Nothing local can see that, so the check has to ask upstream. It is
marked `network`, deselected from the default run, and has its own CI job:

```bash
python -m pytest tests/test_vendored_contracts.py -m network
```

A **404 fails rather than skips.** The recorded `path` is where a refresher
would look, and if it is not there the producer has reorganised — which is drift
of the most consequential kind. Everything else the server can say (a rate
limit, a bad gateway) is about the server and skips. That distinction was
written after the check skipped on exactly the thing it exists to catch.

Upstream having moved is *information*, not a defect in whatever change is
being reviewed — so that job runs on a schedule and on demand rather than
gating every pull request. A check that blocks unrelated work is a check that
gets disabled.

## Refreshing one

1. Copy the new file over the old one.
2. Update `commit`, `sha256` and `retrieved` in `upstream.json`.
3. **Read the diff.** The hash going green again is not evidence that akashi
   still conforms; it is only evidence that the copy is current.

## The fixture

`context-package-seam.json` is what `tsumugi context --json` emits for a fixed
corpus and a fixed question. Its `created_at` is pinned by the producer — it is
the one field deliberately excluded from `package_id`, which is what makes
pinning it honest — so the whole document compares and nothing is skipped.

It is deliberately wider than the happy path: two items **and an omission**, a
superseded passage carried rather than dropped, and `protection: null` rather
than absent. `tests/test_seam_tsumugi.py` is what reads it, and each of those
three is a test in there.

Regenerate it upstream with `python tools/make_seam_fixture.py`; pin the
timestamp with `tsumugi context --json --at <ISO8601>`.
