"""Asking something that reads about the part akashi could not check.

akashi decides by comparing strings, and the cost of that is stated plainly on
every report: a particular the answer *paraphrased* out of the evidence is
`floating`, which is true -- it is in none of the text that was sent -- and is
not what the reader wanted to know. They wanted to know whether the evidence
supports it.

This asks. And it asks about **exactly the claims akashi could not settle**,
which is the whole design:

**A judge never sees a grounded particular.** akashi already knows where that
string is, in which document, at which offset. Handing it to a model would
replace a fact with an opinion and could only make the report worse.

**A judge never produces a verdict.** Its answers land in `judged[]` under the
name of the model that gave them, in a vocabulary that shares no word with
akashi's own. `grounded` and `supported` are different claims and a reader must
not be able to read one as the other.

**`report_id` does not move.** The id hashes the deterministic inputs, so the
same audit with and without judgements carries one id and `recheck` still
re-derives it. ADR-0017: a judge annotates an audit; it does not make one.
"""

from __future__ import annotations

from akashi.domain.evidence import Evidence
from akashi.domain.report import AuditReport
from akashi.domain.verdict import Standing
from akashi.ports.judge import Claim, Judge, Judgement

__all__ = ["claims_for", "judge_report"]

#: How many claims akashi will send in one run.
#:
#: A judge costs money and time per claim, and an answer with two hundred
#: floating particulars is an answer whose problem is not subtle. The bound is
#: on the *report*, so a caller cannot turn one audit into an unbounded number
#: of calls by handing akashi a long enough answer -- the same reasoning as
#: `MAX_RUN`, on a different resource.
MAX_CLAIMS = 64


def claims_for(report: AuditReport) -> tuple[Claim, ...]:
    """What akashi could not settle, in report order.

    A floating particular becomes a claim about that particular *inside its
    sentence*: the sentence is what a reader of the evidence would have to
    agree with, and a bare `2.4kg` entails nothing on its own.

    A `contradicted` particular is **not** sent. akashi has already named the
    value the source gives and the offset it sits at, which is a stronger and
    checkable statement; asking a model to weigh in could only add an opinion
    beside a fact.
    """
    found: list[Claim] = []
    for segment in report.assessment.segments:
        for one in segment.particulars:
            if one.standing is not Standing.FLOATING or one.contradiction is not None:
                continue
            found.append(
                Claim(
                    segment_id=segment.segment.segment_id,
                    text=segment.segment.text,
                    particular=one.particular.text,
                )
            )
            if len(found) >= MAX_CLAIMS:
                return tuple(found)
    return tuple(found)


def judge_report(report: AuditReport, judge: Judge, evidence: Evidence) -> tuple[Judgement, ...]:
    """Every judgement for ``report``, or nothing when there is nothing to ask.

    ``evidence`` is passed rather than taken from the report, because a report
    does not carry the corpus and must not: it quotes the answer, and the text
    that was sent stays in the package. So a caller that wants judgements has to
    still be holding the package -- which is the right requirement, since a
    judgement about evidence nobody has is not checkable by anyone.

    The evidence handed over is the text that was sent, **whole**. Trimming it to
    what akashi thinks is relevant would make the judge's answer depend on
    akashi's own matching, which is the thing the judge is there to be
    independent of.
    """
    claims = claims_for(report)
    if not claims:
        return ()

    judgements = judge.judge(claims, [item.text for item in evidence.items])

    if len(judgements) != len(claims):
        raise ValueError(
            f"the judge answered {len(judgements)} of {len(claims)} claims. A caller "
            f"lines these up against what it asked about, and a missing answer would "
            f"shift every judgement after it onto the wrong sentence."
        )
    return tuple(judgements)
