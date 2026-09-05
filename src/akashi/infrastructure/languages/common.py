"""The particulars that belong to no language.

An ISO date, a percentage, a version string and a bare number are written the
same way in a Japanese document and an English one, so they live here rather
than three times over. This pack claims no terminator: a percentage sign is not
anybody's punctuation.

Two things about the patterns are deliberate and easy to undo by accident.

**No ``\\b``.** Python's word boundary is defined from ``\\w``, which includes
CJK, so there is no boundary between a kanji and a digit -- ``\\b\\d{4}`` never
matches the year in ``西暦2026年``. Every boundary here is an explicit
lookaround instead.

**No decision about decimal conventions.** ``1,234.56`` and ``1.234,56`` are
the same quantity written by two civilisations that disagree, and telling them
apart needs to know which one wrote it. akashi never has to: it compares
strings, so a number is captured as the token it is and matched against the
token in the source. Guessing at a value would be inventing information the
audit does not need.
"""

from __future__ import annotations

from akashi.domain.language import LanguagePack
from akashi.domain.particular import ExtractionRule, ParticularKind

__all__ = ["COMMON"]

#: A run of digits with separators inside it, bounded so that it cannot start
#: or end in the middle of a longer one. ``234`` is not a number inside
#: ``1,234``, and reporting it as one would ground a figure nobody wrote.
_NUMBER = r"(?<![\d.,])\d(?:[\d,.]*\d)?(?![\d])"

#: A sign, where one belongs to the value. ``-20℃`` and ``20℃`` are different
#: temperatures and ``±0.02mm`` is a different tolerance from ``0.02mm``. The
#: hand-marked answers found this: the sign was being left behind, so an answer
#: that flipped one would have grounded against the value it was flipped from --
#: precisely the failure ADR-0004 exists for.
_SIGN = r"[-−+±]?"

#: A bare number, kept away from a letter *before* it. ``HbA1c`` is not a
#: figure and ``H2O`` is not a two, and a digit inside a word extracted as a
#: number is a particular a reader has to explain away on every report.
#:
#: A letter *after* is allowed, and the corpus is why. Forbidding both lost
#: ``350kPa`` entirely -- ``kPa`` is not in the SI alternation, so the bare rule
#: was the only thing seeing it, and an invented pressure became invisible. The
#: asymmetry is not arbitrary: a letter before a digit is a word carrying a
#: digit, and a letter after one is a unit the extractor does not know yet.
_BARE = r"(?<![A-Za-z])" + _NUMBER

#: The unit alternations are longest-first, because ``re`` takes the first
#: alternative that matches and ``m`` would otherwise win over ``mm``.
_SI = (
    r"(?:kg|mg|µg|ug|g|t|lbs|lb|oz|"
    r"km|cm|mm|µm|nm|m|ft|in|mi|"
    r"ml|mL|cc|L|l|"
    r"ms|µs|ns|s|min|hr|hrs|h|"
    r"GHz|MHz|kHz|Hz|kW|MW|W|kV|V|mAh|mA|A|"
    r"TB|GB|MB|KB|kB|B|bit|"
    r"°C|℃|°F|℉|K|ppm|px|pt|"
    # Trade units the corpus never wrote, because the person who wrote the
    # corpus wrote the unit list too. Drafted vocabulary asked for tyre
    # pressure and got `120psi`, which came out as a bare `120`.
    r"psi|bar|kPa|MPa|Pa|rpm|kn|kt|dB|cal|kcal|J|kJ|N|Nm|hp|kWh)"
)

#: What may follow a unit and still be part of the same unit.
#:
#: Found by `tools/draft_genres.py` on the first batch of vocabulary that did
#: not come from this repository's own author. The old rule stopped at the
#: lookahead after the unit, and `/` is not a letter or a digit, so:
#:
#:     320 km/h   ->  320 km      a speed became a distance
#:     10mg/mL    ->  10mg        a concentration became a mass
#:     20,000 m³  ->  20,000 m    a volume became a length
#:     120 m²     ->  120 m       an area became a length
#:
#: Every one of those is a particular akashi would then ground against a
#: document that says something else, and report `grounded`. Nine of eighteen
#: drafted values were this defect; none of the 30 hand-written corpus cases
#: contained the notation at all.
#:
#: Only the superscript characters, never a bare ``2`` or ``3``: ``m2`` in
#: running text is ``m`` followed by a number as often as it is a square metre,
#: and guessing which would trade a miss for a wrong answer.
#: A denominator may be spelled in the document's own script. `50mg/日` is a
#: Japanese document writing a Latin unit over a local one, and the SI rule here
#: matches before either language pack gets a turn -- so a tail that only took
#: Latin denominators repaired `320 km/h` and left `50mg/日` cut at the slash.
#: Bounded to three characters: a denominator is a unit, not a phrase.
_DENOMINATOR = r"(?:" + _SI + r"[²³]?|[一-鿿]{1,3})"

_UNIT_TAIL = r"[²³]?(?:/" + _DENOMINATOR + r")?"


COMMON = LanguagePack(
    code="und",
    version=1,
    terminators=frozenset(),
    needs_space_after=False,
    rules=(
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=r"(?<![\d-])\d{4}-\d{1,2}-\d{1,2}(?![\d-])",
            priority=90,
            note="ISO 8601, and the form every machine-written date arrives in",
        ),
        ExtractionRule(
            kind=ParticularKind.DATE,
            pattern=r"(?<![\d/])\d{4}/\d{1,2}/\d{1,2}(?![\d/])",
            priority=90,
            note="slashed, which a spreadsheet produces and a model repeats",
        ),
        ExtractionRule(
            kind=ParticularKind.TIME,
            pattern=r"(?<![\d:])\d{1,2}:\d{2}(?::\d{2})?(?![\d:])",
            priority=80,
        ),
        ExtractionRule(
            kind=ParticularKind.PERCENTAGE,
            pattern=_NUMBER + r"\s*[%％]",
            priority=70,
            note="the unit that turns a ratio into a claim about a population",
        ),
        ExtractionRule(
            kind=ParticularKind.MONEY,
            pattern=r"[¥￥$€£]\s*" + _NUMBER,
            priority=70,
        ),
        ExtractionRule(
            kind=ParticularKind.MONEY,
            pattern=_NUMBER + r"\s*(?:USD|JPY|EUR|GBP|CNY|KRW)(?![A-Za-z])",
            priority=70,
        ),
        ExtractionRule(
            kind=ParticularKind.IDENTIFIER,
            pattern=r"(?<![\w.])v?\d+\.\d+\.\d+(?:[.\-+][\w.]+)?(?![\w.])",
            priority=95,
            note="a version, which outranks the number rule on the same span",
        ),
        ExtractionRule(
            kind=ParticularKind.IDENTIFIER,
            pattern=r"(?<![A-Za-z0-9])[A-Z]{2,6}[ \-]?\d{3,}(?:-\d+)*(?![A-Za-z0-9])",
            priority=60,
            note="ISO 9001, ABC-1234: a letter prefix and a number that belong together",
        ),
        ExtractionRule(
            kind=ParticularKind.QUANTITY,
            pattern=_SIGN + _NUMBER + r"\s*" + _SI + _UNIT_TAIL + r"(?![A-Za-z0-9])",
            priority=50,
            note="the unit is part of the particular; 2.4kg and 2.4mg differ by it, "
            "and so do 320 km and 320 km/h",
        ),
        ExtractionRule(
            kind=ParticularKind.NUMBER,
            pattern=_BARE,
            priority=0,
            note="the fallback, and the lowest priority: anything more specific wins",
        ),
    ),
)
