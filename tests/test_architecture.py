"""The layering, as an executable table.

``AGENTS.md`` describes these rules in prose. This file is the authority: a
table that stops matching the code turns the build red here, rather than
quietly becoming fiction.

``import-linter`` asserts the *direction* between layers and is configured in
``.importlinter``. It cannot express "everything except the standard library",
which is the rule that matters most (ADR-0001), so that one lives here.

The table is written for the whole design, not for what exists today. A layer
with no modules yet is governed the moment its first module appears, which is
the point of writing it now.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "akashi"

#: Which layer may import which. The key is a layer, the value is every layer
#: its modules are allowed to name. A layer may always import itself.
ALLOWED: dict[str, frozenset[str]] = {
    # The domain knows about no other layer, and about nothing outside the
    # standard library. It raises built-in exceptions rather than importing
    # ``errors``, which keeps this set genuinely empty.
    "domain": frozenset(),
    "errors": frozenset(),
    "ports": frozenset({"domain", "errors"}),
    "infrastructure": frozenset({"domain", "ports", "errors"}),
    "application": frozenset({"domain", "ports", "errors"}),
    "evaluation": frozenset({"domain", "ports", "application", "infrastructure", "errors"}),
    "config": frozenset({"domain", "ports", "application", "infrastructure", "errors"}),
    "interfaces": frozenset(
        {"domain", "ports", "application", "infrastructure", "evaluation", "config", "errors"}
    ),
    # The package's own ``__init__`` is the public surface. It re-exports and
    # decides nothing.
    "public": frozenset(
        {"domain", "ports", "application", "infrastructure", "evaluation", "config", "errors"}
    ),
}

#: Layers whose modules may not import anything outside the standard library.
#: ADR-0001. The whole package declares zero runtime dependencies, so in
#: practice this holds everywhere -- but the domain is the one where it is a
#: guarantee rather than a current fact, so it is asserted separately.
STDLIB_ONLY = frozenset({"domain"})

#: akashi audits locally or it does not audit (ADR-0003). Unlike ``tsumugi``
#: there is no carve-out for a networked adapter, because there is nothing
#: akashi needs from anywhere else -- a report that depended on a service would
#: not be reproducible, and reproducibility is the product.
FORBIDDEN_ANYWHERE = frozenset({"socket", "ssl", "http", "asyncio", "urllib", "ftplib", "smtplib"})

#: Read through the contract, never through an import (ADR-0007). The
#: ``siblings`` extra installs these so the seam tests can run against the
#: reference producer; nothing under ``src/`` may name them.
NEVER_IMPORTED = frozenset({"tsumugi", "kiseki"})

#: The redactor is optional and isolated (ADR-0008). Only an adapter may know
#: it exists; everything above is handed a restorer or nothing.
ADAPTER_ONLY = frozenset({"mamori"})


def _layer_of(module: Path) -> str:
    """The layer a module file belongs to, by its path."""
    parts = module.relative_to(SRC).parts
    if len(parts) == 1:
        return "public" if parts[0] == "__init__.py" else parts[0].removesuffix(".py")
    return parts[0]


def _is_adapter(module: Path) -> bool:
    """Inside ``infrastructure/adapters/``, where the outside world is allowed."""
    parts = module.relative_to(SRC).parts
    return len(parts) > 2 and parts[0] == "infrastructure" and parts[1] == "adapters"


def _modules() -> list[Path]:
    found = sorted(SRC.rglob("*.py"))
    assert found, f"no modules under {SRC}; the test is measuring nothing"
    return found


def _imported_roots(module: Path) -> set[tuple[str, int]]:
    """Every top-level module name this file imports, with its line number.

    Relative imports are resolved against the file's own package, so
    ``from ..domain.segment import Segment`` reports ``akashi.domain.segment``.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    package = ["akashi", *module.relative_to(SRC).parts[:-1]]
    found: set[tuple[str, int]] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level + 1]
                found.add((".".join([*base, node.module or ""]).rstrip("."), node.lineno))
            elif node.module:
                found.add((node.module, node.lineno))
    return found


ALL_MODULES = _modules()


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: str(m.relative_to(SRC)))
def test_a_module_imports_only_from_layers_it_is_allowed_to(module: Path) -> None:
    layer = _layer_of(module)
    assert layer in ALLOWED, f"{module} sits in an unknown layer {layer!r}; add it to ALLOWED"
    permitted = ALLOWED[layer] | {layer}

    for name, line in sorted(_imported_roots(module)):
        if not name.startswith("akashi"):
            continue
        parts = name.split(".")
        if len(parts) < 2:
            continue
        imported = parts[1].removesuffix(".py")
        assert imported in permitted, (
            f"{module.relative_to(SRC)}:{line} imports {name!r}: "
            f"the {layer!r} layer may not reach into {imported!r}. "
            f"Allowed: {sorted(permitted)}"
        )


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: str(m.relative_to(SRC)))
def test_the_domain_imports_only_the_standard_library(module: Path) -> None:
    if _layer_of(module) not in STDLIB_ONLY:
        pytest.skip("not a stdlib-only layer")

    for name, line in sorted(_imported_roots(module)):
        root = name.split(".")[0]
        if root == "akashi":
            continue
        assert root in sys.stdlib_module_names, (
            f"{module.relative_to(SRC)}:{line} imports {name!r}, which is not in the "
            f"standard library. See docs/adr/0001-the-domain-depends-on-nothing.md"
        )


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: str(m.relative_to(SRC)))
def test_nothing_in_akashi_opens_a_socket(module: Path) -> None:
    """No exceptions, no allow-list, no adapter.

    An audit that could reach the network could neither be reproduced nor be
    run inside the networks that most need it. ADR-0003.
    """
    for name, line in sorted(_imported_roots(module)):
        root = name.split(".")[0]
        assert root not in FORBIDDEN_ANYWHERE, (
            f"{module.relative_to(SRC)}:{line} imports {name!r}. akashi audits with no "
            f"network at all, everywhere, and that is a guarantee rather than a default. "
            f"See docs/adr/0003-an-audit-is-reproducible.md"
        )


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: str(m.relative_to(SRC)))
def test_the_producer_is_read_through_its_contract_and_never_imported(module: Path) -> None:
    for name, line in sorted(_imported_roots(module)):
        root = name.split(".")[0]
        assert root not in NEVER_IMPORTED, (
            f"{module.relative_to(SRC)}:{line} imports {name!r}. A ContextPackage is read "
            f"as JSON against a published contract, so that akashi audits answers from any "
            f"conforming producer. See docs/adr/0007-read-the-producer-through-its-contract.md"
        )


@pytest.mark.parametrize("module", ALL_MODULES, ids=lambda m: str(m.relative_to(SRC)))
def test_only_the_adapters_may_know_about_the_redactor(module: Path) -> None:
    for name, line in sorted(_imported_roots(module)):
        root = name.split(".")[0]
        if root not in ADAPTER_ONLY:
            continue
        assert _is_adapter(module), (
            f"{module.relative_to(SRC)}:{line} imports {name!r} outside "
            f"infrastructure/adapters/. akashi audits plain text with nothing installed, "
            f"and that is checked rather than promised. "
            f"See docs/adr/0008-restore-before-you-audit.md"
        )
