"""What is actually installed, as facts rather than as a verdict.

`akashi doctor` prints this. Everything here is a *measurement of the running
installation* -- not of the repository, not of what `pyproject.toml` declares.
The distinction is the whole reason the command exists: two of the three
defects this project has shipped were invisible in development and obvious on
the machine that had them, and neither could be found by reading a declaration.

**Nothing here decides whether the installation is good.** A function that
returned "healthy" would be a second place a verdict comes from, and a reader
would take the word instead of the facts. `doctor` prints what was found and
names what is missing; a missing contract is missing whatever else is fine.

**And it never imports the siblings.** Whether `mamori` is importable is a fact
about the environment and it is obtained by asking `importlib` for the
specification, not by importing the package -- an import runs somebody else's
code, which is not what a diagnostic is allowed to do to a machine somebody is
already suspicious of.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from importlib import resources
from importlib.util import find_spec
from typing import Any

__all__ = [
    "Finding",
    "Installation",
    "inspect",
]

#: The contract akashi promises to ship, and where it lives inside the package.
#:
#: Read through ``importlib.resources`` rather than from a path relative to this
#: file. The two are the same in a source checkout and different in a zip
#: import, and the one that works everywhere is the one that does not assume the
#: package is a directory.
SCHEMA = ("schemas", "audit-report-1.json")

#: The siblings a caller might expect to be able to hand akashi. Absence is not
#: a fault: akashi installs and runs without any of them (ADR-0001), and the
#: adapters name no import. Reported because "is mamori here" is the question
#: somebody debugging a restoration asks first.
SIBLINGS = ("mamori", "tsumugi", "kiseki", "musubi", "iriguchi")


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing looked at, and what was there.

    ``ok`` is whether the thing was *found and readable*, never whether it is
    good. A sibling that is not installed is ``ok=False`` and not a fault, which
    is why the caller decides what a false means and this does not.
    """

    what: str
    detail: str
    ok: bool = True


@dataclass(frozen=True, slots=True)
class Installation:
    """Everything `doctor` found, in the order it prints."""

    akashi_version: str
    python_version: str
    platform: str
    location: str
    console_encoding: str
    stdout_errors: str
    contract: Finding
    packs: tuple[Finding, ...] = ()
    siblings: tuple[Finding, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def missing(self) -> tuple[Finding, ...]:
        """What was looked for and not found, siblings excluded.

        A sibling that is absent is a fact about the machine. A contract that is
        absent is a broken installation: akashi promised to ship it, a consumer
        was told where to find it, and it is not there.
        """
        return tuple(one for one in (self.contract, *self.packs) if not one.ok)


def inspect(packs: tuple[Any, ...]) -> Installation:
    """Look at the running installation. Reads; imports nothing new."""
    from akashi import __version__

    return Installation(
        akashi_version=__version__,
        python_version=sys.version.split()[0],
        platform=sys.platform,
        location=_location(),
        console_encoding=_encoding(),
        stdout_errors=str(getattr(sys.stdout, "errors", "") or "unknown"),
        contract=_contract(),
        packs=tuple(
            Finding("pack", f"{pack.code}  {pack.name}  {len(pack.rules)} rules  v{pack.version}")
            for pack in packs
        ),
        siblings=tuple(_sibling(name) for name in SIBLINGS),
        notes=_notes(),
    )


def _contract() -> Finding:
    """The schema akashi ships, hashed.

    Read and hashed rather than validated: validating would need `jsonschema`,
    which akashi does not depend on and will not (ADR-0001). Whether the bytes
    are there and which bytes they are is a smaller question and the one a
    consumer actually has -- *is the contract you promised me the one I have.*
    """
    try:
        shipped = resources.files("akashi").joinpath(*SCHEMA)
        raw = shipped.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as error:
        return Finding(
            "contract",
            f"{'/'.join(SCHEMA)} is not in the installed package ({error.__class__.__name__}). "
            f"Consumers were told it ships in the wheel; this installation cannot show it.",
            ok=False,
        )

    digest = hashlib.sha256(raw).hexdigest()
    try:
        identifier = json.loads(raw.decode("utf-8")).get("$id", "")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return Finding(
            "contract",
            f"{'/'.join(SCHEMA)} is present and is not readable JSON: {error}",
            ok=False,
        )
    return Finding("contract", f"{identifier or '/'.join(SCHEMA)}  sha256:{digest}")


def _sibling(name: str) -> Finding:
    """Whether a package is importable, without importing it.

    ``find_spec`` answers the question and runs none of the package's code. A
    diagnostic that imported five libraries to report on them would be changing
    the machine it is describing, and on a machine somebody is already
    suspicious of that is the wrong trade.
    """
    try:
        found = find_spec(name) is not None
    except (ImportError, ValueError):
        found = False
    return Finding(name, "importable" if found else "not installed", ok=found)


def _location() -> str:
    import akashi

    paths = list(getattr(akashi, "__path__", []))
    return paths[0] if paths else "unknown"


def _encoding() -> str:
    return str(getattr(sys.stdout, "encoding", "") or "unknown")


def _notes() -> tuple[str, ...]:
    """What the numbers above mean for this machine, where it is not obvious.

    Only where it is *not* obvious. A diagnostic that explained every line would
    be a diagnostic nobody reads to the end, and the line that matters would be
    in the middle of it.
    """
    notes: list[str] = []
    encoding = _encoding().lower().replace("-", "").replace("_", "")
    if encoding not in {"utf8", "utf8mb4", "unknown"}:
        notes.append(
            f"This console is {_encoding()}, not UTF-8. akashi's own prose is ASCII so it "
            f"prints; text akashi echoes from your documents may lose characters it "
            f"cannot represent. Reports and attestations are written as UTF-8 bytes "
            f"regardless of this, so a redirected --json is valid JSON."
        )
    # There is no note about the Python version. `requires-python = ">=3.12"`
    # means a machine that could run this line already passed that check, and a
    # branch that cannot be reached is a check only in appearance.
    return tuple(notes)
