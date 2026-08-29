"""Looking for one particular in one piece of text.

Two problems that a plain substring search gets wrong, and both of them wrong
in the dangerous direction -- reporting a particular as grounded when it is not
there.

**A number occurs inside a longer number.** ``2.4`` is a substring of ``2.40``,
``30`` of ``300``, and ``三千人`` of ``一万三千人``. A search that found them
would let a changed figure ground against the figure it was changed from, which
is precisely the failure akashi exists to catch. So a match is rejected when
the character beside it continues the same kind of token.

The continuity test is per character class rather than per word, because two of
the three languages have no word boundaries. ``\\b`` would reject ``三千人``
inside ``参加者は三千人`` -- ``は`` is a particle and ``\\w`` cannot tell it from
a numeral -- and accept it inside ``一万三千人``, which is a different number.
Comparing classes gets both right: a digit beside a digit continues, a kanji
numeral beside a kanji numeral continues, and a particle beside a numeral does
not.

**A quantity is written with and without its space.** ``2.4kg`` and ``2.4 kg``
are the same quantity and two different strings, and ``text.py`` deliberately
does not collapse that difference -- doing so for prose would make ``a b`` and
``ab`` one sentence. So the tolerance lives here, where it is about a
particular and not about text: a particular is split into its runs of digits
and its runs of everything else, and the runs are allowed to be separated by
any amount of whitespace or none. ``第30条`` therefore matches ``第 30 条``, and
``2.4kg`` matches ``2.4 kg``, and neither matches anything else.
"""

from __future__ import annotations

import re
from functools import lru_cache

from .span import Span
from .text import SearchForm

__all__ = ["find_all", "pattern_for"]

#: Numerals whose adjacency changes the value. ``三千人`` inside ``一万三千人``
#: is thirteen thousand and not three thousand.
_CJK_NUMERALS = frozenset("〇零一二三四五六七八九十百千万億兆亿两")

#: Runs that a space may legitimately sit between. Digits and their internal
#: separators on one side, everything else on the other.
_RUNS = re.compile(r"[0-9][0-9.,]*|[^0-9\s]+")

#: How many places one particular is reported in. A very short particular
#: genuinely occurs everywhere, and reporting all of them carries no more
#: information than reporting that it is common.
_LIMIT = 32


def _class_of(character: str) -> str:
    """The kind of token a character continues, or ``""`` for none.

    Only three classes matter, and they are the three where adjacency changes
    what a particular means.
    """
    if not character:
        return ""
    if character.isdigit():
        return "digit"
    if character in _CJK_NUMERALS:
        return "cjk-numeral"
    if character.isascii() and character.isalpha():
        return "latin"
    return ""


@lru_cache(maxsize=1024)
def pattern_for(form: str) -> re.Pattern[str] | None:
    """A pattern that finds ``form`` with its internal spacing free.

    ``None`` when the form carries nothing to look for. An empty particular is
    not something that fails to resolve; it is something that was never a
    particular, and the caller has to tell those apart.
    """
    runs = _RUNS.findall(form)
    if not runs:
        return None
    return re.compile(r"\s*".join(re.escape(run) for run in runs))


def _continues(left: str, right: str) -> bool:
    """Whether two adjacent characters are part of the same token."""
    kind = _class_of(left)
    return bool(kind) and kind == _class_of(right)


def _at(text: str, index: int) -> str:
    """The character at ``index``, or ``""`` when there is none.

    Written out rather than sliced, because ``text[-1:0]`` is empty and
    ``text[-2:-1]`` is the second-to-last character. A negative index that
    silently reads from the far end of the document is exactly the kind of
    quiet wrong answer this module exists to avoid.
    """
    return text[index] if 0 <= index < len(text) else ""


def _bounded(form: SearchForm, span: Span) -> bool:
    """Whether a match stands alone rather than sitting inside something longer."""
    text = form.text
    before = _at(text, span.start - 1)
    after = _at(text, span.end)

    if _continues(before, text[span.start]):
        return False
    if _continues(text[span.end - 1], after):
        return False

    # A decimal separator is not a digit, so the class test alone misses ``2.4``
    # inside ``12.45``: the character beside the match is ``.``, which continues
    # nothing. Reject a number with a separator beside it and a digit on the far
    # side of that.
    if text[span.start].isdigit() and before in (".", ",") and _at(text, span.start - 2).isdigit():
        return False
    return not (
        text[span.end - 1].isdigit() and after in (".", ",") and _at(text, span.end + 1).isdigit()
    )


def find_all(form: str, haystack: SearchForm) -> tuple[Span, ...]:
    """Every place ``form`` stands alone in ``haystack``, as spans of the original.

    Empty when it does not occur, and that is a real answer: a particular that
    is not there is not nearly there (ADR-0004).

    More than one place is not an error either. A short particular genuinely
    occurs in several, and reporting all of them is more honest than picking
    one and implying a precision that is not there.
    """
    pattern = pattern_for(form)
    if pattern is None or not haystack.text:
        return ()

    found: list[Span] = []
    at = 0
    while len(found) < _LIMIT:
        match = pattern.search(haystack.text, at)
        if match is None:
            break
        start, end = match.span()
        span = Span(start, end)
        if _bounded(haystack, span):
            found.append(haystack.to_original(span))
        at = start + 1
    return tuple(found)
