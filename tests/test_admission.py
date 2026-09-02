"""Refusing rather than reporting an honest answer as fabricated.

ADR-0008, and it is the most damaging misreport akashi could produce: an answer
that quoted its sources perfectly, marked floating in full, by the component
whose whole job is to be believed. The point of these tests is that the failure
is structurally unreachable rather than merely unlikely.
"""

from __future__ import annotations

import re

import pytest

from akashi.application import Admission, admit, audit
from akashi.domain.evidence import Evidence, item
from akashi.domain.package import ContextPackage, Protection
from akashi.domain.protection import find_placeholders
from akashi.errors import ProtectedResponseError
from akashi.infrastructure.languages import DEFAULT
from akashi.ports import Restorer

PLAIN = ContextPackage(
    contract="tsumugi.context-package/1",
    evidence=Evidence.of([item("itm_01", "The tent weighs 2.4kg.")]),
    declares_protection=True,
)

PSEUDONYMIZED = ContextPackage(
    contract="tsumugi.context-package/1",
    evidence=Evidence.of([item("itm_01", "Tanaka signed on 2026-08-30.")]),
    protection=Protection(by="mamori@0.17.0", scope="sess_2f11", reversible=True),
    declares_protection=True,
)

MASKED = ContextPackage(
    contract="tsumugi.context-package/1",
    evidence=Evidence.of([item("itm_01", "[redacted] signed on 2026-08-30.")]),
    protection=Protection(by="mamori@0.17.0", scope="sess_2f11", reversible=False),
    declares_protection=True,
)


class FakeRestorer:
    """A restorer, as anything with the right method is.

    Not a subclass of anything: the port is a ``Protocol``, so satisfying it
    costs a matching method and not a dependency. ``mamori``'s session already
    satisfies it without knowing akashi exists.
    """

    def __init__(self, **mapping: str) -> None:
        self.mapping = mapping

    def restore(self, text: str) -> str:
        for token, value in self.mapping.items():
            text = text.replace(f"<{token}>", value)
        return text


class NullRestorer:
    """A restorer for the wrong scope: it returns its input unchanged."""

    def restore(self, text: str) -> str:
        return text


# --- Recognising a placeholder ----------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Contact <EMAIL_001> by Friday.",
        "Contact [EMAIL_001] by Friday.",
        "Contact {EMAIL_001} by Friday.",
        "<PERSON_001> は担当者です。",
        "The amount was <AMOUNT_003>.",
    ],
)
def test_a_placeholder_is_recognised_in_every_bracket_style(text: str) -> None:
    """`mamori` emits angle brackets by default and the other two for payloads
    that would eat them. akashi is reading whatever came back, not choosing
    what went out."""
    assert len(find_placeholders(text)) == 1


@pytest.mark.parametrize(
    "text",
    [
        "The tent weighs 2.4kg.",
        "See <https://example.com/x>.",
        "Use the <div> element.",
        "A list [1] and [2].",
        "The value is {count}.",
        "SHOUTING is not a placeholder.",
        "<lowercase_001> is not one either.",
    ],
)
def test_ordinary_text_is_not_mistaken_for_a_placeholder(text: str) -> None:
    assert find_placeholders(text) == ()


def test_a_placeholder_appearing_three_times_is_three_pieces_of_evidence() -> None:
    """Collapsing them would understate how much of the answer is affected."""
    found = find_placeholders("<PERSON_001> met <PERSON_001> and <PERSON_002>.")
    assert [entry.token for entry in found] == [
        "<PERSON_001>",
        "<PERSON_001>",
        "<PERSON_002>",
    ]


def test_a_placeholder_carries_where_it_is() -> None:
    found = find_placeholders("Contact <EMAIL_001> by Friday.")[0]
    assert found.entity_type == "EMAIL"
    assert found.span.slice("Contact <EMAIL_001> by Friday.") == "<EMAIL_001>"
    assert found.describe() == "<EMAIL_001> at [8:19]"


