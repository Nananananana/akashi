"""Japanese: an unambiguous terminator, and everything else difficult.

``。`` is only ever the end of a sentence, so there is no disambiguation to do
and no abbreviation list to keep. What is hard here is elsewhere: quotation
brackets that a sentence may not end inside (``domain/segment.py`` tracks the
depth), the absence of a terminator in a bulleted or headed answer (the line
fallback, and ADR-0009 owes a measurement of how often it fires), and the fact
that half-width and full-width digits both occur, often in the same sentence
(``domain/text.py`` folds them together).

``！`` and ``？`` are shared with Chinese and behave identically in both, which
is what ``_rules`` asserts rather than assumes.
"""

from __future__ import annotations

from akashi.domain.language import LanguagePack

__all__ = ["JAPANESE"]

JAPANESE = LanguagePack(
    code="ja",
    version=1,
    # ``．`` is here because a model asked for Japanese sometimes emits the
    # full-width full stop instead of ``。``. It is unambiguous in this script
    # in a way ASCII ``.`` is not.
    terminators=frozenset("。！？．"),
    # Japanese does not put a space after a full stop, and requiring one would
    # produce exactly one segment per paragraph.
    needs_space_after=False,
)
