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

#: Titles and honorifics that make what precedes them a person's name. A name
#: is a name because of what sits beside it; the marker is matched and not
#: captured, so ``田中医師`` yields ``田中``.
#: ``様`` and ``さま`` are **not** here, and dropping them cost a real case.
#: ``様`` ends 仕様, 模様, 多様, 同様 and 様々 -- words that appear in exactly
#: the specification and contract documents akashi is aimed at. It put a name on
#: ``筐体仕様`` on the first measured run, and one false proper noun per
#: specification is worse than missing ``佐藤様``: a precision-first extractor
#: that is not precise is worth nothing at all.
#:
#: ``君`` is out for the same reason (``暴君``, ``諸君``) and ``ちゃん`` because
#: it does not appear in the documents this is for.
_HONORIFIC = (
    r"(?:さん|氏(?![名族])|先生|医師|医長|教授|准教授|講師|"
    r"部長|課長|係長|社長|専務|常務|所長|主任|"
    r"弁護士|税理士|会計士|司法書士|行政書士)"
)

#: Runs that look like a surname before an honorific and are not one. Every
#: entry here was a false positive: ``皆さん`` is everyone, ``彼氏`` is a
#: boyfriend, ``主治医師`` is the attending physician. akashi is
#: precision-first, and one of these on every report is what makes a
#: precision-first extractor worthless.
#:
#: ``mamori`` keeps a much larger list of these because it is recall-first by
#: policy (its ADR-0013): it would rather over-detect a name than leak one.
#: This is the opposite trade and the list is the small end of it.
_NOT_A_NAME = frozenset(
    {
        "皆",
        "皆様",
        "客",
        "顧客",
        "御客",
        "疲",
        "彼",
        "彼女",
        "主治",
        "担当",
        "責任",
        "関係",
        "各",
        "全",
        "当",
        "弊",
        "本",
        "他",
        "貴",
        "御",
        "同",
        "前",
        "後",
        "上",
        "下",
        "先",
        "元",
        "現",
        "旧",
        "新",
        "大",
        "小",
        "中",
        "監督",
        "指導",
        "研修",
        "実習",
        "代表",
        "役員",
        "職員",
        "社員",
        "従業",
    }
)

#: Suffixes that make what precedes them an organisation. ``株式会社`` and its
#: kin are literal and unambiguous; a bare ``社`` is not, and is left out --
#: ``弊社``, ``当社`` and ``本社`` are ordinary words and akashi would put a
#: particular on every business document that used one.
_ORG_SUFFIX = (
    r"(?:株式会社|有限会社|合同会社|合資会社|商事|工業|銀行|証券|保険|"
    r"製薬|製作所|建設|電機|運輸|信託|組合)"
)

#: The body of an organisation name, tempered on particles. Borrowed from
#: ``mamori``: without it a greedy run of kana swallows the rest of the
#: sentence, so ``株式会社さくら商事の田中さん`` comes back as one name ending
#: in ``の田中``.
_ORG_STOP = r"の|は|が|を|に|へ|と|で|も|や|から|より|まで|および|ならびに"
_ORG_BODY = r"(?:(?!" + _ORG_STOP + r")[一-鿿぀-ゟ゠-ヿーA-Za-z0-9]){1,16}"

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

#: A denominator, in either script. See the Chinese pack for the defect this
#: closes: the first repair took Latin denominators only.
_PER = r"(?:/(?:" + _COUNTERS + r"|[A-Za-z]{1,4}))?"


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
            r"リットル|ミリリットル|パーセント|ポイント|キロ)" + _PER,
            priority=76,
            note="a unit spelled in katakana, which the SI alternation cannot match",
        ),
        ExtractionRule(
            kind=ParticularKind.QUANTITY,
            pattern=r"[-−+±]?" + _UNBRACKETED + r"\s*" + _COUNTERS + _PER,
            priority=55,
            note=(
                "the denominator belongs to the unit, in either script: a "
                "Japanese document writes `50mg/日` as readily as `50ミリグラム/日`"
            ),
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=r"[〇一二三四五六七八九]*[十百千万億兆][〇一二三四五六七八九十百千万億兆]*",
            priority=20,
            note="a kanji numeral with a magnitude in it, so that 一般 is not read as a 1",
        ),
        ExtractionRule(
            kind=ParticularKind.PROPER_NOUN,
            pattern=r"(?<![一-鿿])([一-鿿]{2,4})(?=" + _HONORIFIC + r")",
            priority=85,
            group=1,
            reject=_NOT_A_NAME,
            note="a name before an honorific; the honorific is evidence and not part of it",
        ),
        ExtractionRule(
            kind=ParticularKind.PROPER_NOUN,
            pattern=r"(?:株式会社|有限会社|合同会社|合資会社)" + _ORG_BODY,
            priority=86,
            note="株式会社さくら商事: the form is the evidence",
        ),
        ExtractionRule(
            kind=ParticularKind.PROPER_NOUN,
            pattern=r"(?<![一-鿿])" + _ORG_BODY + _ORG_SUFFIX,
            priority=86,
        ),
        ExtractionRule(
            kind=ParticularKind.PROPER_NOUN,
            pattern=r"(?<![一-鿿])[甲乙丙丁戊](?:社|方|側)(?![一-鿿])",
            priority=87,
            note=(
                "甲社 / 乙方: a party designation, which is a name in a contract "
                "and is the one a clause is actually about. Structural like every "
                "other rule here -- the stem is a closed set of five and the "
                "suffix is a closed set of three, so this reads a convention "
                "rather than recognising a name"
            ),
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=r"[〇一二三四五六七八九]{3,}",
            priority=20,
            note="a run long enough to be a numeral rather than a word",
        ),
    ),
)
