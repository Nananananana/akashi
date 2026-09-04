"""How often does the evidence carry a rival for a value that grounded? (#88)

akashi grounds a particular against whichever evidence item contains it. If the
retrieved set holds two documents that disagree, the answer grounds against one
and the report says `grounded`, share 1.0, and nobody is told.

    answer     The tent weighs 3.1kg.
    context 1  The tent weighs 3.1kg.        <- grounds here, share 1.0
    context 5  Tent, revised spec: 2.8kg.    <- nobody is told

The candidate rule is: **same kind, same shape, different digits**. `3.1kg` and
`2.8kg` both reduce to `#kg`. That is the drift rule `docs/measurements.md`
already priced at 47% when it was used to *name a source*, which is why nothing
ships before this runs.

The question this answers is narrower than "is the rule right". It is: **how
often would it fire at all, and on what?** A rule that fires on a third of every
grounded particular is noise whatever its precision; one that fires rarely can
be reported as a fact and left to the reader.

    python tools/measure_source_conflict.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from akashi.application.audit import audit
from akashi.domain.contradiction import SourceIndex, SourceParticular, _digits, _shape
from akashi.errors import ProtectedResponseError
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package

CASES = Path(__file__).resolve().parents[1] / "tests" / "cases"


@dataclass(frozen=True, slots=True)
class Rival:
    case: str
    value: str
    grounded_in: str
    rival: str
    rival_in: str
    planted: bool


def rivals_for(
    value: str, kind: object, item_id: str, index: SourceIndex
) -> list[SourceParticular]:
    """Every source particular of the same kind and shape with different digits.

    Restricted to a **different item**: two figures in one document are that
    document being detailed, not two documents disagreeing.
    """
    shape, digits = _shape(value), _digits(value)
    if not digits:
        return []
    return [
        entry
        for entry in index.entries
        if entry.kind is kind
        and entry.item_id != item_id
        and _shape(entry.text) == shape
        and _digits(entry.text) != digits
    ]


def main() -> None:
    found: list[Rival] = []
    grounded_total = 0
    skipped: list[str] = []

    for folder in sorted(CASES.iterdir()):
        response = folder / "response.txt"
        if not (folder / "case.json").is_file() or not response.is_file():
            continue
        case = json.loads((folder / "case.json").read_text(encoding="utf-8"))
        package = load_package(folder / "package.json")
        try:
            report = audit(response.read_text(encoding="utf-8"), package, DEFAULT)
        except ProtectedResponseError:
            skipped.append(folder.name)
            continue

        index = SourceIndex.of(package.evidence, DEFAULT)
        planted = {
            str(plant.get("text", ""))
            for plant in case.get("plants", [])
            if plant.get("kind") not in {"grounded", "faithful_paraphrase"}
        }
        for segment in report.assessment.segments:
            for one in segment.particulars:
                if not one.locations:
                    continue
                grounded_total += 1
                where = one.locations[0].item_id
                for entry in rivals_for(one.particular.text, one.particular.kind, where, index):
                    found.append(
                        Rival(
                            case=folder.name,
                            value=one.particular.text,
                            grounded_in=where,
                            rival=entry.text,
                            rival_in=entry.item_id,
                            planted=one.particular.text in planted,
                        )
                    )

    out = sys.stdout.buffer
    out.write(
        f"{grounded_total} grounded particulars, {len(skipped)} cases skipped "
        f"(protected)\n".encode()
    )
    if not found:
        out.write(
            b"\n  The rule fires on NONE of them. The corpus contains no evidence set\n"
            b"  that disagrees with itself, so it cannot price this rule either way.\n"
        )
        return

    affected = {(rival.case, rival.value) for rival in found}
    out.write(
        f"\n  fires on {len(affected)} of {grounded_total} grounded particulars "
        f"({len(affected) / grounded_total * 100:.1f}%)\n".encode()
    )
    out.write(f"  {len(found)} rival pairs in total\n".encode())
    on_a_plant = sum(1 for rival in found if rival.planted)
    out.write(f"  of those, {on_a_plant} are on a value the case marks as planted\n\n".encode())
    for rival in sorted(found, key=lambda r: (r.case, r.value))[:20]:
        tag = "PLANTED " if rival.planted else "faithful"
        out.write(
            f"  {tag} {rival.case:<20} {rival.value!r} in {rival.grounded_in} "
            f"vs {rival.rival!r} in {rival.rival_in}\n".encode()
        )
    per_case = Counter(rival.case for rival in found)
    out.write(f"\n  cases with any rival: {len(per_case)}\n".encode())


if __name__ == "__main__":
    main()
