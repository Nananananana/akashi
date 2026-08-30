"""Running the corpus, and turning what happened into counts.

Nothing here decides anything about an answer -- it audits, compares what came
back to what the manifest says was planted, and counts. A runner that made a
judgement would be a second grader, and ADR-0010 exists to have none.

**A plant is flagged when a floating particular overlaps its span.** Not when
the segment floats: a sentence can hold one changed number and three correct
ones, and crediting the plant for the segment would credit it for the three.
Overlap is also what makes a whole-sentence plant work -- a negation flip has
no token to point at, so its span is the sentence and any float inside it
counts.

**Floats that overlap no plant are counted separately.** They are not
attributable to a label, and they are the honest measure of the noise a reader
actually sees: a control sentence is labelled at its target and says other
things too.
"""

from __future__ import annotations

from collections.abc import Sequence

from akashi.application import audit
from akashi.domain.language import LanguagePack
from akashi.domain.report import AuditReport
from akashi.domain.span import Span
from akashi.errors import ProtectedResponseError

from .case import Case, Plant
from .metrics import Breakdown, Score, Tally

__all__ = ["Outcome", "run"]


class Outcome:
    """What became of one case. Held loosely, because it is only counted."""

    __slots__ = ("case", "findings", "refused", "report", "tally")

    def __init__(self, case: Case) -> None:
        self.case = case
        self.report: AuditReport | None = None
        self.refused = False
        self.tally = Tally()
        self.findings: list[str] = []


def _floating_spans(report: AuditReport) -> list[Span]:
    return [
        one.particular.span for segment in report.assessment.segments for one in segment.floating
    ]


def _flagged(floats: Sequence[Span], plant: Plant) -> bool:
    return any(span.overlaps(plant.span) for span in floats)


def _verdicts_over(report: AuditReport, plant: Plant) -> set[str]:
    """Every verdict covering the plant's span.

    A set rather than one value: a plant the segmenter cut in two has two
    verdicts, and picking either would be arbitrary. The split is counted
    separately -- it is a segmentation disagreement, and worth seeing where it
    happens rather than inferring it from a score that moved.
    """
    return {
        segment.verdict.value
        for segment in report.assessment.segments
        if segment.span.overlaps(plant.span)
    }


def _named_source(report: AuditReport, plant: Plant) -> tuple[str, Span] | None:
    """The source akashi named over this plant, right or wrong.

    ``_located`` cannot answer this: it asks whether the labelled source was
    found, and returns False both when akashi said nothing and when it named
    something else. Those are not the same failure, and only the second is one
    the reader can be harmed by.
    """
    for segment in report.assessment.segments:
        for one in segment.particulars:
            if one.contradiction is None or not one.particular.span.overlaps(plant.span):
                continue
            anchor = one.contradiction.anchor
            return anchor.document_id, anchor.span
    return None


def _located(report: AuditReport, plant: Plant) -> bool:
    """Whether akashi reported the source the plant replaced.

    Structurally false until v0.4: a floating particular resolves nowhere, so it
    carried no location at all. The number was the baseline ``contradicted``
    had to move, and a metric introduced at the same time as the feature it
    scores measures nothing.

    A contradicted particular is still floating -- it has no ``locations`` --
    so the anchor is read off the contradiction. Nothing else here changed.
    """
    if plant.source is None:
        return False
    for segment in report.assessment.segments:
        for one in segment.particulars:
            if not one.particular.span.overlaps(plant.span):
                continue
            if one.contradiction is not None and plant.source.matches(
                one.contradiction.anchor.document_id, one.contradiction.anchor.span
            ):
                return True
            for location in one.locations:
                if plant.source.matches(location.anchor.document_id, location.anchor.span):
                    return True
    return False


