"""The one use case: audit an answer against the package that produced it.

Six stages, and every one of them is a pure function of its inputs (ADR-0003).
This module is the order they run in and nothing else -- every verdict on the
report is decided in ``domain``, and a use case that made one would be a second
place to look for the answer to "why does it say that".

The language packs are passed in rather than imported. The application layer
does not know which languages exist; the composition root does, and injecting
them is what keeps a fourth language a data change in one package
(ADR-0009, ADR-0011).
"""

from __future__ import annotations

from collections.abc import Sequence

from akashi.domain.contradiction import SourceIndex
from akashi.domain.coverage import assess
from akashi.domain.extraction import extract_from_segment, kinds_not_extracted
from akashi.domain.language import LanguagePack
from akashi.domain.package import ContextPackage
from akashi.domain.report import Audited, AuditReport, ReportProvenance, content_hash
from akashi.domain.segment import segment_answer
from akashi.domain.verdict import check_segment
from akashi.ports import Restorer

from .admit import admit

__all__ = ["audit"]


def audit(
    answer: str,
    package: ContextPackage,
    packs: Sequence[LanguagePack],
    *,
    restorer: Restorer | None = None,
    restored_by: str = "",
    akashi_version: str = "",
) -> AuditReport:
    """Audit ``answer`` against ``package``, or refuse.

    Raises ``ProtectedResponseError`` when the answer cannot be audited
    honestly (ADR-0008). Everything else is a report -- including a report over
    an empty package, where every particular floats correctly and uselessly and
    the coverage numbers are what say so.
    """
    admission = admit(answer, package, restorer, restored_by=restored_by)
    text = admission.answer

    segmentation = segment_answer(text, packs)
    # Built once. Segmenting and extracting the evidence costs the same work the
    # answer already gets, over text that is usually shorter, and it buys the
    # only finding a reader can act on without opening the file themselves.
    sources = SourceIndex.of(package.evidence, packs)
    checked = [
        check_segment(
            segment,
            extract_from_segment(segment, packs),
            package.evidence,
            sources,
            # What a restorer could not put back. ADR-0008's third path: audit
            # what can be audited and mark what cannot, rather than reporting a
            # masked value as a fabrication.
            admission.residue,
        )
        for segment in segmentation.segments
    ]
    assessment = assess(checked, kinds_not_extracted(packs))

    return AuditReport(
        answer=text,
        assessment=assessment,
        audited=Audited(
            package_id=package.package_id,
            response_hash=content_hash(text),
            response_length=len(text),
            segmenters=segmentation.segmenters,
            extractors=tuple(sorted(pack.extractor_name for pack in packs if pack.rules)),
            # Narrowing the packs changes the segmentation and therefore every
            # count, so the set that was loaded is part of what identifies the
            # report rather than a note beside it.
            packs=tuple(sorted(pack.code for pack in packs)),
            akashi_version=akashi_version,
        ),
        provenance=ReportProvenance(
            restored_by=admission.restored_by,
            restoration_asserted=admission.asserted,
            protection_by=package.protection.by if package.protection else "",
            withheld=tuple(package.evidence.withheld_by_rule().items()),
            unrecognised=package.unrecognised,
        ),
    )
