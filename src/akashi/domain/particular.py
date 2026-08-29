"""The unit of verification: a load-bearing token, and where it sits.

ADR-0004. Not the sentence -- a faithful paraphrase shares no substring with
its source, so a sentence-level exact match scores a correct answer and a
fabricated one identically. A *particular* is the part of a sentence that can
be falsified without changing anything else about it: a quantity, a date, a
sum of money, an article number, a version, a dosage.

Those are strings. A string is in the text that was sent or it is not, and no
model is needed to find out.

**What a kind is for.** The kind is not decoration. It is what makes
``contradicted`` possible in v0.4 -- an answer saying ``2.6kg`` where the source
says ``2.4kg`` is only recognisable as a *changed number* if both are known to
be masses. A particular with no kind can only ever be reported missing.

``PROPER_NOUN`` is declared here and extracted by nothing. Recognising a name
without a dictionary or a model is guessing, and both are refused (ADR-0001,
ADR-0003). It appears in every report's ``kinds_not_extracted`` rather than
being quietly absent (ADR-0005), and structural cases -- a name in front of
``株式会社``, a token in front of ``Inc.`` -- are worth building later because
they are evidence rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .span import Span
from .text import search_form

__all__ = ["ExtractionRule", "Particular", "ParticularKind"]


class ParticularKind(Enum):
    """What sort of thing a particular is.

    The set is closed and it is the same set in the published schema; a test
    asserts that, because there is no pydantic here to derive one from the
    other (ADR-0001).
    """

    NUMBER = "number"
    QUANTITY = "quantity"
    PERCENTAGE = "percentage"
    MONEY = "money"
    DATE = "date"
    TIME = "time"
    DURATION = "duration"
    REFERENCE = "reference"
    IDENTIFIER = "identifier"
    #: Declared, and extracted by nothing. See the module docstring.
    PROPER_NOUN = "proper_noun"


@dataclass(frozen=True, slots=True)
class ExtractionRule:
    """One pattern, and what it finds. Data, contributed by a language pack.

    The algorithm is in ``extraction.py`` and the rules are in
    ``infrastructure/languages/`` (ADR-0009). A fourth language is a module of
    these and a fixture set.
    """

    kind: ParticularKind
    #: A regular expression, as a string. Compiled by the extractor, which is
    #: the only thing that should know it is a regular expression at all.
    pattern: str
    #: Breaks a tie when two rules match exactly the same span. Higher wins.
    #: Length decides first; this is only for the genuine ties, and it is what
    #: makes ``1.2.3`` an identifier rather than a number.
    priority: int = 0
    #: For the person reading the pack. Reaches no output.
    note: str = ""

    def __post_init__(self) -> None:
        if not self.pattern:
            raise ValueError(f"the {self.kind.value} rule has no pattern")


@dataclass(frozen=True, slots=True)
class Particular:
    """One load-bearing token of the answer, and where it was found.

    ``span`` is in answer coordinates, not segment coordinates. A particular
    that could only be located relative to a segment would need the segmentation
    to be re-derived before a reader could open it, and a report is meant to
    stand on its own (ADR-0002).
    """

    kind: ParticularKind
    span: Span
    text: str
    segment_id: str = ""

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a particular with no text bears nothing")
        if len(self.text) != len(self.span):
            raise ValueError(
                f"{self.text!r} has {len(self.text)} characters but a span of "
                f"{len(self.span)}; an offset that has drifted points a reader at the "
                f"wrong number"
            )

    @property
    def form(self) -> str:
        """The comparison form: what resolution actually looks for.

        ``２.４kg`` and ``2.4kg`` are one particular. ``2.4kg`` and ``2.4 kg``
        are still two *strings* (see ``text.py``), and making them one
        *particular* is resolution's job rather than this one's -- the tolerance
        for text and the tolerance for a quantity are different questions and
        collapsing them here would answer the wrong one.
        """
        return search_form(self.text).text

    def describe(self) -> str:
        return f"{self.kind.value} {self.text!r} at {self.span.describe()}"
