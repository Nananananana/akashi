"""What decides what runs, and what happens when a piece of it is removed.

`test_layering_config.py` already guards `.importlinter` this way: a contract
deferred there must actually be in the file, or the test guarding it is
guarding nothing. This is the same idea applied to the two other files that
decide what CI checks — and it exists because the *removal* case was never
tested anywhere.

Every guard in this repository had been broken deliberately at least once
before it was trusted, and the audit of that is published in
`docs/measurements.md`. A sibling project then pointed out what all of those
breaks had in common: **they changed a value. None of them took something
away.** Deleting a branch removes the path a guard watches; deleting a file
removes the thing it watches. The two fail differently and only one of them
had been tried.

Measured here rather than assumed, before writing any of it:

| removed | what happens |
|---|---|
| a test file a CI step names | `pytest` exits 4 — guarded, by accident |
| the whole `.pre-commit-config.yaml` | pre-commit exits 1 — guarded |
| **one hook out of the config** | **exit 0. The step passes, having checked less** |
| **`.github/workflows/contracts.yml`** | **nothing. No test mentions it** |

The last two are why this file exists. Both are the shape everything else this
week has had: the check still runs, still goes green, and covers less.

**The configuration is parsed, not grepped.** A guard that matches strings can
match the comment explaining itself — which has now happened five times across
these projects, most recently to a test asserting `"StopIteration" not in
str(error)` that failed against its own fix message. Reading the YAML means the
assertions are about structure, and a comment cannot satisfy one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
HOOKS = ROOT / ".pre-commit-config.yaml"

#: The hooks CI relies on and nothing else performs. Not every hook in the
#: file: a list that had to be kept in step with all of them would be a second
#: definition, and the failure of those is what this file is about. These four
#: are here because each has a stated reason that would go unenforced.
REQUIRED_HOOKS = {
    # An invalid workflow file is not an error anybody is shown. It is a
    # workflow that quietly does not run.
    "check-yaml": "the published schema's siblings, and every workflow, are YAML",
    # `schemas/audit-report-1.json` and every vendored contract.
    "check-json": "a malformed published contract would ship",
    "detect-private-key": "the only security check in the repository",
    # The vendored-contract digests normalise line endings for exactly this
    # reason; this is what stops the repository needing them to.
    "mixed-line-ending": "a Windows checkout otherwise rewrites files it did not change",
}


def loaded(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def hook_ids() -> set[str]:
    config = loaded(HOOKS)
    return {
        hook["id"]
        for repo in config.get("repos", [])
        for hook in repo.get("hooks", [])
        if "id" in hook
    }


def steps_of(workflow: Path, job: str) -> list[dict[str, Any]]:
    return list(loaded(workflow).get("jobs", {}).get(job, {}).get("steps", []))


def commands_in(workflow: Path) -> str:
    """Every `run:` in a workflow, joined. Comments are gone by construction —
    `yaml.safe_load` does not return them — so a guard here cannot be satisfied
    by prose explaining the guard."""
    config = loaded(workflow)
    return "\n".join(
        str(step.get("run", ""))
        for job in config.get("jobs", {}).values()
        for step in job.get("steps", [])
    )


# --- The hooks, which CI now runs and which nothing else performs ------------


def test_the_hook_configuration_is_there_at_all() -> None:
    """The one removal in this class that already failed loudly: pre-commit
    exits 1 on a missing config, so CI catches it. Asserted anyway, because the
    test below is meaningless without it and would skip past a missing file
    with an empty set."""
    assert HOOKS.is_file()
    assert hook_ids(), "the hook configuration declares no hooks"


def test_every_hook_ci_depends_on_is_still_declared() -> None:
    """Removing one hook from the config leaves `pre-commit run --all-files`
    exiting 0. The step passes and checks less, and nothing says so."""
    missing = sorted(set(REQUIRED_HOOKS) - hook_ids())
    assert not missing, (
        f"{missing} were removed from .pre-commit-config.yaml. CI still passes "
        f"without them and checks less: "
        + "; ".join(f"{name} — {why}" for name, why in REQUIRED_HOOKS.items() if name in missing)
    )


def test_ci_runs_the_hooks_over_every_file() -> None:
    """Not over the staged ones. pre-commit's own default is the changed files,
    which is right on a developer's machine and wrong as the only enforcement:
    it never sees a file nobody touched."""
    commands = commands_in(WORKFLOWS / "ci.yml")
    assert "pre_commit run --all-files" in commands or "pre-commit run --all-files" in commands


# --- The workflows -----------------------------------------------------------


def test_the_drift_workflow_exists() -> None:
    """Deleting this file is silent. The vendored copies then go stale exactly
    as they did before anything watched them, and the offline hash check keeps
    passing because it compares akashi's record to akashi's copy."""
    assert (WORKFLOWS / "contracts.yml").is_file()


def test_the_drift_workflow_actually_asks_upstream() -> None:
    """A workflow that exists and runs the offline half would pass this file's
    other test while checking nothing new. The `network` marker is the whole
    point of the job — the offline half already runs in ordinary CI."""
    assert "-m network" in commands_in(WORKFLOWS / "contracts.yml")


def test_the_drift_workflow_is_not_gating_every_pull_request() -> None:
    """Deliberate, and worth pinning because it looks like an oversight.
    Upstream having moved is information about the family, not a defect in
    whatever change is open, and a check that blocks unrelated work is a check
    somebody eventually disables."""
    triggers = loaded(WORKFLOWS / "contracts.yml")[True]
    assert "schedule" in triggers
    assert "paths" in triggers["pull_request"]


def test_the_seam_runs_through_the_installed_entry_point() -> None:
    """A seam that only works when called from inside its own test suite is not
    a seam. Named as its own step so it is visible in a build log rather than
    buried in a suite of 1,300."""
    assert "tests/test_seam_tsumugi.py" in commands_in(WORKFLOWS / "ci.yml")


def test_the_zero_dependency_job_opens_the_installed_artefact() -> None:
    """`force-include` does not apply to an editable install, so this is the
    only place the shipped schema exists to be opened. If the step goes, the
    promise that the contract ships is back to being checked declaration
    against declaration."""
    assert "importlib.resources" in commands_in(WORKFLOWS / "ci.yml")