def _score_case(case: Case, packs: Sequence[LanguagePack]) -> Outcome:
    outcome = Outcome(case)
    tally = outcome.tally
    tally.cases = 1

    if case.expect_refusal:
        tally.refusals_due = 1
        try:
            audit(case.response, case.package, packs)
        except ProtectedResponseError:
            outcome.refused = True
            tally.refused = 1
            tally.reproduced = 1
        else:
            outcome.findings.append(
                f"{case.case_id}: audited a protected response instead of refusing it"
            )
        return outcome

    report = audit(case.response, case.package, packs)
    outcome.report = report
    if report == audit(case.response, case.package, packs):
        tally.reproduced = 1
    else:
        outcome.findings.append(f"{case.case_id}: two audits, two reports")

    coverage = report.assessment.coverage
    tally.segments = coverage.segments
    tally.unbearing = coverage.unbearing
    tally.unexamined = coverage.unexamined
    tally.particulars = coverage.particulars

    floats = _floating_spans(report)
    claimed: list[Span] = []

    for plant in case.plants:
        flagged = _flagged(floats, plant)
        if flagged:
            claimed.append(plant.span)

        if plant.declared_miss:
            tally.declared_planted += 1
            if not flagged:
                tally.declared_passed += 1
            else:
                outcome.findings.append(
                    f"{case.case_id}: flagged a {plant.kind.value}, which ADR-0004 says "
                    f"it cannot see. The label or the limit is wrong."
                )
        elif plant.is_control:
            tally.controls_planted += 1
            if flagged:
                tally.false_positives += 1
                outcome.findings.append(f"{case.case_id}: flagged the control {plant.describe()}")
        elif plant.is_acknowledged_false_positive:
            tally.acknowledged_planted += 1
            tally.acknowledged_found += int(flagged)
        else:
            tally.fabrications_planted += 1
            tally.fabrications_found += int(flagged)
            if not flagged:
                outcome.findings.append(f"{case.case_id}: missed {plant.describe()}")

        verdicts = _verdicts_over(report, plant)
        if len(verdicts) > 1:
            tally.plants_split += 1
        if flagged:
            tally.verdicts_checked += 1
            tally.verdicts_right += int(plant.expect_verdict in verdicts)
        if plant.source is not None and plant.expect_detected:
            tally.locatable += 1
            tally.located += int(_located(report, plant))
        named = _named_source(report, plant)
        if named is not None:
            tally.localisations += 1
            tally.misdirected += int(plant.source is None or not plant.source.matches(*named))

    tally.unattributed_floats = sum(
        1 for span in floats if not any(span.overlaps(plant.span) for plant in case.plants)
    )
    return outcome


def run(cases: Sequence[Case], packs: Sequence[LanguagePack]) -> tuple[Breakdown, list[str]]:
    """Audit every case and count what happened.

    Returns the breakdown and the notes -- the individual disagreements, in
    case order. A rate says how often something went wrong; the notes say
    which, and a measurement that cannot be followed back to a case is a
    measurement nobody can act on.
    """
    overall = Tally()
    languages: dict[str, Tally] = {}
    kinds: dict[str, Tally] = {}
    notes: list[str] = []

    for case in cases:
        outcome = _score_case(case, packs)
        overall.add(outcome.tally)
        languages.setdefault(case.language, Tally()).add(outcome.tally)
        notes.extend(outcome.findings)

        # Per kind, a case is scored once for each kind it plants, so that a
        # kind's rate is over its own plants rather than over whole cases.
        for kind in sorted({plant.kind.value for plant in case.plants}):
            single = _score_kind(case, outcome, kind)
            kinds.setdefault(kind, Tally()).add(single)

    return (
        Breakdown(
            overall=Score(overall),
            by_language={name: Score(tally, name) for name, tally in sorted(languages.items())},
            by_kind={name: Score(tally, name) for name, tally in sorted(kinds.items())},
        ),
        notes,
    )


def _score_kind(case: Case, outcome: Outcome, kind: str) -> Tally:
    """The counters for one kind's plants inside one case.

    Recomputed rather than accumulated during the pass, because the per-kind
    view has to exclude everything the other kinds contributed -- including the
    coverage numbers, which belong to the case and not to any plant.
    """
    tally = Tally()
    if outcome.report is None:
        if case.expect_refusal:
            tally.refusals_due = 1
            tally.refused = int(outcome.refused)
        return tally

    floats = _floating_spans(outcome.report)
    for plant in case.plants:
        if plant.kind.value != kind:
            continue
        flagged = _flagged(floats, plant)
        if plant.declared_miss:
            tally.declared_planted += 1
            tally.declared_passed += int(not flagged)
        elif plant.is_control:
            tally.controls_planted += 1
            tally.false_positives += int(flagged)
        elif plant.is_acknowledged_false_positive:
            tally.acknowledged_planted += 1
            tally.acknowledged_found += int(flagged)
        else:
            tally.fabrications_planted += 1
            tally.fabrications_found += int(flagged)
        if flagged:
            tally.verdicts_checked += 1
            tally.verdicts_right += int(
                plant.expect_verdict in _verdicts_over(outcome.report, plant)
            )
        if plant.source is not None and plant.expect_detected:
            tally.locatable += 1
            tally.located += int(_located(outcome.report, plant))
        named = _named_source(outcome.report, plant)
        if named is not None:
            tally.localisations += 1
            tally.misdirected += int(plant.source is None or not plant.source.matches(*named))
    return tally
