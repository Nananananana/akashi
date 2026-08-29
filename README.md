# akashi（証）

**Local-first response auditing for generative AI.** Take the answer a model gave
you and the context it was given, and separate what the answer took from its
evidence from what it produced on its own — deterministically, offline, with no
model in the path and nothing installed alongside it.

> **Status: design.** Nothing is built yet. This repository currently contains
> the design, the decisions behind it, and the tooling that will enforce them.
> Start with [`docs/proposals/0001-the-design.md`](docs/proposals/0001-the-design.md).

---

## The problem

Deciding what to send a model is solved infrastructure. Checking what comes back
is not — and the standard answer is to ask another model, which produces a number
that changes when the judge changes, on a document somebody already filed.

akashi does not ask a model anything. It asks one question with an exact answer:

> **Which particulars of this answer occur in the text that was actually sent,
> and where?**

A *particular* is a load-bearing token — a quantity, a date, a name, a dosage, an
article number, a unit. Those are the things that get falsified in the failures
that cost money, and a string is either in the source or it is not.

```text
テントは 2.6kg で、前回より 300g 軽い。
        ~~~~~                ~~~~
        floating             grounded  → notes/design/gear.md:1240
        contradicted: the source says 2.4kg, at notes/design/gear.md:1204
```

## What it will not tell you

Said before what it will, because the boundary is the product.

- **Not whether the answer is true.** A `grounded` particular means the string is
  where the model implies it is. A model can quote your documents perfectly and
  reason from them disastrously.
- **Not the subtle cases.** A sentence whose meaning was reversed without changing
  any particular passes. A sentence assembled from two documents, each quoted
  correctly, passes. These are named on every report rather than left for you to
  discover.
- **Not a guard rail.** akashi runs after the answer exists. It reports; it does
  not block or rewrite.

Every report carries its own blind spots — what was skipped, why, and what the
denominator was. A partial check whose boundary is printed on the artefact is
worth more than a total check whose confidence cannot be examined.

## Design in four lines

- **Zero runtime dependencies.** An auditor with a supply chain is not an
  auditor. Checked in CI by installing without extras and asserting nothing came
  along ([ADR-0001](docs/adr/0001-the-domain-depends-on-nothing.md)).
- **No model at audit time, ever.** Same inputs, same report, byte for byte, this
  quarter and next ([ADR-0003](docs/adr/0003-an-audit-is-reproducible.md)).
- **The report is a document**, versioned JSON, complete on its own, re-derivable
  by anyone who has the inputs ([ADR-0002](docs/adr/0002-the-audit-report-is-a-document.md)).
- **The world is what was sent**, not the corpus. A figure the model guessed that
  happens to exist somewhere in your archive is still floating
  ([ADR-0006](docs/adr/0006-audit-against-what-was-sent.md)).

## Where it sits

```text
[ kiseki ]   personal context, as facts / measures / interpretations
     ↓
[ tsumugi ]  selection ➔ a ContextPackage: what was sent, what was withheld
     ↓
[ mamori ]   pseudonymization ➔ out to the model, restoration on the way back
     ↓  (the answer)
[ akashi ]   ➔ which particulars are traceable, and which are floating
```

Four libraries, each standing alone, none importing another except through an
optional adapter behind a published contract. akashi reads a
[ContextPackage](https://github.com/Nananananana/tsumugi/blob/main/docs/context-package.md)
as JSON and imports `tsumugi` nowhere, so it audits answers from any pipeline
that can emit one.

- [`kiseki`](https://github.com/Nananananana/kiseki) — a local-first personal
  context engine
- [`tsumugi`](https://github.com/Nananananana/tsumugi) — local-first context
  infrastructure
- [`mamori`](https://github.com/Nananananana/mamori) — a local-first privacy
  layer

## Documentation

| | |
|---|---|
| [The concept](docs/concept.md) | What akashi asks, and why that question and not the obvious one |
| [The design and the roadmap](docs/proposals/0001-the-design.md) | The whole plan, and what would falsify it |
| [Decisions](docs/adr/README.md) | Ten ADRs, each with what it costs |
| [Documentation map](docs/README.md) | Which document is current state, which is history, which is a plan |

## License

Apache-2.0. Python 3.12+.
