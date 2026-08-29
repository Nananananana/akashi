"""Building a case, so that what is true about it is known rather than judged.

ADR-0010. The prose is authored; the *labels* are computed. That split is the
whole method: a person or a model writing "this sentence is a hallucination" is
an annotator, and a corpus of annotations measures the annotator. A generator
that takes an authored sentence, records which fact it was built from, and
computes where that sentence landed in the response is recording arithmetic.

**Facts are marked in the source, tightly.** ``{{F:tent_weight}}2.4kg{{/F}}``:
a fact is exactly the particular, not the clause around it, so that a plant's
``was`` and the span its ``source`` names are the same string by construction.
The markup is stripped and the offsets are computed; nothing is typed.

**The seed shuffles, it does not invent.** Every sentence a genre carries is
used exactly once across that genre's cases, so coverage is a property of the
data rather than of the draw. What the seed decides is which sentences sit
together and in what order -- which is worth varying, because a segment's
neighbours are what a segmenter sees.

**No model runs here.** A model wrote the prose, once, at authoring time; this
composes it. CI calls nothing (ADR-0003).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from akashi.domain.span import Span

from .case import CASE_FORMAT, PlantKind

__all__ = [
    "GENERATOR",
    "Document",
    "GenreSpec",
    "SentenceSpec",
    "build_case",
    "strip_facts",
    "write_case",
]

#: Bumped when the composition changes in a way that moves an offset. The
#: fixtures record it, so a case built by an older generator is recognisable.
GENERATOR = "akashi.cases/1"

_FACT = re.compile(r"\{\{F:([a-z0-9_]+)\}\}(.*?)\{\{/F\}\}", re.DOTALL)

#: What each plant kind means, as labels. Kept here rather than on the spec so
#: that a genre author cannot accidentally mislabel a kind -- the kind *is* the
#: label, and a spec that wanted different labels would be describing a
#: different kind.
_LABELS: dict[PlantKind, tuple[bool, bool, bool, str]] = {
    # kind: (expect_detected, is_hallucination, declared_miss, expect_verdict)
    PlantKind.GROUNDED: (False, False, False, "grounded"),
    PlantKind.DIGIT_DRIFT: (True, True, False, "contradicted"),
    PlantKind.UNIT_SWAP: (True, True, False, "contradicted"),
    PlantKind.INVENTED_PARTICULAR: (True, True, False, "floating"),
    PlantKind.DERIVED_VALUE: (True, False, False, "floating"),
    PlantKind.ENTITY_SWAP: (False, True, True, "grounded"),
    PlantKind.NEGATION_FLIP: (False, True, True, "grounded"),
    PlantKind.CROSS_DOCUMENT_STITCH: (False, True, True, "grounded"),
    PlantKind.FAITHFUL_PARAPHRASE: (False, False, False, "unbearing"),
    PlantKind.PLACEHOLDER_RESIDUE: (False, False, False, "unverifiable"),
}


@dataclass(frozen=True, slots=True)
class Fact:
    """One particular in a source document, and where it sits in it."""

    fact_id: str
    text: str
    span: Span
    document_id: str


@dataclass(frozen=True, slots=True)
class Document:
    """One source document, as paragraphs with facts marked in them."""

    document_id: str
    source_path: str
    section: str
    paragraphs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SentenceSpec:
    """One authored sentence, and what was done to it.

    ``target`` is the substring the plant covers. Empty means the whole
    sentence, which is what a negation flip or a paraphrase affects -- there is
    no single token to point at, and pointing at one would be a claim the plant
    does not make.
    """

    kind: PlantKind
    text: str
    target: str = ""
    #: The fact this sentence's plant replaced. Gives the plant its ``was`` and
    #: its ``source``, which is what source localisation is scored against.
    fact: str = ""
    #: Override the verdict the kind implies. Needed where a flip leaves a
    #: sentence with no particulars in it at all.
    expect_verdict: str = ""


@dataclass(frozen=True, slots=True)
class GenreSpec:
    """Everything one genre contributes: its sources, and its sentences."""

    language: str
    genre: str
    question: str
    documents: tuple[Document, ...]
    sentences: tuple[SentenceSpec, ...]
    #: Written into every case's package. A case that declares protection also
    #: carries a placeholder in its response, and the runner expects a refusal.
    protected: bool = False
    #: Which tiers a case belongs to. Every case is in ``ci`` today, because
    #: the whole corpus audits in about a second and a tier that excluded
    #: nothing useful would be a distinction pretending to be an optimisation.
    #: The field is here for the corpus this one is a tenth the size of.
    tier: tuple[str, ...] = field(default_factory=lambda: ("ci",))


def strip_facts(text: str, document_id: str) -> tuple[str, tuple[Fact, ...]]:
    """Remove the markup and compute where each fact ended up.

    The offsets are of the stripped text, which is what a package carries and
    what a reader would open. Computing them here rather than writing them down
    is the entire reason this function exists.
    """
    out: list[str] = []
    facts: list[Fact] = []
    at = 0
    for match in _FACT.finditer(text):
        out.append(text[at : match.start()])
        start = sum(len(piece) for piece in out)
        body = match.group(2)
        out.append(body)
        facts.append(
            Fact(
                fact_id=match.group(1),
                text=body,
                span=Span(start, start + len(body)),
                document_id=document_id,
            )
        )
        at = match.end()
    out.append(text[at:])
    return "".join(out), tuple(facts)


def _rng(seed: int, genre: str) -> random.Random:
    """A generator seeded stably by the genre's name.

    ``hash()`` is salted per process, so a corpus built with it would differ
    between runs on the same seed -- which is the one thing a seed exists to
    prevent.
    """
    digest = hashlib.sha256(genre.encode("utf-8")).digest()[:8]
    # S311: this shuffles a fixture corpus. Reproducibility is the whole
    # requirement and unpredictability is the opposite of it -- a
    # cryptographic generator here would be a defect, not a hardening.
    return random.Random(seed ^ int.from_bytes(digest, "big"))  # noqa: S311


def _paragraph_items(
    spec: GenreSpec,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, Fact]]:
    """The package's items and omissions, and every fact by id.

    A paragraph that carries a fact becomes an item; one that does not becomes
    an omission. That is not decoration: a plant's ``source`` has to fall inside
    an item or the case loader refuses it, and the omissions give the report a
    withheld count to carry (ADR-0012).
    """
    items: list[dict[str, object]] = []
    omissions: list[dict[str, object]] = []
    facts: dict[str, Fact] = {}

    for document in spec.documents:
        raw = "\n\n".join(document.paragraphs)
        text, found = strip_facts(raw, document.document_id)
        for fact in found:
            facts[fact.fact_id] = fact

        at = 0
        for paragraph in text.split("\n\n"):
            span = Span(at, at + len(paragraph))
            at = span.end + 2
            carries = [fact for fact in found if span.contains(fact.span)]
            if carries:
                items.append(
                    {
                        "item_id": f"itm_{len(items) + 1:02d}",
                        "kind": "document_span",
                        "text": paragraph,
                        "anchor": {
                            "document_id": document.document_id,
                            "source_path": document.source_path,
                            "section": document.section,
                            "start": span.start,
                            "end": span.end,
                            "text_hash": _sha(paragraph),
                            "document_hash": _sha(text),
                        },
                        "provenance": {"layer": "fact", "producer": "akashi.cases/1"},
                        "selection": {"rank": len(items) + 1, "score": 0.9},
                        "cost": len(paragraph) // 2,
                    }
                )
            else:
                omissions.append(
                    {
                        "anchor": {
                            "document_id": document.document_id,
                            "source_path": document.source_path,
                            "start": span.start,
                            "end": span.end,
                        },
                        "rule": "below_threshold",
                        "reason": "carries no fact the question asked about",
                        "score": 0.11,
                    }
                )
    return items, omissions, facts


def _sha(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _package(spec: GenreSpec, case_id: str) -> dict[str, object]:
    items, omissions, _ = _paragraph_items(spec)
    protection = (
        {"by": "mamori@0.17.0", "scope": f"sess_{case_id}", "reversible": True}
        if spec.protected
        else None
    )
    return {
        "contract": "tsumugi.context-package/1",
        "package_id": _sha(case_id + spec.question),
        "query": spec.question,
        "items": items,
        "omissions": omissions,
        "budget": {
            "unit": "tokens",
            "limit": 2000,
            "estimate": sum(int(item["cost"]) for item in items),  # type: ignore[call-overload]
            "estimator": "heuristic/cjk-aware@1",
            "measured_error": {
                "p50": 0.03,
                "p95": 0.11,
                "against": "cl100k_base",
                "dataset": "ja-mixed-500",
            },
        },
        "provenance": {
            "tsumugi_version": "0.2.0",
            "providers": ["filesystem"],
            "protection": protection,
        },
    }


def _assemble(sentences: Sequence[SentenceSpec], language: str) -> tuple[str, list[Span]]:
    """The response, and where each sentence landed in it.

    Joined the way a model writes: paragraphs of three, sentences run together
    in scripts that do not space them. A response of one sentence per line would
    exercise the line fallback on every case and the terminator rules on none.
    """
    joiner = " " if language == "en" else ""
    pieces: list[str] = []
    spans: list[Span] = []
    at = 0
    for index, sentence in enumerate(sentences):
        if index and index % 3 == 0:
            pieces.append("\n\n")
            at += 2
        elif index:
            pieces.append(joiner)
            at += len(joiner)
        pieces.append(sentence.text)
        spans.append(Span(at, at + len(sentence.text)))
        at += len(sentence.text)
    return "".join(pieces) + "\n", spans


def _plant(
    sentence: SentenceSpec, span: Span, response: str, facts: dict[str, Fact]
) -> dict[str, object]:
    detected, hallucination, declared, verdict = _LABELS[sentence.kind]
    if sentence.target:
        offset = sentence.text.index(sentence.target)
        if sentence.text.count(sentence.target) != 1:
            raise ValueError(
                f"{sentence.target!r} occurs {sentence.text.count(sentence.target)} times in "
                f"{sentence.text!r}; a plant needs one place to point at"
            )
        where = Span(span.start + offset, span.start + offset + len(sentence.target))
    else:
        where = span

    body: dict[str, object] = {
        "kind": sentence.kind.value,
        "span": [where.start, where.end],
        "text": where.slice(response),
        "expect_detected": detected,
        "is_hallucination": hallucination,
        "declared_miss": declared,
        "expect_verdict": sentence.expect_verdict or verdict,
    }
    if sentence.fact:
        fact = facts[sentence.fact]
        body["was"] = fact.text
        body["source"] = {
            "document_id": fact.document_id,
            "span": [fact.span.start, fact.span.end],
        }
    return body


def build_case(
    spec: GenreSpec, seed: int, index: int, total: int
) -> tuple[str, dict[str, object], str, dict[str, object]]:
    """One case: its id, its package, its response, and its manifest.

    Returns the pieces rather than writing them, so that ``--check-only`` can
    re-derive a case and compare without touching the disk.
    """
    shuffled = list(spec.sentences)
    _rng(seed, spec.genre).shuffle(shuffled)
    # Every sentence is used exactly once across a genre's cases. Coverage is a
    # property of the data rather than of the draw, so a corpus cannot lose a
    # plant kind to an unlucky seed.
    chosen = [sentence for position, sentence in enumerate(shuffled) if position % total == index]
    if not chosen:
        raise ValueError(f"{spec.genre} case {index} drew no sentences from {len(shuffled)}")

    case_id = f"{spec.language}-{spec.genre}-{index + 1:02d}"
    response, spans = _assemble(chosen, spec.language)
    _, _, facts = _paragraph_items(spec)

    manifest: dict[str, object] = {
        "format": CASE_FORMAT,
        "case_id": case_id,
        "language": spec.language,
        "genre": spec.genre,
        "split": "held_out" if index == total - 1 else "train",
        "generator": GENERATOR,
        "seed": seed,
        "tier": list(spec.tier),
        "expect_refusal": spec.protected,
        "plants": [
            _plant(sentence, span, response, facts)
            for sentence, span in zip(chosen, spans, strict=True)
        ],
    }
    return case_id, _package(spec, case_id), response, manifest


def _dump(body: object) -> str:
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_case(root: Path, case_id: str, package: object, response: str, manifest: object) -> Path:
    folder = root / case_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "package.json").write_text(_dump(package), encoding="utf-8", newline="\n")
    (folder / "response.txt").write_text(response, encoding="utf-8", newline="\n")
    (folder / "case.json").write_text(_dump(manifest), encoding="utf-8", newline="\n")
    return folder


def rendered(spec: GenreSpec, seed: int, index: int, total: int) -> dict[str, str]:
    """A case as three strings, for comparing against what is on disk."""
    case_id, package, response, manifest = build_case(spec, seed, index, total)
    return {
        f"{case_id}/package.json": _dump(package),
        f"{case_id}/response.txt": response,
        f"{case_id}/case.json": _dump(manifest),
    }
