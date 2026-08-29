"""What a language pack is, as a value.

The algorithm lives in ``domain``; the rules it runs live in
``infrastructure/languages/`` (ADR-0009, following ``mamori``'s ADR-0008). This
module is the shape they meet in, which is why it is here and not there: a
fourth language must be a data change, and it can only be a data change if the
domain never learns which languages exist.

A pack claims *terminators*, not documents. See ADR-0011: the script is decided
at the boundary rather than for the answer, because one Japanese paragraph with
one English sentence in it is the ordinary case and not the exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .particular import ExtractionRule

__all__ = ["LanguagePack", "Script", "script_of"]


class Script(Enum):
    """The dominant script of a piece of text, for reporting.

    Nothing in segmentation depends on this. Every metric is reported per
    language as well as in aggregate (ADR-0010), because an aggregate hides
    that extraction is strong on Japanese figures and weak on English legal
    citations, and those are different problems.
    """

    JAPANESE = "ja"
    CHINESE = "zh"
    LATIN = "en"
    UNKNOWN = "und"


def script_of(text: str) -> Script:
    """The dominant script, decided by the one unambiguous marker there is.

    Kana wins outright: hiragana and katakana appear in Japanese and nowhere
    else, so a single character of it settles the question no matter how much
    han surrounds it. Han without kana is read as Chinese, which is wrong for a
    Japanese sentence written entirely in kanji -- an uncommon case, reported
    rather than guessed at, and visible in the per-language numbers.
    """
    han = latin = 0
    for character in text:
        code = ord(character)
        if 0x3040 <= code <= 0x30FF or 0x31F0 <= code <= 0x31FF:
            return Script.JAPANESE
        if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
            han += 1
        elif character.isalpha() and code < 0x0250:
            latin += 1
    if han:
        return Script.CHINESE
    if latin:
        return Script.LATIN
    return Script.UNKNOWN


@dataclass(frozen=True, slots=True)
class LanguagePack:
    """The rules one language contributes to segmentation.

    ``terminators`` is what the pack claims for segmentation. Two packs
    claiming the same character must agree about how it behaves -- ``。`` ends a
    sentence the same way in Japanese and in Chinese -- and that is refused at
    construction rather than settled by load order (ADR-0011).

    ``rules`` is what it contributes to extraction. A pack may carry only one
    of the two: the shared numeric pack claims no terminator, because an ISO
    date and a percentage are not anybody's punctuation.
    """

    code: str
    version: int
    #: Characters that can end a sentence.
    terminators: frozenset[str]
    #: Whether a terminator must be followed by whitespace or the end of the
    #: block to count. True for ``.`` in English, where ``example.com`` and
    #: ``2.4`` are not sentence ends. False for ``。``, because Chinese has no
    #: spaces and requiring one would produce one segment per paragraph.
    needs_space_after: bool
    #: Lower-cased and including the full stop: ``{"fig.", "no.", "e.g."}``.
    #: Only consulted for terminators that need a space after them.
    abbreviations: frozenset[str] = field(default_factory=frozenset)
    #: What this pack finds. Ordering is irrelevant -- overlaps are resolved
    #: by a total order in ``extraction.py``, not by which rule ran first.
    rules: tuple[ExtractionRule, ...] = ()

    def __post_init__(self) -> None:
        if not self.terminators and not self.rules:
            raise ValueError(
                f"the {self.code!r} pack claims neither a terminator nor an extraction "
                f"rule, so loading it would change nothing"
            )
        if any(len(terminator) != 1 for terminator in self.terminators):
            raise ValueError(
                f"the {self.code!r} pack claims a terminator that is not one character"
            )
        if self.abbreviations and not self.needs_space_after:
            raise ValueError(
                f"the {self.code!r} pack lists abbreviations but its terminators do not "
                f"need a space after them, so the list would never be consulted"
            )
        if any(word != word.lower() for word in self.abbreviations):
            raise ValueError(f"the {self.code!r} pack has an abbreviation that is not lower-cased")

    @property
    def name(self) -> str:
        """How this pack identifies itself as a segmenter, on a report."""
        return f"akashi.segmenter/{self.code}@{self.version}"

    @property
    def extractor_name(self) -> str:
        """How it identifies itself as an extractor.

        Two names for one pack, because a pack can contribute to one stage and
        not the other -- the shared numeric pack claims rules and no
        punctuation -- and a report that named it under both would say it took
        part in something it did not.
        """
        return f"akashi.extractor/{self.code}@{self.version}"
