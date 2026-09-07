"""Every way akashi refuses, and the catalogue that names them.

This module imports nothing -- not even from the rest of akashi. An error type
that depends on a layer cannot be raised from below it, and refusing is the one
thing every layer has to be able to do.

akashi fails closed. Where the alternative to raising is to produce a report
that is confidently wrong, it raises: a report is meant to be believed, and an
auditor that guesses teaches its user to ignore it.

## Kinds, and why they are a closed set

An orchestrator that talks to seven libraries is the only place that can answer
*"is something broken, or did I do this?"* -- and it can only answer it by
folding failures together, which needs a **stable name** rather than a sentence
(Sora R-E1). A sentence may quote what it was given; a name cannot, which is
what lets a record of failures say it holds no values.

So every refusal carries a ``kind``, and **the default is the class name**. That
is what makes the set closed by construction rather than by anybody remembering:
a new raise site with no ``kind`` is still catalogued, under a name that is
already stable. `CATALOGUE` lists every one, and a test walks the source to
check that the two agree in both directions.

**Granularity is what a caller can do differently**, not one name per raise
site. There are a hundred-odd raise sites and six kinds worth telling apart,
because there are six different things to do about them.

## What the catalogue deliberately does not carry

No paths, no message templates with holes in them, no examples that look like
real values. A reader who finds `{}` in a catalogue fills it from a log, and
then the catalogue has taught somebody to write down the thing it exists to keep
out. `detail` is one whole sentence about the kind and never about an instance.
"""

from __future__ import annotations

from typing import Any, Final, Literal

__all__ = [
    "CATALOGUE",
    "CONTRACT",
    "OPEN_NAMESPACES",
    "AkashiError",
    "ContractError",
    "ErrorKind",
    "ProtectedResponseError",
    "SegmentationError",
    "catalogue",
]

#: What `akashi errors --json` declares itself to be. `-draft` while the field
#: set can still move; a consumer that pins the frozen name will be refused by
#: the check it already has rather than read a document of a shape it does not
#: know.
CONTRACT: Final = "akashi.errors/1-draft"

#: Prefixes under which akashi prints a name it did not choose.
#:
#: Empty, and that is a fact rather than an omission: akashi builds no kind out
#: of another project's vocabulary. It reads `mamori.protection-scope/1` and
#: `tsumugi.context-package/1`, and a document of either shape that it refuses
#: is refused under **akashi's** name for the refusal, because what failed is
#: akashi's reading and not their writing.
OPEN_NAMESPACES: Final[tuple[str, ...]] = ()

Outcome = Literal["refused", "unavailable", "failed", "timed_out"]


class ErrorKind:
    """One named way to fail, and what a caller can do about it.

    ``retryable`` is the field only akashi can answer, and for almost all of
    these the answer is **no** -- not because retrying is expensive but because
    the same inputs give the same report, forever (ADR-0003). A refusal that
    would become an acceptance on a second identical call would mean the audit
    was not deterministic, which is the whole product. The exceptions are the
    two that reach a network, and they are marked.
    """

    __slots__ = ("detail", "detail_ja", "kind", "outcome", "retryable", "status")

    def __init__(
        self,
        kind: str,
        *,
        status: int | None,
        outcome: Outcome,
        retryable: bool,
        detail: str,
        detail_ja: str,
    ) -> None:
        self.kind = kind
        self.status = status
        self.outcome: Outcome = outcome
        self.retryable = retryable
        self.detail = detail
        self.detail_ja = detail_ja

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "outcome": self.outcome,
            "retryable": self.retryable,
            "detail": self.detail,
            "detail_ja": self.detail_ja,
        }


class AkashiError(Exception):
    """Base class for everything akashi raises deliberately.

    ``kind`` names the failure for anything folding failures together. It
    defaults to the class name, so a raise site that says nothing is still
    named, and the name it gets is one already in the catalogue.
    """

    #: Overridden where a subclass's own name is the right default.
    default_kind = "AkashiError"

    def __init__(self, *args: object, kind: str = "") -> None:
        super().__init__(*args)
        self.kind = kind or self.default_kind


class ContractError(AkashiError):
    """A document did not conform to a contract akashi recognises.

    Raised for an unknown ``contract`` value, a missing required field, or an
    audit report whose ``report_id`` does not re-derive. Guessing at an
    unrecognised version is how a consumer reads the wrong field and reports
    the wrong thing, so it is refused instead (ADR-0007).
    """

    default_kind = "ContractError"


class ProtectedResponseError(AkashiError):
    """The response still carries placeholders, and nothing can restore them.

    Auditing pseudonymized text marks every honest particular as floating --
    an answer that quoted its sources perfectly, reported as fabricated in
    full. Unknown and false are different, so this refuses rather than reports
    (ADR-0008).
    """

    default_kind = "ProtectedResponse"


class SegmentationError(AkashiError, ValueError):
    """The answer could not be cut into segments that tile it exactly.

    **Also a `ValueError`**, because the invariant it guards lives in a
    dataclass `__post_init__` and raised a plain one for a long time. Anything
    written against that keeps working; what changes is that the command line
    now prints a refusal instead of letting a traceback out, which is what
    ADR-0009 and this docstring said all along.

    Found by the catalogue guard (Sora R-E1): this class was exported, was
    documented, and was raised by nothing.

    Every count in a report has the segmenter in its denominator, and an
    offset that has drifted points a reader at the wrong sentence. A tiling
    that does not hold is a bug, and it stops the audit (ADR-0009).
    """

    default_kind = "SegmentationError"


