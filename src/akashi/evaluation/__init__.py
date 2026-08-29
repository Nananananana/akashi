"""The labelled corpus, and the arithmetic over it.

ADR-0010. The ground truth is *constructed* rather than judged: a case is built
by taking sentences that are grounded by construction and applying a named
mutation to a named span, so what is true about it is known rather than
annotated. A dataset labelled by a person or a model measures the labeller, and
the corpus that defined this task reports 78.8% agreement between two trained
human annotators at the span level.

**No model runs here.** A model may write prose at authoring time; the fixtures
are committed and CI reads files (ADR-0003).
"""

from __future__ import annotations

from .case import Case, Plant, PlantKind, Source, load_case, load_cases

__all__ = ["Case", "Plant", "PlantKind", "Source", "load_case", "load_cases"]
