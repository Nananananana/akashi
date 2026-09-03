"""Which strings count as the same string is a choice, and it has a name.

The two problems `domain/matching.py` solves -- a number inside a longer number,
and a quantity written with and without its space -- are solved one way, and it
is a *decision*. A component that answers the question the whole audit turns on
without saying which answer it gave is a component nobody can disagree with.

So the answer has a name, the name is on the report, and the name is in
`report_id`. Two runs that answered it differently must not be able to claim one
id, which is the thing `recheck` exists to make impossible.
"""

from __future__ import annotations

import pathlib

import pytest

from akashi.application import audit
from akashi.domain.matching import DEFAULT_MATCHER, MATCHERS, Matcher, exact, matcher_named
from akashi.domain.package import ContextPackage
from akashi.domain.text import search_form
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package

PACKAGES = pathlib.Path(__file__).parent / "packages"


def package() -> ContextPackage:
    return load_package(PACKAGES / "gear-ja.json")


# --- the port has more than one implementation -------------------------------


def test_every_shipped_matcher_satisfies_the_port() -> None:
    """A port with one implementation is a port nobody has tried to satisfy.
    akashi learned that from `Restorer`, whose docstring described a shape the
    real library did not have (#76)."""
    assert len(MATCHERS) >= 2
    for name, one in MATCHERS.items():
        assert isinstance(one, Matcher)
        assert one.name == name, "the registry key is the name that reaches the report"


def test_the_two_matchers_disagree_about_something() -> None:
    """The second implementation is not decoration. `2.4kg` and `2.4 kg` are the
    same quantity and two different strings, and this is where akashi says which
    of those two facts it is using."""
    haystack = search_form("テントは 2.4 kg です。")
    assert MATCHERS["normalized"].find("2.4kg", haystack)
    assert not MATCHERS["exact"].find("2.4kg", haystack)


def test_exact_still_folds_the_text() -> None:
    """Turning folding off as well would compare a full-width `２.４kg` against a
    half-width one and report an honest citation as fabricated. That is not a
    stricter audit; it is a broken one, and half of what akashi reads is CJK."""
    assert exact.find("2.4kg", search_form("重さは ２.４kg です。"))


def test_an_unknown_matcher_is_refused_and_the_message_lists_the_real_ones() -> None:
    """Refused rather than fallen back to the default: a caller who asked for
    `strict` and silently got `normalized` would hold a report that says
    `normalized` and a belief that says otherwise."""
    with pytest.raises(ValueError, match="no matcher named"):
        matcher_named("strict")
    assert "normalized" in _message()


def _message() -> str:
    try:
        matcher_named("strict")
    except ValueError as error:
        return str(error)
    raise AssertionError("it did not refuse")


# --- the choice is on the report, and in its id ------------------------------


def test_the_report_names_the_matcher_that_produced_it() -> None:
    body = audit("テントは 2.4kg。", package(), DEFAULT).to_dict()
    assert body["audited"]["matcher"] == DEFAULT_MATCHER.name


def test_two_matchers_give_two_ids() -> None:
    """The whole reason the name is in the hash. Without it, two audits that
    answered different questions would carry one id, and `recheck` would report
    a match between reports that do not match."""
    answer = "テントは 2.4 kg。"
    one = audit(answer, package(), DEFAULT, matcher=MATCHERS["normalized"]).to_dict()
    two = audit(answer, package(), DEFAULT, matcher=MATCHERS["exact"]).to_dict()
    assert one["report_id"] != two["report_id"]
    assert one["counts"]["particulars"] != two["counts"]["particulars"]


def test_recheck_re_derives_with_the_matcher_the_report_names() -> None:
    """Not with whatever this process defaults to. Re-deriving an `exact` report
    under `normalized` would report a difference that is about this run rather
    than about that report."""
    from akashi.application.recheck import recheck

    answer = "テントは 2.4 kg。"
    archived = audit(answer, package(), DEFAULT, matcher=MATCHERS["exact"]).to_dict()
    result = recheck(archived, answer, package(), DEFAULT)
    assert result.matches, result.differences


def test_a_report_naming_a_matcher_this_akashi_does_not_have_is_refused() -> None:
    """Two answers to two different questions cannot be compared, and saying so
    is more useful than a difference nobody can act on."""
    from akashi.application.recheck import recheck
    from akashi.errors import ContractError

    answer = "テントは 2.4kg。"
    archived = audit(answer, package(), DEFAULT).to_dict()
    archived["audited"]["matcher"] = "from-a-later-akashi"
    with pytest.raises(ContractError, match="does not have"):
        recheck(archived, answer, package(), DEFAULT)


# --- what the corpus can and cannot tell apart -------------------------------


def test_the_corpus_cannot_tell_the_two_matchers_apart() -> None:
    """Measured, and it is a statement about the corpus rather than about the
    matchers.

    `domain/matching.py` justifies the spacing tolerance at length -- `2.4kg`
    finds `2.4 kg`, `第30条` finds `第 30 条` -- and unit tests cover it. Over the
    whole labelled corpus the two matchers ground **exactly the same
    particulars**: 45 evidence items contain a spaced quantity and no answer
    ever re-spaces one, because the generator writes answers that quote the
    evidence verbatim.

    So the tolerance is worth nothing that any published number measures. That
    is a gap in the corpus, not a reason to remove the tolerance -- a model
    re-spaces a quantity constantly -- and this test is here so it stops being
    invisible. **When the corpus grows a case that re-spaces a quantity, this
    test fails and should be deleted.**
    """
    from akashi.domain.extraction import extract_from_answer
    from akashi.domain.segment import segment_answer
    from akashi.evaluation import load_cases

    cases = load_cases(pathlib.Path(__file__).parent / "cases")
    assert cases

    def grounded(one: Matcher) -> int:
        return sum(
            1
            for case in cases
            for particular in extract_from_answer(segment_answer(case.response, DEFAULT), DEFAULT)
            if case.package.evidence.locate(particular, one)
        )

    assert grounded(MATCHERS["normalized"]) == grounded(MATCHERS["exact"])
