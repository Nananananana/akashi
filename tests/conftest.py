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


@pytest.fixture(autouse=True)
def _no_akashi_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every ``AKASHI_*`` variable for the duration of a test."""
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
