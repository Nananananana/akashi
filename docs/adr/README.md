# Architecture decision records

One file per decision that changed a boundary, a default, or a guarantee. Each
says what the situation was, what was chosen, what follows from it, and — the
part that is usually missing — **what it costs**.

A decision recorded before the code exists is still a decision. These were made
while refining the design, and they are why the design looks the way it does.
What is *intended* next lives in [docs/proposals](../proposals/0001-the-design.md)
instead; an ADR records a decision already taken, and a plan is neither.

An ADR is never edited to match the present. When a decision stops holding, a
later ADR supersedes it and says so.

| # | Decision |
|---|---|
| [0001](0001-the-domain-depends-on-nothing.md) | The domain layer imports only the standard library |
| [0002](0002-the-audit-report-is-a-document.md) | The audit report is a document, not a type |
| [0003](0003-an-audit-is-reproducible.md) | An audit is reproducible, and no model runs inside one |
| [0004](0004-the-particular-is-the-unit-of-verification.md) | The particular is the unit of verification |
| [0005](0005-say-what-could-not-be-checked.md) | Say what could not be checked, on every report |
| [0006](0006-audit-against-what-was-sent.md) | Audit against what was sent, not against the corpus |
| [0007](0007-read-the-producer-through-its-contract.md) | Read the producer through its contract, and import nothing |
| [0008](0008-restore-before-you-audit.md) | Restore before you audit, or refuse |
| [0009](0009-segment-by-script-and-record-the-segmenter.md) | Segment by script, and record the segmenter on the report |
| [0010](0010-label-the-response-not-the-ideal-answer.md) | Label the response, not the ideal answer |
| [0011](0011-the-script-is-decided-at-the-boundary.md) | The script is decided at the boundary, not for the answer |
| [0012](0012-an-omission-is-a-receipt-not-a-source.md) | An omission is a receipt, not a source |

[0004](0004-the-particular-is-the-unit-of-verification.md) is the one to read
first. The rest of the design is arranged around it, and
[0005](0005-say-what-could-not-be-checked.md) is what makes it honest.

Several are borrowed, with thanks, from the sibling projects `mamori`, `kiseki`
and `tsumugi`. Where that is the case the ADR says so and names the original: a
decision someone else already paid for is worth taking, and worth attributing.
