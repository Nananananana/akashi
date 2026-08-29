"""Turning a report into something a person or a program reads.

Two renderings, and the difference between them is only format. Neither
decides anything: a renderer that computed a number would be a second place a
verdict could come from.
"""

from __future__ import annotations

from .json_report import as_dict, as_json
from .text import as_text

__all__ = ["as_dict", "as_json", "as_text"]