# --- The three outcomes ------------------------------------------------------


def test_an_ordinary_answer_is_admitted_unchanged() -> None:
    admission = admit("The tent weighs 2.4kg.", PLAIN)
    assert admission.answer == "The tent weighs 2.4kg."
    assert not admission.was_restored
    assert not admission.is_partly_unverifiable


def test_a_pseudonymized_answer_with_no_restorer_is_refused() -> None:
    with pytest.raises(ProtectedResponseError, match="no restorer was given"):
        admit("<PERSON_001> signed on 2026-08-30.", PSEUDONYMIZED)


def test_the_refusal_names_the_scope_a_restorer_would_need() -> None:
    """A caller can act on this rather than only knowing something is wrong."""
    with pytest.raises(ProtectedResponseError, match="sess_2f11"):
        admit("<PERSON_001> signed.", PSEUDONYMIZED)


def test_a_pseudonymized_answer_is_restored_before_it_is_audited() -> None:
    admission = admit(
        "<PERSON_001> signed on 2026-08-30.",
        PSEUDONYMIZED,
        FakeRestorer(PERSON_001="Tanaka"),
    )
    assert admission.answer == "Tanaka signed on 2026-08-30."
    assert admission.restored_by == "mamori@0.17.0"
    assert not admission.is_partly_unverifiable


def test_an_irreversibly_protected_answer_is_audited_and_marked() -> None:
    """Masked or blocked rather than pseudonymized. No restorer can help, so
    akashi audits what it can and says what it cannot -- ``unverifiable``,
    never ``floating``."""
    admission = admit("<PERSON_001> signed on 2026-08-30.", MASKED)
    assert admission.answer == "<PERSON_001> signed on 2026-08-30."
    assert admission.is_partly_unverifiable
    assert not admission.was_restored


def test_a_protected_package_with_a_plain_answer_is_still_refused() -> None:
    """An answer with no placeholders in it is not evidence of restoration.
    ``mamori`` can substitute surrogates -- plausible fake values -- so restored
    text and unrestored text look identical, and the inference akashi would have
    to make is false in the dangerous direction (ADR-0013)."""
    with pytest.raises(ProtectedResponseError, match="not evidence of restoration"):
        admit("Tanaka signed on 2026-08-30.", PSEUDONYMIZED)


# --- The caller's assertion (ADR-0013) ---------------------------------------


def test_a_caller_may_assert_that_they_restored_it() -> None:
    """The ordinary pipeline: it already holds the session and restored the
    answer before handing it over. There is nothing to restore twice."""
    admission = admit("Tanaka signed on 2026-08-30.", PSEUDONYMIZED, restored_by="mamori@0.17.0")
    assert admission.answer == "Tanaka signed on 2026-08-30."
    assert admission.was_restored
    assert admission.asserted


def test_an_asserted_restoration_reads_as_a_claim_and_not_as_a_fact() -> None:
    """The artefact carries the sentence that is true. An audit trail that
    recorded a claim as a fact would be worse than one that refused."""
    asserted = admit("Tanaka signed.", PSEUDONYMIZED, restored_by="mamori@0.17.0")
    assert asserted.describe_restoration() == (
        "asserted restored by mamori@0.17.0; akashi did not verify it"
    )

    watched = admit("<PERSON_001> signed.", PSEUDONYMIZED, FakeRestorer(PERSON_001="Tanaka"))
    assert watched.describe_restoration() == "restored by mamori@0.17.0"
    assert not watched.asserted


def test_an_answer_that_was_not_restored_says_so() -> None:
    assert admit("The tent weighs 2.4kg.", PLAIN).describe_restoration() == "not restored"


def test_an_assertion_and_a_restorer_together_are_refused() -> None:
    """Two answers to "who restored this" is one too many, and picking either
    would put a name on the report that nobody chose."""
    with pytest.raises(ValueError, match="both a restorer and a restored_by"):
        admit("<PERSON_001> signed.", PSEUDONYMIZED, NullRestorer(), restored_by="somebody")


