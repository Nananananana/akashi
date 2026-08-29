"""The language packs, as data.

The algorithm is in ``domain``; what is here is what each language contributes
to it (ADR-0009). A fourth language is a module in this package and a fixture
set, and nothing in ``domain`` learns that it exists.

``DEFAULT`` is every pack, always, and that is the point of ADR-0011: a
boundary is decided by whichever pack claims the character in front of it, so
loading all of them is what makes a Japanese paragraph with one English
sentence in it segment correctly. There is no "choose the language" step to get
wrong.
"""

from __future__ import annotations

from akashi.domain.language import LanguagePack

from .common import COMMON
from .en import ENGLISH
from .ja import JAPANESE
from .zh import CHINESE

__all__ = ["CHINESE", "COMMON", "DEFAULT", "ENGLISH", "JAPANESE", "packs"]

#: Sorted by code, so that anything derived from the order is reproducible.
DEFAULT: tuple[LanguagePack, ...] = (COMMON, ENGLISH, JAPANESE, CHINESE)

_LANGUAGES: dict[str, LanguagePack] = {pack.code: pack for pack in DEFAULT if pack is not COMMON}


def packs(*codes: str) -> tuple[LanguagePack, ...]:
    """The named packs, in a fixed order. Everything, when nothing is named.

    ``COMMON`` is always included and cannot be excluded: an ISO date and a
    percentage belong to no language, and a pack set without them would find no
    particulars at all in an answer written entirely in figures.

    Narrowing the set is for measurement -- what does segmentation cost when
    only one language is loaded -- and not for production. An audit that loaded
    the wrong pack would silently under-segment, and under-segmenting merges
    two sentences into one verdict.
    """
    if not codes:
        return DEFAULT
    unknown = sorted(set(codes) - set(_LANGUAGES))
    if unknown:
        raise ValueError(f"no language pack for {unknown}; known: {sorted(_LANGUAGES)}")
    return (COMMON, *(_LANGUAGES[code] for code in sorted(set(codes))))
