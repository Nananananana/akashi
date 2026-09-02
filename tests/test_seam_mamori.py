"""The restorer seam, against the library rather than against a shape.

`tests/test_mamori_adapter.py` checks the adapter against a stand-in that
presents the shape `mamori` presents. This file checks it against `mamori`, and
the difference is the whole of #59: a stand-in is written from a reading of the
sibling, so it agrees with the reading rather than with the sibling.

**Nothing here is skipped when `mamori` is absent.** The job that runs this
installs it deliberately, so absence means the install step lied, and a suite
that reports success for having checked nothing is the failure this repository
is about. Verified in a sibling: `pytest tests/` against a venv without the
library exits 0, green, with zero seam tests run.

The marker keeps it out of the ordinary suite, where the library genuinely is
not expected. `pytest -m siblings` selects it; collecting nothing exits 5, so a
job that runs it cannot pass by selecting an empty set either.
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
import os

import pytest

from akashi.application import audit
from akashi.domain.evidence import Evidence, item
from akashi.domain.package import ContextPackage, Protection
from akashi.domain.protection import find_placeholders
from akashi.infrastructure.adapters import MamoriRestorer
from akashi.infrastructure.languages import DEFAULT
from akashi.ports import Restorer

pytestmark = pytest.mark.siblings

#: Deliberately a plain import. `pytest.importorskip` here would turn a broken
#: install into a green run (#59).
import mamori  # noqa: E402
from mamori import PrivacySession  # noqa: E402

#: Read at import time. `conftest.py` strips every ``AKASHI_*`` variable for the
#: duration of each test, so a body reading this would find it gone and skip the
#: pin check in the one place the pin exists.
PINNED = os.environ.get("AKASHI_SEAM_MAMORI_REF", "")

ORIGINAL = "担当は田中太郎、金額は 45,000 円です。"


@pytest.fixture
def session() -> PrivacySession:
    return PrivacySession()


# --- is this our mamori ------------------------------------------------------


def test_the_installed_mamori_is_the_one_this_repository_means() -> None:
    """`import mamori` proves a module of that name is installed. It does not
    prove it is ours, and for a name nobody has claimed on an index that is a
    question with an expiry date.

    PEP 610 answers it. A distribution installed from an index has **no**
    `direct_url.json`, so this fails rather than passing quietly.
    """
    raw = metadata.distribution("mamori").read_text("direct_url.json")
    assert raw, (
        "mamori has no direct_url.json, which means it came from an index. "
        "The name is unclaimed there; this is not necessarily the mamori this "
        "repository is a seam for. Install it by direct reference."
    )
    info = json.loads(raw)
    url = str(info.get("url", ""))

    if "vcs_info" in info:
        assert url.endswith("Nananananana/mamori.git"), (
            f"mamori was installed from {url}, which is not this family's repository"
        )
    else:
        # A developer's own checkout. Weaker, and it is the only shape that
        # exists off CI; the assertion above is the one that runs in the job.
        assert url.startswith("file:"), f"unrecognised direct reference: {url}"


def test_the_commit_is_the_one_the_job_pinned() -> None:
    """A seam result that cannot be tied to a revision is a seam result nobody
    can reproduce. The workflow exports the sha it installed; a structural test
    in `test_ci_configuration.py` asserts it still does, so this cannot go
    quiet by the variable disappearing.
    """
    if not PINNED:
        pytest.skip("no pin exported; this is a developer's own checkout, not the job")

    info = json.loads(metadata.distribution("mamori").read_text("direct_url.json") or "{}")
    installed = str(info.get("vcs_info", {}).get("commit_id", ""))
    assert installed == PINNED, (
        f"the job pinned {PINNED} and installed {installed or 'something with no commit'}"
    )


def test_it_reports_the_version_it_measured_against(record_property: object) -> None:
    """The seam is a measurement, and a measurement without its subject's
    version is an anecdote."""
    assert mamori.__version__
    if callable(record_property):
        record_property("mamori_version", mamori.__version__)


# --- the finding the adapter exists for, on the real class -------------------


def test_the_real_session_passes_the_runtime_check_and_returns_the_wrong_thing(
    session: PrivacySession,
) -> None:
    """`ports/restorer.py` used to say `PrivacySession` *"already satisfies it
    without knowing akashi exists"*. It does not, and `runtime_checkable` does
    not catch it: `isinstance` against a `Protocol` checks that the method is
    **present**, not what it returns.

    This is the claim #76 made from a stand-in. Here it is against the class.

    **And `mypy` catches what `isinstance` does not.** Running the real library
    through this file, it refuses the line below:

        Subclass of "PrivacySession" and "Restorer" cannot exist:
        would have incompatible method signatures  [unreachable]

    So the mismatch *is* statically visible -- a caller who type-checks their
    own code would have been told. It is only the runtime check that says yes,
    which makes `runtime_checkable` worse than no check here: it answers the
    question a reader asked with the answer to a narrower one.

    The widening to ``object`` below is what lets the runtime assertion run at
    all. Remove it and `mypy` refuses the file with the message above, which is
    the finding rather than an inconvenience.
    """
    checked: object = session
    assert isinstance(checked, Restorer)
    result: object = session.restore("x")
    assert not isinstance(result, str)
    assert hasattr(result, "text")


def test_without_the_adapter_the_failure_is_a_regex_error_far_from_the_seam(
    session: PrivacySession,
) -> None:
    """What a caller would have seen: a crash about a regular expression, three
    layers from the mistake, saying nothing about restorers or ADR-0008."""
    protected = session.protect(ORIGINAL).protected_text
    with pytest.raises(TypeError, match="expected string"):
        find_placeholders(session.restore(protected))  # type: ignore[arg-type]


# --- the round trip ADR-0008 describes ---------------------------------------


def test_a_real_protection_is_restored_and_then_audited(session: PrivacySession) -> None:
    """protect, audit the protected answer through the adapter, and the real
    value grounds in the document it came from.

    Without the restorer this answer audits as fabricated in full -- which is
    the outcome ADR-0008 exists to make unreachable.
    """
    protection = session.protect(ORIGINAL)
    assert protection.protected_text != ORIGINAL, "nothing was detected; the seam measures nothing"
    assert find_placeholders(protection.protected_text), "no placeholder to restore"

    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", ORIGINAL)]),
        protection=Protection(
            by=f"mamori@{mamori.__version__}",
            scope=protection.scope,
            reversible=protection.reversible,
        ),
        declares_protection=True,
    )
    report = audit(protection.protected_text, package, DEFAULT, restorer=MamoriRestorer(session))

    assert "田中太郎" in report.answer
    assert not find_placeholders(report.answer)
    grounded = [
        one.particular.text for segment in report.assessment.segments for one in segment.grounded
    ]
    assert "45,000 円" in grounded


def test_akashi_watched_this_one_so_it_is_not_an_assertion(session: PrivacySession) -> None:
    """ADR-0013. The seam's stage 2: `restored by`, not `asserted restored by`.

    Stage 1 hands akashi text somebody else restored, and akashi records a
    claim. Here akashi held the restorer, so the report says so -- and the
    difference between the two lines is the difference the seam exists to make.
    """
    protection = session.protect(ORIGINAL)
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", ORIGINAL)]),
        protection=Protection(
            by=f"mamori@{mamori.__version__}",
            scope=protection.scope,
            reversible=protection.reversible,
        ),
        declares_protection=True,
    )
    report = audit(protection.protected_text, package, DEFAULT, restorer=MamoriRestorer(session))
    assert not report.provenance.restoration_asserted
    assert report.provenance.describe_restoration().startswith("restored by")


def test_a_session_for_another_scope_puts_nothing_back_and_is_refused(
    session: PrivacySession,
) -> None:
    """The check above the adapter, against a real second session rather than a
    fake with an empty mapping. A restorer holding no mapping returns its input
    unchanged, and auditing that reports every honest particular as floating."""
    from akashi.application.admit import admit
    from akashi.errors import ProtectedResponseError

    protected = session.protect(ORIGINAL).protected_text
    stranger = PrivacySession()

    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", ORIGINAL)]),
        protection=Protection(by="mamori", scope="session-elsewhere", reversible=True),
        declares_protection=True,
    )
    with pytest.raises(ProtectedResponseError, match="put nothing back"):
        admit(protected, package, MamoriRestorer(stranger))


def test_a_raw_session_is_refused_at_the_seam_and_not_four_frames_in(
    session: PrivacySession,
) -> None:
    """The defect the seam repository found by running the real chain.

    `audit(..., restorer=session)` with the session unwrapped used to raise
    `TypeError: expected string or bytes-like object` from inside
    `domain/protection.py`, four frames from the mistake. The adapter carried a
    message about exactly that case and sat **behind** it: only a caller who had
    already wrapped their session could read it.

    The check is now in `admit`, in front of the thing it guards, and this is
    the case that would go quiet again if it moved back.
    """
    from akashi.errors import ProtectedResponseError

    protection = session.protect(ORIGINAL)
    package = ContextPackage(
        contract="tsumugi.context-package/1",
        evidence=Evidence.of([item("itm_01", ORIGINAL)]),
        protection=Protection(
            by=f"mamori@{mamori.__version__}",
            scope=protection.scope,
            reversible=protection.reversible,
        ),
        declares_protection=True,
    )
    with pytest.raises(ProtectedResponseError, match="returned RestorationResult"):
        audit(
            protection.protected_text,
            package,
            DEFAULT,
            restorer=session,  # type: ignore[arg-type]
        )
