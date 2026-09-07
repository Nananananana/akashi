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

from collections import Counter
from collections.abc import Sequence

from akashi.domain.bounds import (
    from_oversized,
    from_truncated_locations,
    from_truncated_sources,
    oversized_runs,
)
from akashi.domain.contradiction import SourceIndex
from akashi.domain.coverage import (
    IRREVERSIBLE_PROTECTION_LIMITS,
    PLAIN_CONTEXT_LIMITS,
    STANDING_LIMITS,
    assess,
)
from akashi.domain.extraction import MAX_RUN, extract_from_segment, kinds_not_extracted
from akashi.domain.language import LanguagePack
from akashi.domain.matching import DEFAULT_MATCHER, LOCATION_LIMIT, SOURCE_LIMIT, Matcher
from akashi.domain.package import PLAIN_CONTRACT, ContextPackage, Protection
from akashi.domain.report import Audited, AuditReport, ReportProvenance, content_hash
from akashi.domain.segment import segment_answer
from akashi.domain.verdict import check_segment
from akashi.errors import SegmentationError
from akashi.ports import Restorer

from .admit import admit, effective_protection

__all__ = ["audit"]


def audit(
    answer: str,
    package: ContextPackage,
    packs: Sequence[LanguagePack],
    *,
    restorer: Restorer | None = None,
    restored_by: str = "",
    akashi_version: str = "",
    matcher: Matcher = DEFAULT_MATCHER,
    protection: Protection | None = None,
) -> AuditReport:
    """Audit ``answer`` against ``package``, or refuse.

    Raises ``ProtectedResponseError`` when the answer cannot be audited
    honestly (ADR-0008). Everything else is a report -- including a report over
    an empty package, where every particular floats correctly and uselessly and
    the coverage numbers are what say so.
    """
    admission = admit(answer, package, restorer, restored_by=restored_by, protection=protection)
    protection = effective_protection(package, protection)
    text = admission.answer

    try:
        segmentation = segment_answer(text, packs)
    except ValueError as broken:
        # The domain raises a built-in, and deliberately: `domain` imports
        # nothing, not even `errors`, which is what keeps ADR-0001's set
        # genuinely empty. So the class ADR-0009 describes cannot be raised
        # where the invariant lives, and for a long time nothing raised it at
        # all -- it was exported, documented, and dead. The catalogue guard
        # (Sora R-E1) found that.
        #
        # This is the layer that may name it, and it is where the audit
        # actually stops. Without the wrap a broken tiling left the command
        # line as a traceback, which reads as a bug in the tool rather than as
        # a refusal -- the exact thing the CLI's own handler exists to avoid.
        raise SegmentationError(str(broken)) from broken
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
            matcher,
        )
        for segment in segmentation.segments
    ]
    assessment = assess(
        checked,
        kinds_not_extracted(packs),
        # A package built from strings carries no provenance, and the report has
        # to say so where the report is read rather than where the helper that
        # built it is documented.
        limits=(
            *STANDING_LIMITS,
            *(PLAIN_CONTEXT_LIMITS if package.contract == PLAIN_CONTRACT else ()),
            # Only when it bit: a line about masked values on a report with no
            # masked value is a warning about nothing, and a reader learns to
            # skip the section it lives in.
            *(
                IRREVERSIBLE_PROTECTION_LIMITS
                if protection is not None and not protection.reversible and admission.residue
                else ()
            ),
        ),
    )

    # Bounds are read off the finished audit rather than threaded through it:
    # each one is a fact about what came out, and a bound that had to be passed
    # down every call to be noticed is a bound the next code path will forget.
    #
    # Counted once per particular rather than once per document per particular.
    # The first version rebuilt the document set and then rescanned every
    # location for each document in it, which is quadratic in a particular's
    # locations -- and a particular's locations are exactly what grows on a
    # large package. It was the single largest slice of an audit's own time.
    per_document = [
        Counter(place.anchor.document_id for place in one.locations)
        for segment in checked
        for one in segment.particulars
    ]
    truncated = sum(
        1 for counts in per_document if max(counts.values(), default=0) >= LOCATION_LIMIT
    )
    over_sourced = sum(1 for counts in per_document if len(counts) >= SOURCE_LIMIT)
    bounds = (
        *from_oversized(oversized_runs(text, MAX_RUN), MAX_RUN),
        *from_truncated_locations(truncated, LOCATION_LIMIT),
        *from_truncated_sources(over_sourced, SOURCE_LIMIT),
    )

    return AuditReport(
        answer=text,
        assessment=assessment,
        bounds=bounds,
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
            matcher=matcher.name,
        ),
        provenance=ReportProvenance(
            restored_by=admission.restored_by,
            restoration_asserted=admission.asserted,
            protection_by=protection.by if protection else "",
            withheld=tuple(package.evidence.withheld_by_rule().items()),
            unrecognised=package.unrecognised,
        ),
    )
