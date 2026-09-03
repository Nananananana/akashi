# akashi（証）

**Local-first response auditing for generative AI.** Take the answer a model gave
you and the context it was given, and separate what the answer took from its
evidence from what it produced on its own — deterministically, offline, with no
model in the path and nothing installed alongside it.

> **Status: v0.1 through v0.4, and v0.5 in progress.** `akashi audit` works;
> `akashi recheck` re-derives a report from the inputs it names; `akashi
> explain` prints one finding in full from the report alone; `akashi
> certificate` renders a report as one self-contained HTML file for somebody
> who will sign it; `akashi eval` measures against a labelled corpus and nine
> hand-marked realistic answers, gated on floors; `akashi doctor` says what is
> installed and what this console will do to prose and to a document; `akashi
> mcp` speaks MCP over stdio, for the assistant that produced the answer rather
> than a person at a terminal. Nothing is released and the API is not stable.
> [`docs/measurements.md`](docs/measurements.md) is what it currently scores;
> [`docs/proposals/0002-what-building-it-taught.md`](docs/proposals/0002-what-building-it-taught.md)
> is the rest of the roadmap.

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

```bash
akashi audit --package package.json --response answer.txt
```

Real output, from the fixtures in this repository:

```text
akashi — 3 segments, 0 not checked, 4 particulars checked, 75% grounded

Not checked
  no rule covers: proper_noun

Findings
  seg_003  floating
    The cap was raised in 2025.
    2025  [134:138]  is in none of the text that was sent

Traced
  seg_001  30 days  [31:38]  -> contracts/2024-msa.md (Termination)[4164:4171]
  seg_001  Section 4(b)  [59:71]  -> contracts/2024-msa.md (Termination)[4120:4132]
  seg_002  45,000 dollars  [96:110]  -> contracts/2024-msa.md (Liability)[8844:8858]

Coverage
  3 segments: 3 bearing, 0 unbearing, 0 unexamined; 4 of 4 particulars checked
  3 of 4 particulars grounded (75%)
```

It leads with what was **not** checked and ends with what the report does not
establish. That is a deliberate reversal of what every dashboard in this
category does, and it is why the page can be handed to a reviewer.

## What it will not tell you

Said before what it will, because the boundary is the product.

- **Not whether the answer is true.** A `grounded` particular means the string is
  where the model implies it is. A model can quote your documents perfectly and
  reason from them disastrously.
- **Not the subtle cases.** A sentence whose meaning was reversed without changing
  any particular passes. A sentence assembled from two documents, each quoted
  correctly, passes. These are named on every report rather than left for you to
  discover.
- **Not causal faithfulness.** Whether the cited passage actually *influenced*
  what the model wrote is a stronger claim than akashi makes, and measuring it
  needs the model's internals. akashi never runs a model, so it never will.
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

## Settings

Where the tools around it look, in the order they look:

```text
--matcher / --language        the command line
AKASHI_MATCHER, AKASHI_LANGUAGES, AKASHI_FAIL_ON_FINDINGS
akashi.toml                   [top level]
pyproject.toml                [tool.akashi]
                              akashi's own defaults
```

```toml
# pyproject.toml
[tool.akashi]
matcher = "normalized"        # or "exact"
languages = ["ja", "en"]
fail_on_findings = true
```

**Both of the first two reach `report_id`.** That is what makes a configuration
file safe to read here: a run configured one way cannot be mistaken for a run
configured another, and `akashi doctor` prints what was resolved *and which file
or variable it came from*. A setting three directories up that quietly changed
an audit, with nothing on either report to say why, is the failure this whole
project is about.

A key akashi does not read is **refused**, not ignored — a typo in a
configuration file is a setting somebody believes is in force.

`MAX_RUN` and `MAX_DEPTH` are deliberately not settings. They are bounds akashi
states about its own cost on input somebody else chose, and a file that could
raise them could reintroduce what they exist to stop.

## For an agent rather than a person

