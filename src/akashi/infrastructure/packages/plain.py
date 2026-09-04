"""A package from the shape everybody else already has.

akashi reads `tsumugi.context-package/1`, and almost nobody has one. What people
have is a question, an answer, and a list of strings that were retrieved -- the
shape every RAG evaluation library takes, under three different sets of names:

| | question | answer | context |
| --- | --- | --- | --- |
| RAGAS | ``user_input`` | ``response`` | ``retrieved_contexts`` |
| DeepEval | ``input`` | ``actual_output`` | ``retrieval_context`` |
| plain | ``question`` | ``answer`` | ``contexts`` |

All three are read here. A person with a dataset should be able to point akashi
at it, not port it.

**No provenance is invented.** A ContextPackage carries a document id, a source
path and an offset into a file, and a list of strings has none of those. So the
anchors here point into **the strings the caller passed**, the source path is
empty, and the report says so in `limits` -- because a reader who sees
``notes/gear.md[1209:1214]`` on a report will go and open that file, and a
reader who sees ``context 2[41:46]`` will not.

That distinction is the whole reason this is a separate module and not a
convenience keyword on the reader: reading somebody's package and being handed
somebody's strings are different amounts of knowledge, and the report has to
keep them apart.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from akashi.domain.evidence import Evidence, item
from akashi.domain.package import PLAIN_CONTRACT, ContextPackage
from akashi.errors import ContractError

__all__ = ["CONTRACT", "package_from_contexts", "read_sample"]

#: What a package built from plain strings says it is.
#:
#: Not `tsumugi.context-package/1`: that contract promises a document id, a
#: source path and an offset into a file that exists, and nothing here can
#: promise any of it. A consumer that recognises the tsumugi contract would be
#: entitled to open the paths, and there are none.
#:
#: Defined in the domain, because the audit changes on it -- `limits` gains a
#: line -- and re-exported here where it is used.
CONTRACT = PLAIN_CONTRACT

#: The field names three ecosystems use for the same three things. Order is
#: precedence: the first name found wins, so a mapping carrying both `answer`
#: and `response` is not ambiguous.
FIELDS: dict[str, tuple[str, ...]] = {
    "answer": ("answer", "response", "actual_output", "output"),
    "contexts": ("contexts", "retrieved_contexts", "retrieval_context", "context"),
    "question": ("question", "user_input", "input", "query"),
}


def package_from_contexts(
    contexts: Sequence[str], question: str = "", *, protected_by: str = ""
) -> ContextPackage:
    """A ContextPackage over plain strings, with honest anchors.

    ``protected_by`` is for a caller whose strings came back from a redactor;
    without it the package declares no protection, which is what a package built
    from strings somebody handed over honestly says (ADR-0008 refuses on an
    undeclared one rather than assuming).
    """
    if isinstance(contexts, str):
        raise ContractError(
            "contexts is a list of strings and one string was given. A single string "
            "would be read as a list of its characters, which is a package of one "
            "letter per item and an audit that means nothing."
        )
    kept = [text for text in contexts if text and text.strip()]
    if not kept:
        raise ContractError(
            "no context was given, so every particular in the answer would float "
            "correctly and uselessly. akashi audits an answer against text; with no "
            "text there is nothing to audit it against."
        )

    return ContextPackage(
        contract=CONTRACT,
        query=question,
        evidence=Evidence.of(
            [
                # `document_id` names the position in the list the caller passed,
                # and `source_path` stays empty. An invented filename here is a
                # reader opening a file that does not exist.
                item(
                    f"itm_{index:02d}",
                    text,
                    document_id=f"context {index}",
                    producer="caller",
                )
                for index, text in enumerate(kept, start=1)
            ]
        ),
        declares_protection=not protected_by,
        protection=None,
    )


def read_sample(sample: Mapping[str, Any]) -> tuple[str, ContextPackage]:
    """``(answer, package)`` from a RAGAS, DeepEval or plain sample.

    The names are read in the order given by `FIELDS`, and a mapping that
    carries none of them is refused with all of them listed -- a caller whose
    field is spelled differently needs to see the ones that would have worked,
    not that theirs did not.
    """
    answer = _one(sample, "answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ContractError(
            f"the sample has no answer to audit. akashi reads any of: "
            f"{', '.join(FIELDS['answer'])}."
        )

    contexts = _one(sample, "contexts")
    if contexts is None:
        raise ContractError(
            f"the sample has no context. akashi reads any of: {', '.join(FIELDS['contexts'])}."
        )
    if isinstance(contexts, str):
        contexts = [contexts]
    if not isinstance(contexts, list) or not all(isinstance(one, str) for one in contexts):
        raise ContractError(f"the sample's context is not a list of strings: {contexts!r}")

    question = _one(sample, "question")
    return answer, package_from_contexts(contexts, str(question or ""))


def _one(sample: Mapping[str, Any], role: str) -> Any:
    for name in FIELDS[role]:
        if name in sample and sample[name] is not None:
            return sample[name]
    return None
