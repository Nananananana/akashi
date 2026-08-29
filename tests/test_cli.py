"""``akashi audit``, from the outside.

Every test here isolates itself: it chdirs into ``tmp_path`` and copies what it
needs, so a relative path can never reach the repository. That is the sibling
projects' rule, and each of them learned it by writing into a developer's real
data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from akashi import __version__
from akashi.interfaces.cli.main import AUDITED, FOUND, REFUSED, main

FIXTURES = Path(__file__).parent
ANSWER = "テントは 2.6kg、二人用です。前回より 300g 軽くなりました。\n"


@pytest.fixture
def workspace(isolated: Path) -> Path:
    """A directory holding a package and an answer, and nothing else."""
    shutil.copy(FIXTURES / "packages" / "gear-ja.json", isolated / "package.json")
    (isolated / "answer.txt").write_text(ANSWER, encoding="utf-8")
    return isolated


def run(*argv: str) -> int:
    return main(list(argv))


# --- The ordinary run --------------------------------------------------------


def test_an_audit_prints_a_report_and_exits_zero(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("audit", "--package", "package.json", "--response", "answer.txt") == AUDITED
    printed = capsys.readouterr().out
    assert printed.startswith("akashi — ")


def test_the_output_leads_with_what_was_not_checked(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A deliberate reversal of what every dashboard in this category does, and
    the reason the output can be handed to a reviewer (ADR-0005)."""
    run("audit", "--package", "package.json", "--response", "answer.txt")
    printed = capsys.readouterr().out
    assert printed.index("Not checked") < printed.index("Findings")
    assert printed.index("Findings") < printed.index("Coverage")


