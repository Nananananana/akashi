"""The authored material the corpus is composed from.

Prose, written once, by hand. The labels are computed from it (ADR-0010) and
nothing here is a label: a spec says what a sentence *is* -- grounded, digit
drifted, negated -- and ``generation.py`` derives what should follow from that.
A spec that could state its own expectations would be an annotation, and an
annotated corpus measures the annotator.

Three genres, chosen for where a wrong number costs money rather than for
variety: a contract, a clinical note, an engineering specification. Each in
three languages. The genres are not decoration, but they are not the dataset
either -- the plants are.
"""

from __future__ import annotations

from ..generation import GenreSpec
from .en import ENGLISH
from .ja import JAPANESE
from .zh import CHINESE

__all__ = ["ALL", "CHINESE", "ENGLISH", "JAPANESE", "genres"]

ALL: tuple[GenreSpec, ...] = (*ENGLISH, *JAPANESE, *CHINESE)


def genres(*languages: str) -> tuple[GenreSpec, ...]:
    """Every spec, or only those in the named languages, in a fixed order."""
    if not languages:
        return ALL
    wanted = set(languages)
    unknown = sorted(wanted - {spec.language for spec in ALL})
    if unknown:
        raise ValueError(f"no genre specs for {unknown}")
    return tuple(spec for spec in ALL if spec.language in wanted)
