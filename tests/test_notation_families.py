"""A notation that exists in more than one spelling must be read in all of them.

Four rounds of drafted vocabulary found the same defect four times, and it was
never the same rule twice:

| | landed in | missed | found by |
| --- | --- | --- | --- |
| `/` denominators | Latin | CJK | batch 2 |
| the katakana unit rule | the rule beside it | itself | a test written for the fix |
| feet and inches | English, Japanese | Chinese | batch 4 |
| compound duration | -- | built for three at once | this file exists so it stays that way |

The shape is always the same: **a repair is written against the examples that
prompted it, and those are whatever that batch happened to contain.** The
corpus cannot catch it, because the corpus has the same author as the rule.

`kinds_not_extracted` does not catch it either, and that is worth stating: it
answers *which kinds does no rule cover*, and every one of these defects was
**inside** a covered kind. `40'` and `12英尺` are both `quantity`; the Chinese
half being missing moved no kind.

So the check has to be a table, and the table has to be written by hand -- there
is no way to derive "these two notations are the same idea twice" from the rules
themselves. What it buys is that **adding a family for one spelling leaves a hole
somebody has to look at**, instead of a defect a later batch finds.

A cell holds a *list* of probes rather than one, and that is the second row of
the table above rather than a convenience: the katakana defect was two rules in
a single pack, one of them repaired and the one beside it not. A matrix with one
probe per script cannot see that, and the first version of this file could not.

The first hole it found was not a script half-fix at all: `120 sq ft`,
`120平方米` and `120平方メートル` each came out as a bare `120`, an area reduced
to a number in all three scripts at once. Fixed in the same commit, each half in
the pack that owns the spelling.

Adding a row is the cost, and it is the point: a family with no row is a family
nobody asked the question about.
"""

from __future__ import annotations

import pytest

from akashi.domain.extraction import extract_from_answer
from akashi.domain.segment import segment_answer
from akashi.infrastructure.languages import packs

SCRIPTS = ("en", "ja", "zh")

#: A whole sentence, and the particular it must yield.
#:
#: Sentences rather than bare values, because the boundary rules are half of
#: what these test -- `40'` inside `the 1990's` is a decade, and a probe with no
#: text around it would not know.
Probe = tuple[str, str]

#: One row per notation that exists in more than one script, and for each script
#: every spelling that script writes it in.
FAMILIES: dict[str, dict[str, tuple[Probe, ...]]] = {
    "compound duration": {
        "en": (("The lap was 1:45.32 exactly.", "1:45.32"),),
        "ja": (
            ("記録は1分30秒5でした。", "1分30秒5"),
            ("所要は2時間15分でした。", "2時間15分"),
        ),
        "zh": (
            ("用时1分30秒。", "1分30秒"),
            ("用时2小时15分。", "2小时15分"),
        ),
    },
    "feet and inches": {
        "en": (("A 40' container shipped.", "40'"),),
        "ja": (("全長は8フィートです。", "8フィート"),),
        "zh": (("高度是6英寸。", "6英寸"),),
    },
    "a unit over a unit": {
        "en": (("Speed was 320 km/h then.", "320 km/h"),),
        "ja": (
            ("用量は50mg/日です。", "50mg/日"),
            # The katakana rule beside the SI one. This is the row of the table
            # above that no per-script probe could have reached.
            ("用量は5ミリグラム/日です。", "5ミリグラム/日"),
        ),
        "zh": (
            ("速度是320 千米/小时。", "320 千米/小时"),
            ("剂量是50mg/日。", "50mg/日"),
        ),
    },
    "a thousands separator": {
        "en": (("Total 45,000 units shipped.", "45,000"),),
        "ja": (("合計は４５，０００円です。", "４５，０００円"),),
        "zh": (("共有１，０００辆。", "１，０００辆"),),
    },
    "an area or a volume": {
        # English puts the dimension before the unit and the other two after,
        # which is why the shared superscript tail could not be the whole answer.
        "en": (
            ("The area is 120 m² exactly.", "120 m²"),
            ("The site covers 120 sq ft exactly.", "120 sq ft"),
            ("The tank holds 3 cubic metres now.", "3 cubic metres"),
        ),
        "ja": (
            ("容量は20,000 m³です。", "20,000 m³"),
            ("面積は120平方メートルです。", "120平方メートル"),
        ),
        "zh": (
            ("面积是120 m²。", "120 m²"),
            ("面积是120平方米。", "120平方米"),
        ),
    },
    "a percentage": {
        "en": (("Revenue rose 12.5% again.", "12.5%"),),
        "ja": (("増加は12.5%でした。", "12.5%"),),
        "zh": (("增长了12.5%。", "12.5%"),),
    },
}


