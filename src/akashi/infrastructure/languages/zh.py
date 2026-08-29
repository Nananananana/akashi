"""Chinese: no spaces anywhere, which breaks every whitespace-based rule.

A segmenter that leans on whitespace produces one segment for a whole
paragraph of Chinese, and one segment is one verdict, so the whole paragraph
would stand or fall on its worst number. That is the reason
``needs_space_after`` exists as a per-pack property rather than a constant.

The terminators overlap with Japanese, and identically: ``。``, ``！`` and
``？`` end a sentence the same way in both. ``_rules`` asserts that the packs
agree rather than letting whichever loaded first decide.
"""

from __future__ import annotations

from akashi.domain.language import LanguagePack

__all__ = ["CHINESE"]

CHINESE = LanguagePack(
    code="zh",
    version=1,
    terminators=frozenset("。！？"),
    needs_space_after=False,
)
