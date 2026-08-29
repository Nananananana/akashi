# 1. The domain layer imports only the standard library

**Status:** accepted

Taken, with thanks, from `mamori`'s ADR-0001 and `tsumugi`'s ADR-0001. The
reasoning below is why it is taken again rather than assumed.

## Context

The obvious way to build an auditor in 2026 is to assemble it: a sentence
splitter from one package, an NER model from another, an embedding library for
similarity, a validation library for the report schema. Each is one line in a
`pyproject.toml`, and each arrives with its own transitive tree.

akashi is the component whose entire value is that someone can be told to trust
it. It is offered to law firms, hospitals and patent departments as the thing
that says *this sentence is backed by your document and this one is not*. A
buyer in those industries does not audit akashi. They audit whatever akashi
pulled in, or they do not audit at all — and forty transitive packages is the
second one.

There is a second reason, particular to this project. An auditor that is not
reproducible is not evidence. A dependency that changes its tokenizer in a point
release changes a verdict, silently, on a report someone has already filed.

## Decision

**`domain/` imports nothing but the standard library, and the distribution
declares zero runtime dependencies.**

Development tools — `pytest`, `hypothesis`, `mypy`, `ruff`, `import-linter`,
`jsonschema` — live in the `dev` extra and never in the shipped path.
`jsonschema` in particular validates reports *in the test suite*; the library's
own reader checks the contract field itself, in plain Python, because a consumer
validating a report should not need a package in order to do it.

Two mechanisms enforce it rather than one, because a rule this load-bearing
should not rest on anyone remembering it:

- `tests/test_architecture.py` parses every module in `domain/` and asserts that
  every import resolves to the standard library.
- CI installs the distribution with no extras into a clean environment and
  asserts that nothing else arrived.

## Consequences

The sentence segmenter, the particular extractor, the matcher and the report
serializer are all written here. That is a real amount of code that could have
been imported.

It also means that every one of them is inspectable, and every one of them is
pinned to a version of akashi rather than to whatever resolved that day. The
reproducibility ADR-0003 asks for is achievable because of this, and would not
be otherwise.

## What it costs

No NER model, no embeddings, no learned segmenter. Anything akashi cannot do
with `re`, `unicodedata`, `json` and `difflib` it does not do — and ADR-0004 and
ADR-0005 exist to make sure that boundary is stated to the user rather than
papered over.

An excellent Japanese morphological analyser exists, and akashi will not use it.
The segmenter is therefore worse than the best available, and ADR-0009 records
what that costs and how it is measured.
