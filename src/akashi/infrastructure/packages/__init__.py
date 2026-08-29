"""Reading the document that says what was sent.

akashi consumes ``tsumugi.context-package/1`` as JSON and imports `tsumugi`
nowhere -- not even in an adapter (ADR-0007). The dependency is on a published
contract, which is what lets akashi audit an answer from any pipeline that can
produce one, including a pipeline written in another language.
"""

from __future__ import annotations

from akashi.domain.package import ContextPackage, Protection

from .contextpackage import ACCEPTED_CONTRACT, load_package, read_package

__all__ = [
    "ACCEPTED_CONTRACT",
    "ContextPackage",
    "Protection",
    "load_package",
    "read_package",
]
