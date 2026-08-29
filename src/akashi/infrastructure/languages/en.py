"""English: the hard one, because its terminator is four other things.

``.`` is a decimal point, an abbreviation marker, part of an ellipsis, a
version separator and a domain separator, and only sometimes the end of a
sentence. Every one of those is handled by a rule in ``domain/segment.py``
except the abbreviations, which cannot be a rule because they are a list.

**A list is never complete**, and that is the cost ADR-0009 records. Each miss
splits one sentence into two, which moves the denominator every count is over
and can turn one floating segment into two. The list below is the vocabulary
that actually appears in the documents this project is aimed at -- legal,
medical, technical and financial prose -- rather than a general-purpose one.
"""

from __future__ import annotations

from akashi.domain.language import LanguagePack
from akashi.domain.particular import ExtractionRule, ParticularKind

__all__ = ["ENGLISH"]

_ABBREVIATIONS = frozenset(
    {
        # Titles.
        "dr.",
        "prof.",
        "mr.",
        "mrs.",
        "ms.",
        "st.",
        "sr.",
        "jr.",
        "rev.",
        "hon.",
        # Latin, which survives entirely in the kinds of document being audited.
        "e.g.",
        "i.e.",
        "etc.",
        "cf.",
        "viz.",
        "vs.",
        "et al.",
        "al.",
        "ibid.",
        "op.",
        # Reference and citation, the ones that sit next to a number and so sit
        # next to a particular.
        "no.",
        "nos.",
        "fig.",
        "figs.",
        "eq.",
        "eqs.",
        "ref.",
        "refs.",
        "ch.",
        "chap.",
        "sec.",
        "secs.",
        "art.",
        "arts.",
        "para.",
        "paras.",
        "pt.",
        "vol.",
        "vols.",
        "p.",
        "pp.",
        "ed.",
        "eds.",
        "col.",
        "cols.",
        "tbl.",
        "app.",
        # Organisational, which end sentences often enough that getting them
        # wrong is visible.
        "inc.",
        "ltd.",
        "co.",
        "corp.",
        "plc.",
        "llc.",
        "dept.",
        "div.",
        "assn.",
        # Measurement and approximation.
        "approx.",
        "min.",
        "max.",
        "avg.",
        "est.",
        "ca.",
        "wt.",
        "vol%.",
        # Calendar, which sits next to dates and so next to particulars.
        "jan.",
        "feb.",
        "mar.",
        "apr.",
        "jun.",
        "jul.",
        "aug.",
        "sep.",
        "sept.",
        "oct.",
        "nov.",
        "dec.",
        "mon.",
        "tue.",
        "wed.",
        "thu.",
        "fri.",
        "sat.",
        "sun.",
        # Medical, where a wrong split sits next to a dosage.
        "b.i.d.",
        "t.i.d.",
        "q.d.",
        "p.o.",
        "p.r.n.",
        "u.s.p.",
    }
)

ENGLISH = LanguagePack(
    code="en",
    version=1,
    terminators=frozenset(".!?"),
    # ``example.com`` and ``2.4`` are not sentence ends, and the cheapest way
    # to know that is that nothing follows the stop but more text.
    needs_space_after=True,
    abbreviations=_ABBREVIATIONS,
    rules=(
        ExtractionRule(
            kind=ParticularKind.REFERENCE,
            pattern=(
                r"(?<![A-Za-z])(?:Sections?|Secs?\.|Articles?|Arts?\.|Clauses?|"
                r"Figs?\.|Figures?|Tables?|Chapters?|Chs?\.|Paragraphs?|Paras?\.|"
                r"Appendix|Annex|Exhibit|Schedule|Items?|Nos?\.|Rules?|Claims?)"
                r"\s*\d+(?:\.\d+)*(?:\s*\([a-z0-9]+\))*"
            ),
            priority=90,
            note="Section 4(b) -> Section 4(d) is a different obligation, and reads the same",
        ),
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=(
                r"(?<![A-Za-z])(?:January|February|March|April|May|June|July|August|"
                r"September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|"
                r"Sept|Oct|Nov|Dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?"
            ),
            priority=92,
        ),
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=(
                r"(?<![\d])\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|"
                r"June|July|August|September|October|November|December)(?:,?\s*\d{4})?"
            ),
            priority=92,
        ),
        ExtractionRule(
            kind=ParticularKind.DURATION,
            pattern=(
                r"(?<![\d])\d[\d,.]*\s*(?:days?|weeks?|months?|years?|hours?|minutes?|"
                r"seconds?|business days?)(?![A-Za-z])"
            ),
            priority=60,
        ),
        ExtractionRule(
            kind=ParticularKind.MONEY,
            pattern=(
                r"(?<![\d])\d[\d,]*(?:\.\d+)?\s*(?:trillion|billion|million|thousand)?"
                r"\s*(?:dollars|euros|pounds|yen)(?![A-Za-z])"
            ),
            priority=75,
        ),
        ExtractionRule(
            kind=ParticularKind.QUANTITY,
            pattern=(
                r"(?<![\d])\d[\d,.]*\s*(?:kilograms?|kilogrammes?|grams?|grammes?|"
                r"milligrams?|tonnes?|tons?|pounds?|ounces?|kilometres?|kilometers?|"
                r"metres?|meters?|centimetres?|centimeters?|millimetres?|millimeters?|"
                r"litres?|liters?|millilitres?|milliliters?|"
                r"percentage points|percent|per cent|"
                r"degrees?)(?![A-Za-z])"
            ),
            priority=76,
            note="a unit spelled out, which the SI alternation in the common pack cannot match",
        ),
    ),
)