The thing that most wants an audit is the assistant that just produced the
answer, holding the package it was given. `akashi mcp` speaks MCP over stdio,
on the standard library, so it costs no dependency and reaches no network:

```json
{
  "mcpServers": {
    "akashi": { "command": "akashi", "args": ["mcp"] }
  }
}
```

Three tools -- `audit`, `recheck`, `explain` -- over the same use cases as the
commands above. **They take text and objects, never paths.** The command line
opens a file the user named, because the user is the person holding the files;
here the model chooses the arguments, and a tool that opened a path would be a
file-read primitive with an audit report as the channel out.

## Where it sits

Six libraries, each standing alone. akashi is the last one, and the only one
that reads what the others produced rather than producing for them.

```text
   your exports, your folders          your photo library
              |                                  |
        [ musubi ]                          [ kiseki ]
   documents/ + traces/            kiseki-interest-export/1
              |                                  |
              +----------------+-----------------+
                               |
                         [ tsumugi ]
                 selection -> what was sent, what was withheld
                               |
                    tsumugi.context-package/1
                               |
                        [ iriguchi ]
              decides where this prompt is allowed to go
              +----------------+-----------------+
              |                |                 |
          REFUSED        local model         ESCALATED
        nothing runs    on this machine           |
                                            [ mamori ]
                              pseudonymized on the way out,
                                 restored on the way back
                                                  |
                                        ( external model )
                                                  |
     +--------------------------------------------+
     |                                            |
 the answer                       tsumugi.context-package/1
     |                                            |
     +---------------------+----------------------+
                           |
                 ##########################
                 #        akashi          #   <- you are here
                 #  which particulars are #
                 #  in the text that was  #
                 #  sent, and which are   #
                 #  in none of it         #
                 ##########################
                           |
                akashi.audit-report/1-draft
                           |
                     (no consumer yet)
```

**None of the others is required.** akashi reads a ContextPackage as JSON and
imports `tsumugi` nowhere, so it audits answers from any pipeline that can emit
one — the shape of the document is the whole interface. `mamori` is reached
through an optional adapter that imports nothing, so akashi installs and runs
without it; a caller who holds a session hands it over.

**The last arrow is a dead end, deliberately drawn as one.** Nothing in the
other five repositories reads `akashi.audit-report/1-draft` today — measured, not
assumed. That is also why the contract still says `-draft`: it freezes when a
second program has **produced and consumed** a report and found something the
schema could not say, and that has not happened
([ADR-0002](docs/adr/0002-the-audit-report-is-a-document.md)).

- [`kiseki`](https://github.com/Nananananana/kiseki) — a local-first personal
  context engine
- [`musubi`](https://github.com/Nananananana/musubi) — local-first ingestion;
  every character still knows which byte of which original file it came from
- [`tsumugi`](https://github.com/Nananananana/tsumugi) — local-first context
  infrastructure; selects what bears on the question and says what it left out
- [`iriguchi`](https://github.com/Nananananana/iriguchi) — a local-first
  governance router; decides where each prompt may go, before anything leaves
- [`mamori`](https://github.com/Nananananana/mamori) — a local-first privacy
  layer; detects and pseudonymizes secrets before they reach an external model

## Documentation

| | |
|---|---|
| [The concept](docs/concept.md) | What akashi asks, and why that question and not the obvious one |
| [The roadmap](docs/proposals/0002-what-building-it-taught.md) | What building it taught, and the plan that follows |
| [The original design](docs/proposals/0001-the-design.md) | Written before any code, left as written. Parts of it are wrong and `0002` says which |
| [The report contract](docs/audit-report.md) | `akashi.audit-report/1`, for producers and consumers |
| [What it scores](docs/measurements.md) | Every number, with the command that produced it and what it does not say |
| [The corpus](docs/evaluation-corpus.md) | The labelled dataset, its plants, and what it cannot tell you |
| [Decisions](docs/adr/README.md) | Thirteen ADRs, each with what it costs |
| [Documentation map](docs/README.md) | Which document is current state, which is history, which is a plan |

## License

Apache-2.0. Python 3.12+.
