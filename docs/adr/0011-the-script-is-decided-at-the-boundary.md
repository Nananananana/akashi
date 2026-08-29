# 11. The script is decided at the boundary, not for the answer

**Status:** accepted

Refines [ADR-0009](0009-segment-by-script-and-record-the-segmenter.md), which
said segmentation rules are "selected per script". They are — just not per
document, and the difference turned out to matter enough to write down.

## Context

ADR-0009 was written before the segmenter existed, and it left the selection
step unspecified in a way that reads as: detect the script of the text, choose
the pack for that script, segment with it.

Implementing it showed the flaw. Consider a real answer:

```text
テントは軽い。The tent is light. 重さは 2.4kg。
```

The dominant script is Japanese. Under per-document selection the Japanese pack
is chosen, its terminator set is `。！？．`, and `The tent is light.` never ends
— it merges into the following segment. One verdict then covers two sentences,
which means one floating particular condemns a grounded one, and the report
points a reader at a span that is twice the size of the finding.

This is not an edge case. A model answering a Japanese question about a
technical corpus quotes English terms, product names and whole English
sentences from the sources, because the sources do. The same is true in the
other direction, and the same is true of Chinese.

Detecting the script per *paragraph* moves the problem without solving it — the
example above is one paragraph. Detecting it per sentence is circular: sentence
boundaries are what is being computed.

## Decision

**A language pack claims terminator characters, and a boundary is decided by
whichever pack claims the character in front of it.**

The packs are merged once into a map from terminator to behaviour. `。` comes
with "no space needed after"; `.` comes with "a space is needed, and here is
the abbreviation list". Every pack is loaded, always; there is no selection
step and therefore no selection to get wrong.

Two packs may claim the same character — `。`, `！` and `？` are Japanese and
Chinese both — and where they do, **they must agree about how it behaves.** A
disagreement is refused at construction rather than resolved by load order,
because an answer that depended on which pack was imported first would not be
reproducible (ADR-0003). Abbreviation lists are unioned instead, since those are
per-language vocabulary attached to a shared character rather than a claim
about the character itself.

Script detection survives, with a narrower job: it labels each segment for
reporting, so that metrics can be broken down per language (ADR-0010). Nothing
in segmentation depends on its answer.

## Consequences

Mixed-script answers segment correctly, and they are the ordinary case rather
than the exception.

The caller has nothing to configure. A `--language` flag would be a flag that is
wrong by default in exactly the answers this project exists for.

Adding a fourth language cannot break the other three: it contributes
terminators, and a terminator it does not claim behaves as it did before.

## What it costs

Every terminator's rules run on every answer, including the English
abbreviation list on a document with no English in it. The cost is a set
lookup per candidate boundary and is not measurable next to anything else in an
audit.

A character that genuinely means different things in two scripts could not be
expressed. None of the three languages has one, so the constraint is currently
free — and the refusal in `_rules` is what makes it a loud problem rather than a
quiet one if a fourth language brings one.

`script_of` reads kana as decisive, so a Japanese sentence written entirely in
kanji is labelled Chinese. That is a reporting error and not a segmentation
error, it is visible in the per-language breakdown, and fixing it would need
either a dictionary or a model. Both are refused (ADR-0001, ADR-0003), so it is
stated instead.