def test_an_assertion_does_not_hide_placeholder_residue() -> None:
    """It changes what akashi is willing to look at, not what it concludes."""
    admission = admit("<PERSON_001> signed.", PSEUDONYMIZED, restored_by="mamori@0.17.0")
    assert admission.is_partly_unverifiable
    assert [entry.token for entry in admission.residue] == ["<PERSON_001>"]


# --- The case the contract field exists to prevent ---------------------------


def test_placeholders_with_no_declared_protection_are_refused() -> None:
    """Something in the pipeline protected the prompt without recording it.
    ``provenance.protection`` exists to make this unnecessary; the refusal is
    for the pipelines that do not set it."""
    silent = ContextPackage(contract="tsumugi.context-package/1", evidence=PLAIN.evidence)
    with pytest.raises(ProtectedResponseError, match="declares no protection at all"):
        admit("<PERSON_001> signed.", silent)


def test_a_package_that_declared_no_protection_is_still_refused_but_worded_for_it() -> None:
    with pytest.raises(ProtectedResponseError) as raised:
        admit("<PERSON_001> signed.", PLAIN)
    assert "declares no protection." in str(raised.value)
    assert "at all" not in str(raised.value)


def test_the_refusal_counts_what_it_found() -> None:
    with pytest.raises(ProtectedResponseError, match="carries 2 placeholder-shaped tokens"):
        admit("<PERSON_001> and <PERSON_002>.", PLAIN)

    with pytest.raises(ProtectedResponseError, match="carries 1 placeholder-shaped token "):
        admit("<PERSON_001> signed.", PLAIN)


def test_the_refusal_shows_a_few_examples_and_not_the_whole_answer() -> None:
    answer = " ".join(f"<PERSON_{n:03d}>" for n in range(1, 11))
    with pytest.raises(ProtectedResponseError) as raised:
        admit(answer, PLAIN)
    message = str(raised.value)
    assert "<PERSON_001>, <PERSON_002>, <PERSON_003>, ..." in message
    assert "<PERSON_010>" not in message


# --- A restorer that did nothing ---------------------------------------------


def test_a_restorer_that_put_nothing_back_is_caught() -> None:
    """A restorer for the wrong scope returns its input unchanged, and text
    that looks restored and is not is the one outcome worse than refusing."""
    with pytest.raises(ProtectedResponseError, match="put nothing back"):
        admit("<PERSON_001> signed.", PSEUDONYMIZED, NullRestorer())


def test_a_restorer_that_put_some_back_is_accepted_with_the_rest_marked() -> None:
    """A placeholder the restorer does not know about is left as it is, not
    removed. akashi checks again afterwards, so the remainder is visible."""
    admission = admit(
        "<PERSON_001> met <PERSON_002>.",
        PSEUDONYMIZED,
        FakeRestorer(PERSON_001="Tanaka"),
    )
    assert admission.answer == "Tanaka met <PERSON_002>."
    assert admission.was_restored
    assert [entry.token for entry in admission.residue] == ["<PERSON_002>"]


def test_a_restorer_is_recognised_by_its_method_and_not_its_ancestry() -> None:
    assert isinstance(FakeRestorer(), Restorer)
    assert isinstance(NullRestorer(), Restorer)
    assert not isinstance("not a restorer", Restorer)


# --- What admission is, as a value -------------------------------------------


def test_an_admission_says_what_had_to_happen_to_clear_the_answer() -> None:
    admission = Admission(answer="Tanaka signed.", restored_by="mamori@0.17.0")
    assert admission.was_restored
    assert not admission.is_partly_unverifiable


def test_admitting_twice_gives_the_same_admission() -> None:
    """ADR-0003. A stage that ran differently on the same inputs would move
    every number downstream of it."""
    restorer = FakeRestorer(PERSON_001="Tanaka")
    answer = "<PERSON_001> signed on 2026-08-30."
    assert admit(answer, PSEUDONYMIZED, restorer) == admit(answer, PSEUDONYMIZED, restorer)


