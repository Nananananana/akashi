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
from akashi.domain.particular import ExtractionRule, ParticularKind

__all__ = ["JAPANESE"]

#: Arabic digits or the kanji ones. Both occur, often in the same document:
#: a price is written 1,200 and a clause number 第三十条.
_DIGITS = r"(?:\d[\d,.]*\d|\d|[〇一二三四五六七八九十百千]+)"

#: A numeral safe to use *without* a bracketing marker around it. Kanji
#: numerals are only admitted when they carry a magnitude character, because
#: `一` is also the first character of `一般`, `一部`, `一体` and a hundred other
#: ordinary words -- and `一部` read as "one copy" would put a particular in
#: every other Japanese sentence, each of which then has to ground somewhere.
#:
#: The cost is real and is the other half of the same trade: `三人` is a
#: genuine quantity and is not found, because nothing distinguishes it from a
#: word except a dictionary. Recall lost on small bare numerals, precision kept
#: everywhere. A false find is what a reader judges the tool by.
_UNBRACKETED = (
    r"(?:\d[\d,.]*\d|\d|[〇一二三四五六七八九]*[十百千万億兆][〇一二三四五六七八九十百千万億兆]*)"
)

#: Counters. Japanese attaches one to almost every number, which is what makes
#: a quantity recognisable here without a unit table: 3人 and 3日 are as much
#: quantities as 3kg is. Longest first.
_COUNTERS = (
    r"(?:時間|分間|週間|年間|日間|か月|ヶ月|箇月|カ月|"
    r"人|件|回|台|個|本|枚|冊|名|部|棟|軒|口|通|点|品|"
    r"日|月|年|週|時|分|秒|割|倍|度|階|位|歳|才)"
)

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
    rules=(
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=r"(?:令和|平成|昭和|大正|明治)\s*(?:元|\d{1,2})年(?:\s*\d{1,2}月)?(?:\s*\d{1,2}日)?",
            priority=99,
            note="an era date: the era is half the information and the year alone means nothing",
        ),
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=r"(?<![\d])\d{4}\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?",
            priority=95,
        ),
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=r"(?<![\d])\d{1,2}\s*月\s*\d{1,2}\s*日",
            priority=94,
        ),
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=r"[〇一二三四五六七八九]{4}年(?:\s*[〇一二三四五六七八九十]{1,3}月)?(?:\s*[〇一二三四五六七八九十]{1,3}日)?",
            priority=94,
            note="二〇二六年: a year in kanji numerals, which the number rules cannot see",
        ),
        ExtractionRule(
            kind=ParticularKind.REFERENCE,
            pattern=r"第\s*" + _DIGITS + r"\s*(?:条|項|号|章|節|款|編|表|図|巻|版|回|条の\d+)",
            priority=90,
            note="第30条 -> 第13条 is the failure this whole project is aimed at",
        ),
        ExtractionRule(
            kind=ParticularKind.MONEY,
            pattern=_UNBRACKETED + r"\s*(?:兆|億|万)?\s*円",
            priority=75,
            note="万 and 億 are multipliers and belong inside the particular",
        ),
        ExtractionRule(
            kind=ParticularKind.QUANTITY,
            pattern=_UNBRACKETED + r"\s*(?:キログラム|グラム|ミリグラム|トン|"
            r"キロメートル|メートル|センチメートル|ミリメートル|センチ|ミリ|"
            r"リットル|ミリリットル|パーセント|ポイント|キロ)",
            priority=76,
            note="a unit spelled in katakana, which the SI alternation cannot match",
        ),
        ExtractionRule(
            kind=ParticularKind.QUANTITY,
            pattern=r"[-−+±]?" + _UNBRACKETED + r"\s*" + _COUNTERS,
            priority=55,
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=r"[〇一二三四五六七八九]*[十百千万億兆][〇一二三四五六七八九十百千万億兆]*",
            priority=20,
            note="a kanji numeral with a magnitude in it, so that 一般 is not read as a 1",
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=r"[〇一二三四五六七八九]{3,}",
            priority=20,
            note="a run long enough to be a numeral rather than a word",
        ),
    ),
)