def extracted(sentence: str, script: str) -> list[str]:
    """Read with **that script's pack alone**, plus the shared one.

    Not with every pack loaded, which is what the first version of this file
    did -- and a poison that removed the Chinese duration chain went straight
    through it, because the Japanese rule matched the Chinese sentence. `分` and
    `秒` are written the same in both, so a sibling's rule can answer a question
    that was asked about this pack.

    The default really does load all of them, so that reading is not wrong. It
    is just not the question: whether Chinese is read **by the Chinese pack** is
    what a hole in this table is supposed to be about.
    """
    chosen = packs(script)
    return [one.text for one in extract_from_answer(segment_answer(sentence, chosen), chosen)]


@pytest.mark.parametrize("family", sorted(FAMILIES), ids=lambda name: name.replace(" ", "-"))
@pytest.mark.parametrize("script", SCRIPTS)
def test_a_notation_is_read_in_every_script_that_writes_it(family: str, script: str) -> None:
    """The cell. A hole here is the defect four batches found four times."""
    for sentence, wanted in FAMILIES[family][script]:
        found = extracted(sentence, script)
        assert wanted in found, (
            f"{family!r} is read in the other spellings and not in {wanted!r}: "
            f"{sentence!r} gave {found}"
        )


def test_every_family_has_a_cell_for_every_script() -> None:
    """A row missing a script is a question nobody asked, and it would make the
    parametrisation above silently smaller rather than red."""
    for family, probes in FAMILIES.items():
        assert set(probes) == set(SCRIPTS), (
            f"{family!r} has no probe for {set(SCRIPTS) - set(probes)}"
        )
        for script, cell in probes.items():
            assert cell, f"{family}/{script} has an empty cell, which passes vacuously"


def test_the_table_is_not_empty_and_covers_more_than_one_family() -> None:
    """Both tests above pass on an empty table, which is the shape of check
    this repository has caught itself writing before."""
    assert len(FAMILIES) >= 5
    assert sum(len(cell) for row in FAMILIES.values() for cell in row.values()) >= 20


def test_some_script_writes_a_family_more_than_one_way() -> None:
    """The second row of the table in the module docstring: the katakana rule
    was missed by the repair *beside* it, in the same pack. A matrix of one
    probe per script cannot fail on that, so a matrix that has quietly collapsed
    to one probe per script has lost the case it was widened for."""
    widest = max(len(cell) for row in FAMILIES.values() for cell in row.values())
    assert widest >= 2


def test_a_probe_is_a_sentence_and_not_a_bare_value() -> None:
    """The boundary rules are half of what these test. `40'` on its own does
    not distinguish a foot mark from the apostrophe in `the 1990's`, and a
    probe that cannot fail on a boundary is a probe about half the rule."""
    for family, probes in FAMILIES.items():
        for script, cell in probes.items():
            for sentence, wanted in cell:
                where = f"{family}/{script}/{wanted}"
                assert sentence != wanted, f"{where}: the probe is the value"
                assert wanted in sentence, f"{where}: the value is not in its own sentence"
                # Text on both sides, rather than a character count: a Japanese
                # sentence is dense, and a margin that reads as generous in
                # English rejected `用时1分30秒。` for being eight characters.
                at = sentence.index(wanted)
                assert at > 0, f"{where}: nothing before the value"
                assert sentence[at + len(wanted) :], f"{where}: nothing after the value"


def test_kinds_not_extracted_would_not_have_caught_any_of_these() -> None:
    """Stated as a test because it is the reason this file exists rather than a
    line in `coverage`.

    Every defect this table guards was **inside** a covered kind: `40'` and
    `12英尺` are both `quantity`, and the Chinese half being missing moved no
    kind at all. A check that asks "which kinds does nothing cover" is blind to
    "which spellings of a covered kind does nothing cover".
    """
    from akashi.domain.extraction import kinds_not_extracted

    for script in SCRIPTS:
        assert kinds_not_extracted(packs(script)) == (), (
            f"{script} now misses a kind outright; this file is about the other case"
        )
