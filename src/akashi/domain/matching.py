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
import unicodedata
from functools import lru_cache
from typing import Protocol, runtime_checkable

from .span import Span
from .text import SearchForm, search_form

__all__ = [
    "DEFAULT_MATCHER",
    "MATCHERS",
    "Matcher",
    "exact",
    "find_all",
    "matcher_named",
    "normalized",
    "pattern_for",
]

#: Numerals whose adjacency changes the value. ``三千人`` inside ``一万三千人``
#: is thirteen thousand and not three thousand.
_CJK_NUMERALS = frozenset("〇零一二三四五六七八九十百千万億兆亿两")

#: Runs that a space may legitimately sit between. Digits and their internal
#: separators on one side, everything else on the other.
_RUNS = re.compile(r"[0-9][0-9.,]*|[^0-9\s]+")

#: How many places one particular is reported in. A very short particular
#: genuinely occurs everywhere, and reporting all of them carries no more
#: information than reporting that it is common.
LOCATION_LIMIT = 32


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

    # A separator is not a digit, so the class test alone misses ``2.4`` inside
    # ``12.45``: the character beside the match is ``.``, which continues
    # nothing. So a separator with a digit on the far side of it binds too.
    if text[span.start].isdigit() and _binds(form, span.start - 1):
        return False
    return not (text[span.end - 1].isdigit() and _binds(form, span.end))


def _binds(form: SearchForm, index: int) -> bool:
    """Whether the separator at ``index`` makes one number out of two runs.

    ``.`` always does, between digits: ``12.45`` is one value.

    **``,`` only does when it is a thousands separator**, and that is the whole
    of this function. Treating every comma between digits as binding is what
    made ``第3，5，7条`` -- an ordinary Chinese enumeration -- fail to resolve
    into the very document it was extracted from. NFKC turns ``，`` into ``,``,
    the rule saw digit-comma-digit, and every clause number in the list was
    reported as fabricated. Found by the property test that says everything
    extracted from the evidence must ground back into it, on ``2026-08-30，2.4kg``.

    A thousands separator is a comma between digits with **exactly three**
    digits after it: ``45,000`` and ``1,234,567`` bind, ``3,5`` and ``30,2.4``
    do not. That is right for the three languages akashi reads, all of which
    group by threes; it would be wrong where a comma is the decimal point, and
    akashi does not claim those.
    """
    text = form.text
    character = _at(text, index)
    if not _at(text, index - 1).isdigit():
        return False
    if character == ".":
        return _at(text, index + 1).isdigit()
    if character != ",":
        return False
    group = text[index + 1 : index + 4]
    if not (len(group) == 3 and group.isdigit() and not _at(text, index + 4).isdigit()):
        return False
    return _same_width(form, index) and _is_number_tail(text, index)


def _same_width(form: SearchForm, index: int) -> bool:
    """Whether the separator was written at the same width as its digits.

    ``NFKC`` folds ``，`` to ``,``, and with it the distinction the *author*
    made. In ``45,000，300g`` the number's own separator is half-width and the
    pause between the two values is full-width; folded, both are ``,`` and the
    text reads as one number ``45,000,300``. The extractor -- which works on the
    original -- had already read it as two, so a particular it took out of the
    evidence did not resolve back into it.

    A fully full-width number is not the same case: ``４５，０００`` uses one
    width throughout and its comma binds. So the test is agreement rather than
    width: a separator joins two runs when it was written the way they were.

    Found by the property test that says everything extracted from the evidence
    must resolve back into it, on ``45,000，300g``, and pinned there.
    """
    return _width_of(form, index) == _width_of(form, index - 1) == _width_of(form, index + 1)


def _width_of(form: SearchForm, index: int) -> str:
    """``"wide"`` or ``"narrow"`` for the original character behind ``text[index]``."""
    if not 0 <= index < len(form.text):
        return ""
    original = form.original[form.origin[index] : form.extent[index]] or " "
    return "wide" if unicodedata.east_asian_width(original[0]) in ("F", "W") else "narrow"


