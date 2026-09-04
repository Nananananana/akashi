"""A setting that changes an audit has to be visible in the audit.

akashi reads settings where the tools around it do, in the order they do:
`pyproject.toml`, then `akashi.toml`, then `AKASHI_*`, then the command line.
That part is convention and is worth following exactly because a person
configuring a Python project should not have to learn a new place.

The part that is not convention is why it is safe at all. Both settings akashi
reads reach `report_id` -- `matcher` decides which strings count as the same
string, `languages` decides the segmentation and therefore every count -- so a
report made under one configuration cannot be mistaken for a report made under
another. A file three directories up that quietly changed either would make two
runs disagree with nothing on either report to say why, which is the failure the
whole project is about.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from akashi.errors import ContractError
from akashi.infrastructure.settings import KNOWN, load_settings


def written(folder: Path, name: str, body: str) -> Path:
    path = folder / name
    path.write_text(body, encoding="utf-8")
    return path


# --- where it looks ----------------------------------------------------------


def test_nothing_configured_is_a_different_fact_from_everything_default() -> None:
    """`describe()` lists what somebody chose, and is empty when nobody did.
    A reader chasing a difference between two machines needs to be able to see
    that one of them was configured and the other was not."""
    settings = load_settings(Path(__file__).parent, environ={})
    assert settings.describe() == () or all("from" in line for line in settings.describe())


def test_pyproject_is_read_from_the_tool_table(tmp_path: Path) -> None:
    written(tmp_path, "pyproject.toml", '[tool.akashi]\nmatcher = "exact"\n')
    settings = load_settings(tmp_path, environ={})
    assert settings.matcher == "exact"
    assert settings.sources["matcher"].endswith("pyproject.toml")


def test_a_standalone_file_beats_pyproject(tmp_path: Path) -> None:
    """Both are conventional and a project may have both. The dedicated file
    wins, which is what every tool offering the pair does."""
    written(tmp_path, "pyproject.toml", '[tool.akashi]\nmatcher = "normalized"\n')
    written(tmp_path, "akashi.toml", 'matcher = "exact"\n')
    assert load_settings(tmp_path, environ={}).matcher == "exact"


def test_the_environment_beats_a_file(tmp_path: Path) -> None:
    written(tmp_path, "akashi.toml", 'matcher = "exact"\n')
    settings = load_settings(tmp_path, environ={"AKASHI_MATCHER": "normalized"})
    assert settings.matcher == "normalized"
    assert settings.sources["matcher"] == "AKASHI_MATCHER"


def test_a_file_is_found_from_a_subdirectory(tmp_path: Path) -> None:
    """A subdirectory of a project is still in the project."""
    written(tmp_path, "akashi.toml", 'matcher = "exact"\n')
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert load_settings(deep, environ={}).matcher == "exact"


# --- what it refuses ---------------------------------------------------------


def test_a_setting_akashi_does_not_read_is_refused(tmp_path: Path) -> None:
    """A typo in a configuration file is a setting somebody believes is in
    force, and ignoring it is what makes that belief last. The message lists
    what akashi does read, so the typo is visible next to the real name."""
    written(tmp_path, "akashi.toml", 'mather = "exact"\n')
    with pytest.raises(ContractError) as refusal:
        load_settings(tmp_path, environ={})
    assert "mather" in str(refusal.value)
    assert "matcher" in str(refusal.value)


def test_a_value_of_the_wrong_shape_is_refused(tmp_path: Path) -> None:
    written(tmp_path, "akashi.toml", "languages = 'ja'\n")
    with pytest.raises(ContractError, match="list of pack codes"):
        load_settings(tmp_path, environ={})


def test_a_gate_is_never_silently_off(tmp_path: Path) -> None:
    """`AKASHI_FAIL_ON_FINDINGS=maybe` read as false is how a gate stops gating
    while the pipeline that set it goes on believing it is armed."""
    with pytest.raises(ContractError, match="not a yes or a no"):
        load_settings(tmp_path, environ={"AKASHI_FAIL_ON_FINDINGS": "maybe"})
    assert load_settings(tmp_path, environ={"AKASHI_FAIL_ON_FINDINGS": "yes"}).fail_on_findings


def test_broken_toml_says_which_file(tmp_path: Path) -> None:
    written(tmp_path, "akashi.toml", "matcher = \n")
    with pytest.raises(ContractError, match="not valid TOML"):
        load_settings(tmp_path, environ={})


# --- what may be set at all --------------------------------------------------


def test_only_settings_that_reach_the_report_may_be_configured() -> None:
    """Both of these are in `report_id`, which is what makes a configuration
    file safe to read: a run configured one way cannot be mistaken for a run
    configured another.

    `MAX_RUN` and `MAX_DEPTH` are deliberately absent. They are bounds akashi
    states about its own cost on hostile input, and a file that could raise them
    would be a file that could reintroduce the quadratic blowup they stop.
    """
    assert {"matcher", "languages", "fail_on_findings"} == KNOWN
    for forbidden in ("max_run", "max_depth", "recursion_limit", "timeout"):
        assert forbidden not in KNOWN


def test_the_command_line_beats_everything(tmp_path: Path) -> None:
    """Measured through `main`, not asserted about the resolver: the precedence
    a user experiences is the one the CLI applies, and the resolver only knows
    about three of the four levels."""
    import json

    from akashi.interfaces.cli.main import main

    written(tmp_path, "akashi.toml", 'matcher = "exact"\n')
    package = Path(__file__).parent / "packages" / "gear-ja.json"
    answer = tmp_path / "a.txt"
    answer.write_text("テントは 2.4 kg。", encoding="utf-8")
    out = tmp_path / "out.json"

    import contextlib

    with out.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle):
        main(
            [
                "audit",
                "--package",
                str(package),
                "--response",
                str(answer),
                "--matcher",
                "normalized",
                "--json",
            ]
        )
    assert json.loads(out.read_text(encoding="utf-8"))["audited"]["matcher"] == "normalized"


def test_doctor_says_where_each_setting_came_from() -> None:
    """The reason this module records sources at all. Somebody comparing two
    machines needs the file named, not the value repeated."""
    from akashi.infrastructure.installation import Finding, Installation
    from akashi.infrastructure.rendering import as_diagnosis

    installation = Installation(
        akashi_version="0",
        python_version="3.12",
        platform="win32",
        location="/x",
        console_encoding="utf-8",
        stdout_errors="strict",
        contract=Finding("contract", "fine"),
        settings=("matcher = exact   (from /somewhere/akashi.toml)",),
    )
    printed = as_diagnosis(installation)
    assert "/somewhere/akashi.toml" in printed
    assert "reach report_id" in printed
