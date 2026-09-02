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

import tomllib
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
    """The one job with a *real* install rather than an editable one.

    Since #57 the schema lives inside the package tree, so an editable install
    can open it too -- which makes this step cheaper rather than redundant: it
    is now the only place that checks the path resolves in the artefact a user
    actually receives, and those two stopped being the same file the day the
    build was misconfigured (`docs/measurements.md`).
    """
    assert "importlib.resources" in commands_in(WORKFLOWS / "ci.yml")


def test_doctor_is_run_against_a_real_install() -> None:
    """`akashi doctor` exits non-zero when something akashi promised to ship is
    absent, so running it here covers both halves of #57 at once: the contract
    reaches a real install, and the reader that reports on it works there.

    Asserted structurally rather than by grepping the file, because a `doctor`
    inside a comment or a `continue-on-error` step reads the same to `grep` and
    proves nothing.
    """
    steps = [
        step
        for job in yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))[
            "jobs"
        ].values()
        for step in job.get("steps", [])
        if "akashi doctor" in str(step.get("run", ""))
    ]
    assert steps, "no CI step runs `akashi doctor`"
    for step in steps:
        assert not step.get("continue-on-error"), (
            "a doctor step that cannot fail the job is a doctor step that reports nothing"
        )


def _job(name: str) -> dict[str, object]:
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert name in jobs, f"ci.yml has no {name!r} job; jobs are {sorted(jobs)}"
    return dict(jobs[name])


def test_the_seam_job_installs_the_sibling_by_direct_reference() -> None:
    """#59. `mamori` is on no index, and the name is free there, so an index
    install would be a different package with the same name."""
    steps = _job("seam-mamori")["steps"]
    assert isinstance(steps, list)
    installs = [
        step
        for step in steps
        if "git+https://github.com/Nananananana/mamori.git" in str(step.get("run", ""))
    ]
    assert installs, "the seam job does not install mamori by direct git reference"


def test_the_seam_job_pins_a_commit_and_exports_it() -> None:
    """A seam result that cannot be tied to a revision is not reproducible, and
    the test that checks the pin reads it from the environment -- so if the
    variable disappears, that check skips itself in the one place it applies.
    This is what stops that.
    """
    job = _job("seam-mamori")
    env = job.get("env")
    assert isinstance(env, dict)
    reference = str(env.get("AKASHI_SEAM_MAMORI_REF", ""))
    assert len(reference) == 40 and all(c in "0123456789abcdef" for c in reference), (
        f"AKASHI_SEAM_MAMORI_REF should be a full commit sha, not {reference!r}"
    )
    assert env.get("AKASHI_SEAM_MAMORI"), (
        "without this the seam file is not collected at all, and `-m siblings` would select nothing"
    )


def test_no_continue_on_error_anywhere_in_the_seam_job() -> None:
    """Observed in `tsumugi`: a job-level `continue-on-error` swallowed an
    install failure and the job had never run once. Nothing said so, because a
    swallowed setup failure looks exactly like a passing job.

    A setup failure must be red, and it is a different finding from "the seam
    failed" -- only the second is a fact about the seam.
    """
    job = _job("seam-mamori")
    assert not job.get("continue-on-error"), "the seam job may not swallow its own failures"
    steps = job["steps"]
    assert isinstance(steps, list)
    for step in steps:
        assert not step.get("continue-on-error"), (
            f"step {step.get('name')!r} cannot fail the job, so it reports nothing"
        )


def test_the_direct_reference_is_not_in_the_distribution_metadata() -> None:
    """#59's first trap, and the expensive one. An extra reaches the built
    distribution as `Requires-Dist: mamori @ git+... ; extra == 'siblings'`, and
    PyPI refuses **any** distribution whose metadata carries a direct
    reference. One line in an extra nobody installs would make the whole
    distribution unpublishable.
    """
    config = tomllib.loads((WORKFLOWS.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    declared = list(project.get("dependencies", []))
    for group in (project.get("optional-dependencies") or {}).values():
        declared.extend(group)
    offenders = [one for one in declared if "@" in one and "git+" in one]
    assert not offenders, (
        f"a direct reference in project metadata makes the distribution unpublishable: {offenders}"
    )


def test_the_seam_job_type_checks_the_file_the_ordinary_run_excludes() -> None:
    """`tests/test_seam_mamori.py` is excluded from the default mypy run,
    because it can only be checked where `mamori` is installed. That exclusion
    is a hole unless somewhere checks it, and this is what says somewhere does.

    The alternative -- `ignore_missing_imports` for `mamori` -- would type-check
    the seam against `Any`, which agrees with every reading of the sibling. That
    is the thing a seam exists not to do.
    """
    config = tomllib.loads((WORKFLOWS.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    excluded = str(config["tool"]["mypy"].get("exclude", ""))
    assert "test_seam_mamori" in excluded, (
        "if the seam file is no longer excluded from the ordinary mypy run, "
        "delete this test and the step it guards rather than leaving both"
    )

    steps = _job("seam-mamori")["steps"]
    assert isinstance(steps, list)
    checked = [
        step
        for step in steps
        if "mypy" in str(step.get("run", "")) and "test_seam_mamori" in str(step.get("run", ""))
    ]
    assert checked, "the seam file is excluded from mypy everywhere, so it is checked nowhere"
