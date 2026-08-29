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
)
