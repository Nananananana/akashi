"""One labelled case, and the refusal to trust an offset somebody typed.

A case is a folder: a real ContextPackage, a response, and a manifest saying
what was planted in the response and where. The manifest is the ground truth,
and it is only ground truth because every span in it is *derived* -- from the
markup in the source, or from the mutation the generator applied -- and never
written by hand.

This project has already paid for that lesson once. Three of the four
hand-written fixture anchors in v0.1 were the wrong length on their first run,
and they were four anchors written carefully by somebody who knew what they
were for. A corpus annotated that way measures the annotator.

So the loader re-derives what it can and refuses a case that disagrees with its
own files. A broken fixture fails the build; it does not fail a correct
implementation.

**Three booleans, and they are not the same question.**

``expect_detected``   should akashi flag this span?
``is_hallucination``  is the span actually wrong?
``declared_miss``     is akashi's silence here a stated limit rather than a bug?

Most plants set the first two together. The ones that do not are the reason the
corpus is worth more than a hallucination benchmark:

- a ``faithful_paraphrase`` is not a hallucination and must not be flagged --
  flagging it is a false positive, and false positives are what decide whether
  a reader keeps reading the reports;
- a ``cross_document_stitch`` *is* a hallucination and will not be flagged,
  because ADR-0004 says so out loud. Counting those and publishing the count is
  the most honest line the measurement document will carry;
- a ``derived_value`` is not a hallucination and *will* be flagged, because
  akashi does no arithmetic. That is an acknowledged false positive and it gets
  its own number rather than being hidden in the others.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from akashi.domain.package import ContextPackage
from akashi.domain.span import Span
from akashi.errors import ContractError
from akashi.infrastructure.packages import load_package

__all__ = [
    "MANIFEST",
    "Case",
    "Plant",
    "PlantKind",
    "Source",
    "Split",
    "load_case",
    "load_cases",
]

MANIFEST = "case.json"
PACKAGE = "package.json"
RESPONSE = "response.txt"

#: The manifest format, so a case written against an older one is refused
#: rather than read with the wrong meaning.
CASE_FORMAT = "akashi.case/1"


class PlantKind(Enum):
    """What was done to a span of the response.

    ``omitted_source`` is absent, and deliberately: ADR-0012 withdrew it once
    it turned out that an omission carries no text to plant against. A plant
    nothing can detect measures nothing.
    """

    #: One digit of a grounded number changed. 2.4kg -> 2.6kg.
    DIGIT_DRIFT = "digit_drift"
    #: The unit changed and the number kept. kg -> g, 万円 -> 億円.
    UNIT_SWAP = "unit_swap"
    #: A particular replaced by one of the same kind from a different item of
    #: the same package. It still resolves, so akashi passes it.
    ENTITY_SWAP = "entity_swap"
    #: A particular present nowhere in the package.
    INVENTED_PARTICULAR = "invented_particular"
    #: The meaning reversed with every particular left intact.
    NEGATION_FLIP = "negation_flip"
    #: Subject from one item, predicate from another, both verbatim.
    CROSS_DOCUMENT_STITCH = "cross_document_stitch"
    #: A true restatement with no substring in common with its source.
    FAITHFUL_PARAPHRASE = "faithful_paraphrase"
    #: A correct sum of two grounded numbers, which is in neither.
    DERIVED_VALUE = "derived_value"
    #: A `mamori` placeholder left in the answer. ADR-0008's path.
    PLACEHOLDER_RESIDUE = "placeholder_residue"
    #: Untouched, and grounded by construction. The control.
    GROUNDED = "grounded"


class Split(Enum):
    """Which half of the corpus a case is in.

    Nothing reads ``held_out`` except a command that says it is doing so. A
    held-out split that anything touches by default is a training split with a
    different name.
    """

    TRAIN = "train"
    HELD_OUT = "held_out"


@dataclass(frozen=True, slots=True)
class Source:
    """Where the truth about a plant lives in the package."""

    document_id: str
    span: Span

    def matches(self, document_id: str, span: Span) -> bool:
        return self.document_id == document_id and self.span == span

    def describe(self) -> str:
        return f"{self.document_id}[{self.span.start}:{self.span.end}]"


@dataclass(frozen=True, slots=True)
class Plant:
    """One thing that was done to the response, and what should follow."""

    kind: PlantKind
    #: Where it sits in the response.
    span: Span
    #: What the response says there.
    text: str
    #: What the source says instead, when the plant replaced something.
    was: str = ""
    #: Where ``was`` can be found in the package. Present when the plant
    #: replaced a grounded particular, and what source localisation is scored
    #: against.
    source: Source | None = None
    #: Should akashi flag this span?
    expect_detected: bool = True
    #: Is the span actually wrong?
    is_hallucination: bool = True
    #: Is akashi's silence here a stated limit rather than a defect?
    declared_miss: bool = False
    #: What akashi should ultimately say. ``contradicted`` for the plants that
    #: replaced a value, which v0.1 reports as ``floating`` -- the difference
    #: is what verdict correctness measures, and it is the number that should
    #: rise when v0.4 ships rather than a failure to fix now.
    expect_verdict: str = "floating"

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError(f"the {self.kind.value} plant covers no text")
        if len(self.text) != len(self.span):
            raise ValueError(
                f"the {self.kind.value} plant says {len(self.text)} characters and its "
                f"span covers {len(self.span)}"
            )
        if self.declared_miss and self.expect_detected:
            raise ValueError(
                f"the {self.kind.value} plant is a declared miss and expects detection. "
                f"A miss akashi is expected to catch is not a miss."
            )

    @property
    def is_control(self) -> bool:
        """Planted to catch a false positive rather than to be caught."""
        return not self.is_hallucination and not self.expect_detected

    @property
    def is_acknowledged_false_positive(self) -> bool:
        """Not a hallucination, and akashi flags it anyway, and says why.

        ``derived_value``: a correct sum is in neither source, so it floats.
        Correct under the definition and useless to the reader, which is why it
        is on ``STANDING_LIMITS`` and why it gets its own number here.
        """
        return not self.is_hallucination and self.expect_detected

    def describe(self) -> str:
        where = f" (source {self.source.describe()})" if self.source else ""
        return f"{self.kind.value} {self.text!r} at [{self.span.start}:{self.span.end}]{where}"


@dataclass(frozen=True, slots=True)
class Case:
    """One package, one response, and the truth about what is in it."""

    case_id: str
    language: str
    genre: str
    package: ContextPackage
    response: str
    plants: tuple[Plant, ...] = ()
    split: Split = Split.TRAIN
    generator: str = ""
    seed: int = 0
    tier: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("a case with no id cannot be reported on")
        for plant in self.plants:
            if plant.span.slice(self.response) != plant.text:
                raise ValueError(
                    f"{self.case_id}: the {plant.kind.value} plant says {plant.text!r} at "
                    f"[{plant.span.start}:{plant.span.end}] and the response says "
                    f"{plant.span.slice(self.response)!r} there"
                )
            self._check_source(plant)

    def _check_source(self, plant: Plant) -> None:
        """A plant that names a source must name one the package really holds.

        akashi never reads the corpus, but it holds the item text and the item
        anchors -- so a source span that falls inside an item can be sliced and
        compared to ``was``. That is the only part of the ground truth that can
        be checked against something other than itself, and it is the part
        source localisation is scored on.
        """
        if plant.source is None or not plant.was:
            return
        for item in self.package.evidence.items:
            anchor = item.anchor
            if anchor.document_id != plant.source.document_id:
                continue
            if not anchor.span.contains(plant.source.span):
                continue
            inside = Span(
                plant.source.span.start - anchor.span.start,
                plant.source.span.end - anchor.span.start,
            )
            if inside.slice(item.text) != plant.was:
                raise ValueError(
                    f"{self.case_id}: the {plant.kind.value} plant says the source holds "
                    f"{plant.was!r} at {plant.source.describe()}, and {item.item_id} holds "
                    f"{inside.slice(item.text)!r} there"
                )
            return
        raise ValueError(
            f"{self.case_id}: the {plant.kind.value} plant names the source "
            f"{plant.source.describe()}, which is inside no item of the package. A "
            f"localisation target akashi could never reach is not a target."
        )

    @property
    def in_ci_tier(self) -> bool:
        return "ci" in self.tier

    def plants_of(self, kind: PlantKind) -> tuple[Plant, ...]:
        return tuple(plant for plant in self.plants if plant.kind is kind)

    @property
    def hallucinations(self) -> tuple[Plant, ...]:
        return tuple(plant for plant in self.plants if plant.is_hallucination)

    @property
    def controls(self) -> tuple[Plant, ...]:
        return tuple(plant for plant in self.plants if plant.is_control)

    @property
    def declared_misses(self) -> tuple[Plant, ...]:
        return tuple(plant for plant in self.plants if plant.declared_miss)


def _span(raw: object, where: str) -> Span:
    if not isinstance(raw, list) or len(raw) != 2:
        raise ContractError(f"{where} is not a two-element span: {raw!r}")
    start, end = raw
    if not isinstance(start, int) or not isinstance(end, int):
        raise ContractError(f"{where} has a non-integer offset: {raw!r}")
    try:
        return Span(start, end)
    except ValueError as error:
        raise ContractError(f"{where} is not a usable span: {error}") from error


def _checked_text(raw: dict[str, object], span: Span, response: str, at: str) -> str:
    """The text at ``span``, checked against what the manifest claims is there.

    The manifest's ``text`` is not the source of truth -- the response is -- and
    it is not redundant either. Deriving the text and trusting the span would
    make the check vacuous: an edited response would silently move every plant
    onto different words, and the manifest would agree with itself all the way
    down. Carrying both and comparing them is what turns an offset into
    something a build can verify.
    """
    found = span.slice(response)
    claimed = raw.get("text")
    if not isinstance(claimed, str):
        raise ContractError(
            f"{at} has no 'text'. It is what checks the span: without it an edited "
            f"response moves every plant onto different words and nothing notices."
        )
    if claimed != found:
        raise ContractError(
            f"{at} says {claimed!r} at [{span.start}:{span.end}] and the response says "
            f"{found!r} there. The manifest and the response disagree, and a manifest "
            f"that disagrees with its own files is not ground truth."
        )
    return found


def _plant(raw: object, response: str, index: int, where: str) -> Plant:
    if not isinstance(raw, dict):
        raise ContractError(f"{where}.plants[{index}] is not an object")
    at = f"{where}.plants[{index}]"

    try:
        kind = PlantKind(raw.get("kind"))
    except ValueError:
        raise ContractError(
            f"{at} has the kind {raw.get('kind')!r}, which akashi does not know. "
            f"It knows {sorted(one.value for one in PlantKind)}."
        ) from None

    span = _span(raw.get("span"), f"{at}.span")
    source: Source | None = None
    if isinstance(raw.get("source"), dict):
        body = raw["source"]
        source = Source(
            document_id=str(body.get("document_id", "")),
            span=_span(body.get("span"), f"{at}.source.span"),
        )

    try:
        return Plant(
            kind=kind,
            span=span,
            text=_checked_text(raw, span, response, at),
            was=str(raw.get("was", "")),
            source=source,
            expect_detected=bool(raw.get("expect_detected", True)),
            is_hallucination=bool(raw.get("is_hallucination", True)),
            declared_miss=bool(raw.get("declared_miss", False)),
            expect_verdict=str(raw.get("expect_verdict", "floating")),
        )
    except ValueError as error:
        raise ContractError(f"{at} is not a usable plant: {error}") from error


def load_case(folder: Path | str) -> Case:
    """Read one case folder, and refuse one that disagrees with itself."""
    root = Path(folder)
    manifest_path = root / MANIFEST
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ContractError(f"cannot read {manifest_path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ContractError(f"{manifest_path} is not JSON: {error}") from error

    if not isinstance(manifest, dict):
        raise ContractError(f"{manifest_path} is not an object")

    declared = manifest.get("format")
    if declared != CASE_FORMAT:
        raise ContractError(
            f"{manifest_path} declares the format {declared!r}; akashi reads "
            f"{CASE_FORMAT!r}. A case written against an older format is refused "
            f"rather than read with the wrong meaning."
        )

    try:
        response = (root / RESPONSE).read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError(f"cannot read {root / RESPONSE}: {error}") from error

    package = load_package(root / PACKAGE)
    case_id = str(manifest.get("case_id") or root.name)

    try:
        split = Split(manifest.get("split", "train"))
    except ValueError:
        raise ContractError(
            f"{case_id} is in the split {manifest.get('split')!r}; akashi knows "
            f"{sorted(one.value for one in Split)}."
        ) from None

    raw_plants = manifest.get("plants", [])
    if not isinstance(raw_plants, list):
        raise ContractError(f"{case_id} has a 'plants' that is not a list")

    try:
        return Case(
            case_id=case_id,
            language=str(manifest.get("language", "")),
            genre=str(manifest.get("genre", "")),
            package=package,
            response=response,
            plants=tuple(
                _plant(raw, response, index, case_id) for index, raw in enumerate(raw_plants)
            ),
            split=split,
            generator=str(manifest.get("generator", "")),
            seed=int(manifest.get("seed", 0)),
            tier=tuple(str(name) for name in manifest.get("tier", [])),
        )
    except ValueError as error:
        raise ContractError(f"{case_id} is not a usable case: {error}") from error


def _folders(root: Path) -> Iterator[Path]:
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / MANIFEST).is_file():
            yield child


def load_cases(
    root: Path | str,
    *,
    splits: Sequence[Split] = (Split.TRAIN,),
    tier: str = "",
) -> tuple[Case, ...]:
    """Every case under ``root``, in a fixed order.

    ``splits`` defaults to the training half alone. Reading the held-out half
    is possible and has to be asked for: a held-out split that anything touches
    by default is a training split with a different name.
    """
    location = Path(root)
    if not location.is_dir():
        raise ContractError(f"no case directory at {location}")

    found = [load_case(folder) for folder in _folders(location)]
    chosen = [case for case in found if case.split in splits]
    if tier:
        chosen = [case for case in chosen if tier in case.tier]
    return tuple(sorted(chosen, key=lambda case: case.case_id))
