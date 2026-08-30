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

#: Titles that make what precedes them a person's name. Chinese surnames are
#: routinely one character -- 李, 王, 张 -- so the candidate may be shorter than
#: the Japanese one, which is why the stoplist below has to be longer.
_TITLE = (
    r"(?:医生|医師|大夫|教授|副教授|讲师|老师|先生|女士|小姐|"
    r"经理|总监|主任|院长|部长|律师|会计师|工程师)"
)

#: What may sit immediately before a name. Chinese has no spaces, so a name is
#: always preceded by a character -- a lookbehind on "not a kanji" rejects every
#: real case and lets a wrong one through, because the engine simply restarts one
#: character later and takes ``治`` out of ``主治医生``.
#:
#: So the rule requires a connector instead. That is more evidence rather than
#: less: a surname in this construction follows 为, 是, 由, punctuation or the
#: start of the segment, and never the middle of a word.
_BEFORE_NAME = r"(?:^|[为是由的给找请与和及，。、：；（）()\s])"

#: Determiners a name may not begin with. ``各部门经理`` is every department's
#: manager and not a person called 各部门, and a stoplist of whole words cannot
#: catch it -- there is one for each noun in the language. Guarding the first
#: character does.
_NOT_FIRST = r"(?![各全本该此每某诸前后新旧老总副])"

#: Every entry was a false positive. ``主治医生`` is the attending physician and
#: ``责任`` is responsibility, not a surname. akashi is precision-first: one of
#: these on every report is what makes a precision-first extractor worthless.
_NOT_A_NAME = frozenset(
    {
        "主治",
        "主管",
        "责任",
        "负责",
        "相关",
        "各",
        "全",
        "本",
        "该",
        "此",
        "前",
        "后",
        "上",
        "下",
        "大",
        "小",
        "中",
        "新",
        "旧",
        "老",
        "总",
        "副",
        "代理",
        "指导",
        "实习",
        "住院",
        "门诊",
        "专科",
        "首席",
        "执行",
    }
)

#: Organisation suffixes. ``公司`` is literal and unambiguous in a way a bare
#: ``社`` is not.
_ORG_SUFFIX = (
    r"(?:股份有限公司|有限责任公司|有限公司|公司|集团|银行|证券|保险|"
    r"研究院|研究所|事务所)"
)

#: Tempered on the particles a greedy run would otherwise swallow. The idea is
#: ``mamori``'s and the reason is the same: without it, one name eats the
#: sentence after it.
#: The connectors are in here as well as in ``_BEFORE_NAME``, and they have to
#: be. ``^`` matches at offset zero without consuming anything, so a body that
#: could contain ``由`` would take it: ``由中信证券`` came back as one name
#: starting with the preposition. The cost is a company whose name genuinely
#: contains one of these -- 三和銀行 is truncated -- and ``mamori`` accepted the
#: same trade for the same reason.
_ORG_STOP = r"的|和|与|及|或|在|从|到|对|向|为|是|由|给|请|找"
_ORG_BODY = r"(?:(?!" + _ORG_STOP + r")[一-鿿A-Za-z0-9]){1,16}"

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
            kind=ParticularKind.PROPER_NOUN,
            pattern=_BEFORE_NAME + r"(" + _NOT_FIRST + r"[一-鿿]{1,3})(?=" + _TITLE + r")",
            priority=85,
            group=1,
            reject=_NOT_A_NAME,
            note="a name before a title; the title is evidence and not part of it",
        ),
        ExtractionRule(
            kind=ParticularKind.PROPER_NOUN,
            pattern=_BEFORE_NAME + r"(" + _ORG_BODY + _ORG_SUFFIX + r")",
            priority=86,
            group=1,
            note="the connector is matched, so a name cannot start with one",
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=r"[〇零一二三四五六七八九两]*[十百千万亿][〇零一二三四五六七八九十百千万亿两]*",
            priority=20,
            note="a magnitude character is required, so a one-character word is not read as a 1",
        ),
    ),
)
