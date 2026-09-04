# akashi（証）

**Find what a RAG answer took from its sources, and what it made up — offline,
in milliseconds, with every finding a byte offset you can open.**

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#install)
[![CI](https://github.com/Nananananana/akashi/actions/workflows/ci.yml/badge.svg)](https://github.com/Nananananana/akashi/actions/workflows/ci.yml)
[![Typed](https://img.shields.io/badge/mypy-strict-blue.svg)](pyproject.toml)

```python
from akashi import evaluate

result = evaluate(
    answer="The tent weighs 2.4kg and the gas is 9.9kg.",
    contexts=["The tent weighs 2.4kg.", "Gas cartridge, 250mg."],
)

result.grounded  # ('2.4kg',)   in the text you passed
result.floating  # ('9.9kg',)   in none of it
result.grounded_share  # 0.5
result.unchecked  # what was skipped, and why
```

No API key. No model download. No network. `pip install akashi` brings **zero
dependencies** and opens **zero sockets** — a CI job checks the built artefact,
not the promise.

That audit takes **0.35 ms**. A hundred-sentence answer against twenty
retrieved chunks takes **56 ms**, on one CPU core, with nothing warmed up.

## See it

```bash
git clone https://github.com/Nananananana/akashi && cd akashi
pip install -e .
python examples/demo.py
```

Six sections, no network, no model, no key. Section 2 is akashi printing the
two cases it gets **wrong**.

## Why another one

Every other tool in this space asks a language model whether the context
entails each claim. That answers a question akashi cannot, and it costs three
things akashi keeps:

| | akashi | RAGAS / DeepEval / RefChecker |
| --- | --- | --- |
| **Reproducible** | same input, same report, forever | a new model version is a new answer |
| **Where** | byte offsets into the exact text you passed | a score |
| **Cost** | milliseconds, no network | a model call per claim |
| **What it misses** | paraphrase (see below) | nothing structural — that is their strength |

**So use both.** `--judge` bolts one of theirs onto one of these, and the two
answers stay in separate sections under separate words, because `grounded` and
`supported` are different claims:

```bash
pip install 'akashi[nli]'      # local entailment, Apache-2.0, no network after the download
akashi audit --contexts sample.json --judge nli
```

## Read this before you quote the number

`grounded_share` is **not a faithfulness score**, and `docs/measurements.md`
prices the difference rather than hedging about it:

| answer | evidence | akashi |
| --- | --- | --- |
| `The tent weighs 2.4kg.` | `The stove weighs 2.4kg.` + `The tent weighs 3.1kg.` | **1.0** ([#83](https://github.com/Nananananana/akashi/issues/83)) |
| `Alice reports to Bob.` | `Bob reports to Alice.` | nothing to check |
| `The tent weighs 2.4 kilograms.` | `Tent mass: 2.4kg.` | **0.0** |

akashi compares strings. A value grounded against the wrong subject scores
perfect, and a correct paraphrase scores zero. That is on every report in
`limits`, it is why `--judge` exists, and it is
[docs/roadmap.md](docs/roadmap.md) item 1.1 rather than a footnote.

## Install

| | brings | needs a network | for |
| --- | --- | --- | --- |
| `pip install akashi` | nothing | no | the audit |
| `pip install 'akashi[nli]'` | transformers, torch, a 600MB model | once | local entailment (`--judge nli`) |
| `pip install 'akashi[claude]'` | the Anthropic SDK | every call | `--judge claude-opus-5` |

## In your test suite

```python
from akashi.testing import assert_grounded


def test_the_summary_quotes_its_sources():
    assert_grounded(answer=summarise(doc), contexts=[doc], at_least=0.9)
```

The failure names every floating particular, what was skipped and why, and the
limits the number was produced under — a red CI job should not be a bare
`assert 0.72 >= 0.9`. `allow_floating=[...]` waives an expected one, and a
waiver for something that **stopped** floating fails too: a suite full of stale
waivers is a suite that has stopped checking.

> **Status: v0.1 through v0.4, and v0.5 in progress.** Nothing is released and
> the API is not stable. [`docs/measurements.md`](docs/measurements.md) is what
> it currently scores; [`docs/roadmap.md`](docs/roadmap.md) is what is next and
> what is deliberately not being done.

---

## The shortest way in

You do not need a ContextPackage, a corpus, or any of the rest of the family.
Three values, the same three every RAG evaluation library takes:

```python
from akashi import evaluate

result = evaluate(
    answer="The tent weighs 2.4kg and the gas is 9.9kg.",
    contexts=["The tent weighs 2.4kg.", "Gas cartridge, 250mg."],
)
result.grounded_share  # 0.5
result.floating  # ('9.9kg',)
result.unchecked  # what was skipped, and why
```

A **RAGAS or DeepEval sample works unchanged** — `evaluate_sample(sample)` reads
`user_input` / `input` / `question`, `response` / `actual_output` / `answer`, and
`retrieved_contexts` / `retrieval_context` / `contexts`. So does the command
line and the MCP tool:

```bash
akashi audit --contexts sample.json
```

**A whole dataset**, which is the shape people actually have:

```python
from akashi import evaluate_samples

results = evaluate_samples(rows)  # RAGAS, DeepEval or plain, mixed
results.describe()
# '0.412 over 1173 particulars in 486 of 500 rows; 2 refused'

import pandas as pd

pd.DataFrame(results.rows())  # akashi does not depend on pandas
```

`rows` can be a list of dicts, a generator, a HuggingFace `Dataset`, or a
`pandas.DataFrame`. Three decisions it makes so a caller does not have to make
them wrong:

- **A DataFrame is read as rows, not as its column names** — which is what
  iterating one actually gives you. Passing a 500-row frame would otherwise have
  audited three strings, refused all three, and returned an empty result whose
  refusals read as though your data was bad.
- **The share counts particulars, not rows.** A mean of per-row shares weights a
  one-particular answer the same as a forty-particular one, and has to decide
  what a row with nothing checkable contributes — and every answer to that is
  wrong. `describe()` says how many rows reached the number.
- **A row akashi refuses is kept as a refusal**, not raised and not dropped.
  One malformed row in five hundred should not lose the other 499, and a run
  reported over 500 rows that audited 499 is the failure this project exists to
  remove. `results.refused` names the index and the reason.

**`grounded_share` is not a faithfulness score.** Every library in this space
reports a 0–1 number by that name, computed by asking a model whether the
context entails each claim. This one is *the share of load-bearing strings in
the answer that occur in the text that was sent* — a different question, and
comparing the two numbers is comparing nothing. `result.limits` says so on the
object; the report says so on the artefact.

**No provenance is invented.** A ContextPackage carries a document, a path and
an offset into a file; a list of strings carries none of that. So the offsets
index the strings you passed, `source_path` stays empty, and the report gains a
line saying it — because a reader who sees `notes/gear.md[1209:1214]` will go and
open that file.

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

## Asking a model about what akashi could not check

akashi decides by comparing strings, so a claim the answer *paraphrased* out of
the evidence comes back `floating` — true, and not what you wanted to know. You
wanted to know whether the evidence supports it.

```bash
pip install "akashi[claude]"
akashi audit --package pkg.json --response answer.txt --judge
```

```text
Judged
  Not akashi verdicts. A model read these and said what it thought.
  seg_003  9.9kg  unsupported  [claude-opus-5]
    the evidence gives 2.4kg for the tent and no other weight.
```

**A judgement is not a verdict, and akashi will not let the two blur**
([ADR-0017](docs/adr/0017-a-judge-annotates-an-audit-it-does-not-make-one.md)):

- akashi says `grounded` / `floating` / `contradicted`; a judge says `supported`
  / `unsupported` / `unclear`. **No word is shared.**
- They never share a section, and **`report_id` does not move** — the same audit
  with and without judgements carries one id, and `recheck` re-derives it with
  no network.
- Every judgement names the model that gave it, and three sentences join
  `limits` saying that it is an opinion and is not reproducible.
- A judge only ever sees what akashi could not settle. It is not shown a
  grounded particular: akashi already knows the string, the document and the
  offset, and replacing a fact with an opinion could only make the report worse.

**`pip install akashi` still installs nothing and reaches nothing.** The SDK is
an extra, the judge is behind `--judge`, and `import akashi` loads no HTTP
client even where the extra is present — checked in CI on a machine that has it.

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
