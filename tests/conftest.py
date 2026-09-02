"""Isolation for every test, whether it remembers to ask for it or not.

Nothing reads ``AKASHI_*`` yet. The fixture exists anyway, because the rule it
enforces is one the sibling projects each learned by writing into a developer's
real data, and a convention added after the first configuration option is a
convention added after the first accident.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

#: The seam against the real `mamori` is not collected unless it is asked for.
#:
#: A marker is not enough. Markers deselect at *selection* time, and this file
#: imports the library at the top -- deliberately, so that its absence in the job
#: that installs it is an error rather than a skip (#59). Collection happens
#: first, so without this the whole suite fails on every machine that does not
#: have the sibling, which is every machine except one CI job.
#:
#: Ignoring it here cannot make that job pass quietly: the job selects
#: `-m siblings`, and pytest exits 5 when it collects nothing. A forgotten
#: variable is red, not green.
collect_ignore = [] if os.environ.get("AKASHI_SEAM_MAMORI") else ["test_seam_mamori.py"]


@pytest.fixture(autouse=True)
def _no_akashi_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every ``AKASHI_*`` variable for the duration of a test.

    This includes the two the seam job sets, so `test_seam_mamori.py` reads
    them at import time. A test that read ``AKASHI_SEAM_MAMORI_REF`` from
    inside its own body would find it gone and skip the pin check in the one
    place the pin exists.
    """
    for name in list(os.environ):
        if name.startswith("AKASHI_"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Run inside ``tmp_path``, so a relative path cannot reach the repository."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def published_schema() -> Path:
    """The report contract, reached the way a consumer reaches it.

    `importlib.resources` rather than a path from this file, which is the whole
    point of #57: the schema moved into the package tree, so one route now
    works in a source checkout, an editable install and a wheel. A test that
    kept walking up from `__file__` would keep passing while the route akashi
    documents was broken -- and that route being broken is precisely how the
    schema shipped empty once before (`docs/measurements.md`).
    """
    from importlib.resources import files

    shipped = files("akashi") / "schemas" / "audit-report-1.json"
    return Path(str(shipped))