def _is_number_tail(text: str, end: int) -> bool:
    """Whether the digit run ending at ``end`` is the tail of a *number*.

    A thousands separator joins two parts of one number, so the left part has to
    be a number. In ``2026-08-30，300g`` it is not: the ``30`` is a day, and the
    run before the comma reads as a thousands group only because nothing looked
    at what was in front of it.

    Found by the property test that says everything extracted from the evidence
    must resolve back into it -- **a date did not ground in the very text it was
    extracted from**, which is the direction that matters: akashi reporting an
    honest citation as fabricated. Pinned as an `@example` in
    `tests/test_invariants.py`.

    A hyphen is only a separator when a digit is in front of it. ``-1,234`` is a
    negative number and its comma binds; ``08-30,300`` is a date beside a
    quantity and its comma does not.
    """
    start = end
    while start > 0 and text[start - 1].isdigit():
        start -= 1
    return not (_at(text, start - 1) in "-/" and _at(text, start - 2).isdigit())


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
    while len(found) < LOCATION_LIMIT:
        match = pattern.search(haystack.text, at)
        if match is None:
            break
        start, end = match.span()
        span = Span(start, end)
        if _bounded(haystack, span):
            found.append(haystack.to_original(span))
        at = start + 1
    return tuple(found)


# --- choosing how a particular is looked for ---------------------------------
#
# The two problems at the top of this module are solved one way here, and it is
# a *choice*: which strings count as the same string is the question the whole
# audit turns on, and a component that answers it silently is a component whose
# answer nobody can disagree with.
#
# So the answer has a name, the name travels on the report, and the name is in
# `report_id` -- because it changes every count, exactly as the language packs
# do (ADR-0009). A matcher swapped without that would produce two different
# reports carrying one id, which is the failure `recheck` exists to make
# impossible.
#
# **There are two, and the second is not decoration.** A port with one
# implementation is a port nobody has tried to satisfy; akashi learned that from
# `Restorer`, whose docstring described a shape the real library did not have
# (#76). `exact` is the one a reader reaches for when they want to know how much
# of the score the tolerance is carrying.


@runtime_checkable
class Matcher(Protocol):
    """How akashi decides a particular occurs in a piece of text.

    ``name`` is not a label. It goes into the report and into ``report_id``,
    so two runs that answered this question differently cannot be mistaken for
    each other.
    """

    @property
    def name(self) -> str: ...

    def find(self, form: str, haystack: SearchForm) -> tuple[Span, ...]: ...


class _Normalized:
    """The default, and what akashi measured every number in `docs/measurements.md` with.

    Comparison happens over the folded form (`text.py`), a particular's internal
    spacing is free, and a match that sits inside a longer token of the same
    kind is rejected. ``2.4kg`` finds ``2.4 kg`` and does not find ``2.40kg``.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return "normalized"

    def find(self, form: str, haystack: SearchForm) -> tuple[Span, ...]:
        return find_all(form, haystack)


class _Exact:
    """The same boundary rules, and no tolerance for spacing.

    ``2.4kg`` no longer finds ``2.4 kg``. That is a **stronger** claim per
    grounded particular and a weaker recall, and both halves are the point: a
    reader who wants to know what the spacing tolerance is worth runs the corpus
    under both and reads the difference.

    Folding still applies. Turning that off as well would compare a full-width
    ``２.４kg`` against a half-width one and report an honest citation as
    fabricated -- which is not a stricter audit, it is a broken one, and half
    of what akashi reads is CJK.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return "exact"

    def find(self, form: str, haystack: SearchForm) -> tuple[Span, ...]:
        needle = search_form(form).text
        if not needle or not haystack.text:
            return ()
        found: list[Span] = []
        at = 0
        while len(found) < LOCATION_LIMIT:
            index = haystack.text.find(needle, at)
            if index < 0:
                break
            span = Span(index, index + len(needle))
            if _bounded(haystack, span):
                found.append(haystack.to_original(span))
            at = index + 1
        return tuple(found)


normalized: Matcher = _Normalized()
exact: Matcher = _Exact()

#: Every matcher a caller may name, by the name that appears on the report.
MATCHERS: dict[str, Matcher] = {one.name: one for one in (normalized, exact)}

#: What akashi uses when nobody chooses, and what every published measurement
#: was taken with. Changing this changes what the numbers in
#: `docs/measurements.md` mean, so it is a decision and not a default.
DEFAULT_MATCHER: Matcher = normalized


def matcher_named(name: str) -> Matcher:
    """The matcher called ``name``, or a refusal that lists the ones there are.

    Refused rather than fallen back to the default: a caller who asked for
    `strict` and silently got `normalized` would have a report that says
    `normalized` and a belief that says otherwise.
    """
    try:
        return MATCHERS[name]
    except KeyError:
        raise ValueError(
            f"no matcher named {name!r}. akashi ships: {', '.join(sorted(MATCHERS))}. "
            f"The name is on the report and in its id, because which strings count "
            f"as the same string changes every count."
        ) from None
