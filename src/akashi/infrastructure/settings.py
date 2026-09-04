"""Where a setting came from, as well as what it is.

akashi reads settings the way the tools around it do -- `pyproject.toml`, a
standalone file, the environment, the command line, in that order of increasing
precedence -- because a person configuring a Python project should not have to
learn a new place to put things.

**And it records the source of every value.** That is not politeness. A setting
here changes the audit: `matcher` decides which strings count as the same
string, and `languages` decides the segmentation and therefore every count on
the report. A file three directories up that quietly changed either would make
two runs disagree with no visible reason, which is the failure this whole
project is about. So `akashi doctor` prints what was resolved and where each
part of it came from, and a value that came from a file says which file.

**Only settings that are already on the report may be set here.** Both of them
are in `report_id` (ADR-0009 for the packs, and the matcher for the same
reason), so a report made under one configuration cannot be mistaken for a
report made under another. A setting that changed an audit *without* reaching
the report would be unreachable by `recheck`, and this module is the wrong place
to add the first one.

`MAX_RUN` and `MAX_DEPTH` are deliberately **not** here. They are bounds akashi
states about its own cost on hostile input, and a configuration file that could
raise them would be a configuration file that could reintroduce the quadratic
blowup they exist to stop.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from akashi.errors import ContractError

__all__ = ["FILE", "SECTION", "Settings", "load_settings"]

#: The standalone file, for a project that keeps akashi's settings out of
#: `pyproject.toml`. Read *after* `pyproject.toml`, so it wins.
FILE = "akashi.toml"

#: The table both files use. In `pyproject.toml` it is `[tool.akashi]`; in
#: `akashi.toml` it is the top level, which is what every tool that offers both
#: does and what a reader will expect without being told.
SECTION = "akashi"

#: Every setting akashi reads, and nothing else. An unknown key is refused
#: rather than ignored: a typo in a configuration file is a setting somebody
#: believes is in force, and silence is what makes that belief last.
KNOWN = frozenset({"matcher", "languages", "fail_on_findings"})


@dataclass(frozen=True, slots=True)
class Settings:
    """The resolved configuration, and where each part of it came from."""

    matcher: str = ""
    languages: tuple[str, ...] = ()
    fail_on_findings: bool = False
    #: ``{"matcher": "akashi.toml", ...}`` -- only for values somebody set.
    sources: dict[str, str] = field(default_factory=dict)

    def describe(self) -> tuple[str, ...]:
        """One line per setting somebody actually chose, with its source.

        Empty when nothing was configured, which is a different thing from
        everything being at its default and worth being able to see.
        """
        lines: list[str] = []
        for name in sorted(self.sources):
            value = getattr(self, name)
            shown = ", ".join(value) if isinstance(value, tuple) else str(value)
            lines.append(f"{name} = {shown}   (from {self.sources[name]})")
        return tuple(lines)


def load_settings(start: Path | None = None, environ: Mapping[str, str] | None = None) -> Settings:
    """Settings for a run, lowest precedence first.

    ``pyproject.toml`` then ``akashi.toml`` then ``AKASHI_*``. The command line
    is applied by the caller on top of this, because argparse already knows
    which flags were given and reproducing that here would be a second answer
    to the same question.

    Both files are looked for in the working directory and then upwards, the
    way every tool in this ecosystem does it -- a subdirectory of a project is
    still in the project.
    """
    root = Path.cwd() if start is None else Path(start)
    variables: Mapping[str, str] = os.environ if environ is None else environ

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}

    for name in ("pyproject.toml", FILE):
        found = _find(root, name)
        if found is None:
            continue
        for key, value in _read(found, name).items():
            values[key] = value
            sources[key] = str(found)

    for key in sorted(KNOWN):
        variable = f"AKASHI_{key.upper()}"
        if variable in variables:
            values[key] = _from_text(key, variables[variable], variable)
            sources[key] = variable

    return Settings(
        matcher=str(values.get("matcher", "")),
        languages=tuple(values.get("languages", ())),
        fail_on_findings=bool(values.get("fail_on_findings", False)),
        sources=sources,
    )


def _find(start: Path, name: str) -> Path | None:
    for folder in (start, *start.parents):
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def _read(path: Path, name: str) -> dict[str, Any]:
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise ContractError(f"cannot read {path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ContractError(f"{path} is not valid TOML: {error}") from error

    table = document.get("tool", {}).get(SECTION, {}) if name == "pyproject.toml" else document
    if not isinstance(table, dict):
        raise ContractError(f"{path} has a {SECTION!r} section that is not a table")

    unknown = sorted(set(table) - KNOWN)
    if unknown:
        raise ContractError(
            f"{path} sets {', '.join(unknown)}, which akashi does not read. "
            f"It reads: {', '.join(sorted(KNOWN))}. A setting nobody reads is a setting "
            f"somebody believes is in force."
        )
    return {key: _checked(key, value, str(path)) for key, value in table.items()}


def _checked(key: str, value: object, where: str) -> Any:
    """A value of the shape the setting takes, or a refusal naming both."""
    if key == "languages":
        if not isinstance(value, list) or not all(isinstance(one, str) for one in value):
            raise ContractError(f"{where}: 'languages' is a list of pack codes, not {value!r}")
        return list(value)
    if key == "fail_on_findings":
        if not isinstance(value, bool):
            raise ContractError(f"{where}: 'fail_on_findings' is true or false, not {value!r}")
        return value
    if not isinstance(value, str):
        raise ContractError(f"{where}: {key!r} is a string, not {value!r}")
    return value


def _from_text(key: str, raw: str, where: str) -> Any:
    """An environment variable, which is always text, as the setting's type."""
    if key == "languages":
        return [one.strip() for one in raw.split(",") if one.strip()]
    if key == "fail_on_findings":
        lowered = raw.strip().lower()
        if lowered not in {"0", "1", "true", "false", "yes", "no"}:
            raise ContractError(
                f"{where}={raw!r} is not a yes or a no. akashi reads "
                f"1/0, true/false, yes/no -- and refuses anything else rather than "
                f"reading it as false, which is how a gate silently stops gating."
            )
        return lowered in {"1", "true", "yes"}
    return raw