def test_the_refusal_never_quotes_the_restored_values() -> None:
    """A refusal is often logged. It names the placeholders, which are exactly
    the tokens that carry no sensitive value, and never the text around them."""
    answer = "<PERSON_001> lives at 4-2-1 Roppongi and earns 8,000,000 yen."
    with pytest.raises(ProtectedResponseError) as raised:
        admit(answer, PLAIN)
    message = str(raised.value)
    assert "Roppongi" not in message
    assert "8,000,000" not in message
    assert not re.search(r"\d-\d-\d", message)


# --- An assertion on a package that declares no protection -------------------


def test_a_restoration_claim_is_recorded_even_when_the_package_says_nothing() -> None:
    """Found by somebody acting on a recommendation to use the flag.

    `--restored-by` produced a report **byte-identical** to one made without
    it, because `admit` returned early on the unprotected path and dropped the
    claim. The docstring called that harmless and pointless, and it was
    neither: the caller believes they recorded something, and the report says
    nothing.

    It is not pointless because **the package does not always know.** A
    redactor that ran after the package was built cannot appear in
    `provenance.protection`, so this branch is exactly where a real restoration
    claim arrives — the pipeline that prompted this has `mamori` restoring
    downstream of `tsumugi` packaging.
    """
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "金額は 45,000 円。")]),
    )
    admission = admit("金額は 45,000 円でした。", package, None, restored_by="mamori")
    assert admission.restored_by == "mamori"
    assert admission.asserted


def test_the_claim_reaches_the_report_and_says_akashi_did_not_check_it() -> None:
    """ADR-0013. akashi cannot verify a restoration it did not watch — a
    surrogate is designed to be indistinguishable from a real value — so the
    claim is attributed rather than absorbed."""
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "金額は 45,000 円。")]),
    )
    report = audit("金額は 45,000 円でした。", package, DEFAULT, restored_by="mamori")
    assert report.provenance.restored_by == "mamori"
    assert report.provenance.restoration_asserted
    assert "did not verify" in report.provenance.describe_restoration()


def test_without_the_claim_the_report_says_nothing_about_restoration() -> None:
    """The other direction. Recording the claim must not invent one."""
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "金額は 45,000 円。")]),
    )
    admission = admit("金額は 45,000 円でした。", package, None)
    assert admission.restored_by == ""
    assert not admission.asserted


def test_the_refusal_says_what_akashi_cannot_decide_rather_than_only_no() -> None:
    """#52. `<PERSON_001>` is a string a person can type, and akashi cannot tell
    a token a redactor minted from one an author quoted.

    Both ways of being wrong are silent -- an honest quotation reported as
    unrestored residue, a real placeholder audited against as ordinary text --
    so the refusal names the limit and the way out instead of leaving a caller
    to guess which of the two akashi thinks it is looking at.

    #52 asks for "can say which of the two it found, **or says it cannot**".
    This is the second, and it is the honest one: the enumeration that would
    settle it is in the redactor's own record, and the document akashi reads has
    no field that can carry it (pinned in `test_vendored_contracts.py`).
    """
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "the form's name box")]),
    )
    with pytest.raises(ProtectedResponseError) as refusal:
        admit("The form reads <PERSON_001> in the name box.", package)

    message = str(refusal.value)
    assert "cannot tell a token a redactor minted from one an author typed" in message
    assert "the package should say so and akashi will audit it" in message


def test_the_refusal_does_not_claim_the_answer_was_redacted() -> None:
    """The claim akashi is not entitled to. It found a shape; a shape is not a
    provenance, and a message that asserted one would be the fabrication this
    whole module exists to refuse -- committed by the auditor."""
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", "x")]),
    )
    with pytest.raises(ProtectedResponseError) as refusal:
        admit("<PERSON_001> signed it.", package)

    message = str(refusal.value)
    assert "placeholder-shaped" in message
    assert "was redacted" not in message
    assert "is a placeholder" not in message