def test_the_output_ends_with_what_it_does_not_establish(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run("audit", "--package", "package.json", "--response", "answer.txt")
    printed = capsys.readouterr().out
    assert "What this does not establish" in printed
    assert "not about truth" in printed


def test_a_floating_particular_prints_with_its_span(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run("audit", "--package", "package.json", "--response", "answer.txt")
    printed = capsys.readouterr().out
    assert "2.6kg  [5:10]  is in none of the text that was sent" in printed


def test_a_grounded_particular_prints_with_where_it_was_found(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "answer.txt").write_text("前回より 300g 軽い。\n", encoding="utf-8")
    run("audit", "--package", "package.json", "--response", "answer.txt")
    printed = capsys.readouterr().out
    assert "300g" in printed
    assert "notes/2025-06-03-装備メモ.md" in printed


def test_the_report_carries_no_terminal_escapes(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """This is as likely to be redirected into a file somebody attaches to a
    filing as it is to be read on a screen."""
    run("audit", "--package", "package.json", "--response", "answer.txt")
    assert "\x1b" not in capsys.readouterr().out


# --- JSON --------------------------------------------------------------------


def test_json_emits_the_report_as_a_document(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run("audit", "--package", "package.json", "--response", "answer.txt", "--json")
    document = json.loads(capsys.readouterr().out)
    assert document["contract"] == "akashi.audit-report/1-draft"
    assert document["coverage"]["segments"] == 2
    assert document["limits"]
    assert document["audited"]["akashi_version"] == __version__


def test_the_json_is_not_escaped_into_unreadability(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Half of what akashi audits is CJK, and a report full of ``\\u30c6`` is a
    report nobody reads."""
    run("audit", "--package", "package.json", "--response", "answer.txt", "--json")
    printed = capsys.readouterr().out
    assert "テント" in printed
    assert "\\u30c6" not in printed


def test_the_json_puts_the_caveats_before_the_findings(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON objects are unordered by specification and ordered in practice, and
    a reader skimming the raw file is a real reader."""
    run("audit", "--package", "package.json", "--response", "answer.txt", "--json")
    keys = list(json.loads(capsys.readouterr().out))
    assert keys.index("contract") == 0
    assert keys.index("unchecked") < keys.index("segments")
    assert keys.index("coverage") < keys.index("segments")
    assert keys.index("limits") < keys.index("segments")


def test_the_json_reports_no_share_rather_than_a_perfect_one(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "answer.txt").write_text("装備は満足のいくものでした。\n", encoding="utf-8")
    run("audit", "--package", "package.json", "--response", "answer.txt", "--json")
    document = json.loads(capsys.readouterr().out)
    assert document["counts"]["grounded_share"] is None


# --- Reading the answer ------------------------------------------------------


def test_the_answer_may_come_from_standard_input(
    workspace: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import io
    import sys

    stdin = io.TextIOWrapper(io.BytesIO(ANSWER.encode("utf-8")), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stdin)
    assert run("audit", "--package", "package.json", "--response", "-") == AUDITED
    assert "2.6kg" in capsys.readouterr().out


def test_an_answer_is_read_as_utf8_whatever_the_platform_thinks(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "answer.txt").write_bytes("テントは 2.4kg。\n".encode())
    run("audit", "--package", "package.json", "--response", "answer.txt", "--json")
    document = json.loads(capsys.readouterr().out)
    assert document["answer"] == "テントは 2.4kg。\n"


def test_an_answer_that_is_not_utf8_is_refused_rather_than_audited(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Text read with the wrong encoding audits as fabricated in full."""
    (workspace / "answer.txt").write_bytes("テントは 2.4kg。".encode("shift_jis"))
    assert run("audit", "--package", "package.json", "--response", "answer.txt") == REFUSED
    assert "not UTF-8" in capsys.readouterr().err


# --- Exit codes --------------------------------------------------------------


def test_a_missing_package_is_a_refusal_and_not_a_traceback(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal is an answer. A traceback reads as a bug in the tool."""
    assert run("audit", "--package", "nothing.json", "--response", "answer.txt") == REFUSED
    error = capsys.readouterr().err
    assert error.startswith("akashi: ")
    assert "Traceback" not in error


def test_a_missing_answer_is_a_refusal(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("audit", "--package", "package.json", "--response", "nothing.txt") == REFUSED
    assert capsys.readouterr().err.startswith("akashi: ")


def test_a_protected_answer_is_refused_with_the_reason(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copy(FIXTURES / "packages" / "protected-ja.json", isolated / "package.json")
    (isolated / "answer.txt").write_text("<PERSON_001> は担当です。\n", encoding="utf-8")
    assert run("audit", "--package", "package.json", "--response", "answer.txt") == REFUSED
    error = capsys.readouterr().err
    assert "no restorer was given" in error
    assert "restored_by" in error


def test_finding_something_is_not_a_failure_by_default(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Finding things is what an auditor does, and a non-zero exit for that
    would make the ordinary case look like a failure."""
    assert run("audit", "--package", "package.json", "--response", "answer.txt") == AUDITED


def test_a_caller_may_ask_for_findings_to_fail_the_build(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(
        "audit", "--package", "package.json", "--response", "answer.txt", "--fail-on-findings"
    )
    assert code == FOUND


def test_nothing_floating_passes_even_with_the_gate_on(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (workspace / "answer.txt").write_text("前回より 300g 軽い。\n", encoding="utf-8")
    code = run(
        "audit", "--package", "package.json", "--response", "answer.txt", "--fail-on-findings"
    )
    assert code == AUDITED


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["audit"],
        ["audit", "--package", "package.json"],
        ["audit", "--response", "answer.txt"],
        ["nonsense"],
    ],
)
def test_a_wrong_command_line_exits_two(workspace: Path, argv: list[str]) -> None:
    """argparse's own code, and it is the right one: a caller has to tell "you
    used it wrong" from "it would not run"."""
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2


def test_the_version_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert __version__ in capsys.readouterr().out


# --- Options -----------------------------------------------------------------


def test_the_language_packs_can_be_narrowed_for_measurement(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(
        "audit",
        "--package",
        "package.json",
        "--response",
        "answer.txt",
        "--language",
        "ja",
        "--json",
    )
    document = json.loads(capsys.readouterr().out)
    assert document["audited"]["segmenters"] == ["akashi.segmenter/ja@1"]


def test_an_unknown_language_is_refused_by_name(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ValueError, match="no language pack for"):
        run(
            "audit",
            "--package",
            "package.json",
            "--response",
            "answer.txt",
            "--language",
            "ko",
        )


def test_a_caller_may_assert_that_they_restored_the_answer(
    isolated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copy(FIXTURES / "packages" / "protected-ja.json", isolated / "package.json")
    (isolated / "answer.txt").write_text("田中は 第30条 の対応を担当。\n", encoding="utf-8")
    code = run(
        "audit",
        "--package",
        "package.json",
        "--response",
        "answer.txt",
        "--restored-by",
        "mamori@0.17.0",
    )
    assert code == AUDITED
    assert "akashi did not verify it" in capsys.readouterr().out


def test_the_cli_writes_nothing_to_disk(workspace: Path) -> None:
    """An auditor that left files behind would be one whose output a reader has
    to go looking for. Everything goes to standard output."""
    before = sorted(path.name for path in workspace.iterdir())
    run("audit", "--package", "package.json", "--response", "answer.txt")
    assert sorted(path.name for path in workspace.iterdir()) == before