#: Exit code 1 on the command line: akashi read the input and would not audit
#: it. Every kind here shares it, which is why `status` alone cannot tell them
#: apart and `kind` exists.
_REFUSED: Final = 1


def _refusal(kind: str, detail: str, detail_ja: str, *, retryable: bool = False) -> ErrorKind:
    return ErrorKind(
        kind,
        status=_REFUSED,
        outcome="refused",
        retryable=retryable,
        detail=detail,
        detail_ja=detail_ja,
    )


#: Every kind akashi can print, in the order a reader meets them.
#:
#: Both sentences are written here, by one hand. A translation living in the
#: consumer would be a second author guessing at the first one's meaning, and
#: the two would drift in the direction nobody notices -- the one where the
#: translation is more confident than the original (Sora R-E1).
CATALOGUE: Final[tuple[ErrorKind, ...]] = (
    _refusal(
        "SurrogateRecord",
        "A protection record declaring surrogates cannot be audited. A surrogate is "
        "built to be indistinguishable from a real value, so auditing the text it "
        "protects would report invented names as grounded. Restore it first, or audit "
        "the text the redactor was given.",
        "surrogate を宣言した保護記録は監査できない。surrogate は本物の値と区別できないよう"
        "作られているので、その本文を監査すると捏造された名前が grounded と報告される。"
        "復元してから渡すか、redactor が受け取った側の本文を監査すること。",
    ),
    _refusal(
        "ProtectionMismatch",
        "The package and the protection record disagree about who protected this "
        "answer, in which scope, or whether it can be undone. Two answers is one too "
        "many, and choosing either would put a name on the report that the other "
        "source contradicts.",
        "package と保護記録が、誰がこの答えを保護したか・どの scope か・元に戻せるかで"
        "食い違っている。答えが 2 つあるのは 1 つ多い。どちらかを選べば、もう一方が"
        "否定する名前をレポートに載せることになる。",
    ),
    _refusal(
        "ProtectedResponse",
        "The answer still carries placeholder-shaped tokens and nothing can put the "
        "values back. Auditing it would report every honest quotation as fabricated. "
        "Pass a restorer, or assert who restored it.",
        "答えに placeholder の形をしたトークンが残っていて、値を戻せるものが無い。"
        "そのまま監査すると、正直な引用がすべて捏造として報告される。restorer を渡すか、"
        "誰が復元したかを申告すること。",
    ),
    _refusal(
        "ContractError",
        "A document did not conform to the contract it declares, or declares one "
        "akashi does not read. akashi refuses rather than reading the fields it "
        "happens to recognise, because guessing at an unrecognised version is how a "
        "consumer reports the wrong thing confidently.",
        "文書が、自分で宣言した契約に適合していないか、akashi が読まない契約を宣言している。"
        "akashi は、たまたま知っているフィールドだけを読むのではなく拒否する。未知の版を"
        "推測して読むことが、消費者が自信を持って誤りを報告する経路だから。",
    ),
    _refusal(
        "SegmentationError",
        "The answer could not be cut into segments that tile it exactly. Every count "
        "on a report has the segmenter in its denominator, so a tiling that does not "
        "hold stops the audit rather than producing counts nobody can trust.",
        "答えを、過不足なく敷き詰める segment に切れなかった。レポートのすべての計数は"
        "分母に segmenter を持つので、敷き詰めが成り立たないときは、誰も信用できない"
        "計数を出すのではなく監査を止める。",
    ),
    ErrorKind(
        "JudgeUnavailable",
        status=_REFUSED,
        outcome="unavailable",
        retryable=False,
        detail="A judge was asked for and the extra that provides it is not installed. "
        "akashi itself has no dependencies; a judge is the one thing that changes "
        "that. Installing it is what fixes this, not asking again.",
        detail_ja="judge を要求されたが、それを提供する extra が入っていない。akashi 本体には"
        "依存が無く、judge だけがそれを変える。同じ要求を繰り返すのではなく、"
        "インストールすることで解決する。",
    ),
    ErrorKind(
        "JudgeRefused",
        status=_REFUSED,
        outcome="failed",
        retryable=True,
        detail="A judge declined to answer, or answered a different number of claims "
        "than it was asked about. akashi records what a judge said and never supplies "
        "an answer on its behalf, so the report carries no judgements rather than "
        "invented ones. A model may answer differently on a second attempt.",
        detail_ja="judge が回答を拒んだか、尋ねた数と違う数の claim に答えた。akashi は judge が"
        "言ったことを記録するだけで、代わりに答えを供給しない。だからレポートは、捏造された"
        "判断ではなく、判断を持たない状態になる。モデルは 2 回目に違う答えを返しうる。",
    ),
    ErrorKind(
        "AkashiError",
        status=_REFUSED,
        outcome="refused",
        retryable=False,
        detail="akashi refused for a reason it has not given its own name. The sentence "
        "on stderr says which; this kind exists so that a failure without a narrower "
        "name is still foldable rather than uncounted.",
        detail_ja="akashi が、独自の名前を与えていない理由で拒否した。どれかは stderr の文が"
        "言う。この kind は、より狭い名前を持たない失敗が、数えられないままにならず"
        "畳めるようにするためにある。",
    ),
)


def catalogue() -> dict[str, Any]:
    """The catalogue as plain data, for `akashi errors --json`.

    A document, like everything else akashi publishes: a consumer reads it,
    compares it with what they had, and notices the day it changes.
    """
    return {
        "contract": CONTRACT,
        "errors": [entry.to_dict() for entry in CATALOGUE],
        "open_namespaces": list(OPEN_NAMESPACES),
    }
