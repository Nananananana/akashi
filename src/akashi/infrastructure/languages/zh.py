"""Chinese: no spaces anywhere, which breaks every whitespace-based rule.

A segmenter that leans on whitespace produces one segment for a whole
paragraph of Chinese, and one segment is one verdict, so the whole paragraph
would stand or fall on its worst number. That is the reason
``needs_space_after`` exists as a per-pack property rather than a constant.

The terminators overlap with Japanese, and identically: ``。``, ``！`` and
``？`` end a sentence the same way in both. ``_rules`` asserts that the packs
agree rather than letting whichever loaded first decide.

The extraction rules do *not* overlap with Japanese, even where the characters
look similar. ``月`` is a month in both; ``个`` and ``天`` are Chinese and
``箇`` and ``日間`` are Japanese; and the money unit is ``元`` rather than
``円``. Two packs contributing the same pattern would be harmless -- overlaps
are resolved by a total order, not by which rule ran first -- but writing the
rules where they belong is what keeps a fourth language a data change.
"""

from __future__ import annotations

from akashi.domain.language import LanguagePack
from akashi.domain.particular import ExtractionRule, ParticularKind

__all__ = ["CHINESE"]

_DIGITS = r"(?:\d[\d,.]*\d|\d|[〇零一二三四五六七八九十百千两]+)"

#: A numeral safe to use without a marker bracketing it. Chinese numerals are
#: admitted only with a magnitude character, for the same reason as Japanese:
#: `一个` is the indefinite article as often as it is a count, and a particular
#: in every other sentence is noise a reader learns to ignore. `三个` is a real
#: quantity and is not found; the trade is deliberate and is the same one.
_MAGNITUDE = r"[〇零一二三四五六七八九两]*[十百千万亿][〇零一二三四五六七八九十百千万亿两]*"
_UNBRACKETED = r"(?:\d[\d,.]*\d|\d|" + _MAGNITUDE + r")"

#: Measure words and units. Longest first, so that 小时 wins over 时.
_UNITS = (
    r"(?:公斤|千克|毫克|公里|千米|厘米|毫米|毫升|小时|分钟|"
    r"个|人|件|次|台|本|张|条|只|辆|家|位|名|页|章|"
    r"克|吨|米|升|天|周|月|年|时|分|秒|倍|度|岁)"
)

CHINESE = LanguagePack(
    code="zh",
    version=1,
    terminators=frozenset("。！？"),
    needs_space_after=False,
    rules=(
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
            kind=ParticularKind.REFERENCE,
            pattern=r"第\s*" + _DIGITS + r"\s*(?:条|款|项|章|节|编|款|表|图|版|次)",
            priority=90,
        ),
        ExtractionRule(
            kind=ParticularKind.MONEY,
            pattern=_UNBRACKETED + r"\s*(?:万|亿)?\s*(?:元|人民币)",
            priority=75,
        ),
        ExtractionRule(
            kind=ParticularKind.QUANTITY,
            pattern=_UNBRACKETED + r"\s*(?:万|亿)?\s*" + _UNITS,
            priority=55,
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=r"[〇零一二三四五六七八九两]*[十百千万亿][〇零一二三四五六七八九十百千万亿两]*",
            priority=20,
            note="a magnitude character is required, so a one-character word is not read as a 1",
        ),
    ),
)
