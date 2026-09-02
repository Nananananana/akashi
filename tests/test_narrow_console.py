"""akashi has to print on the console its reader actually has.

A Japanese Windows console is `cp932`, and that is what somebody gets by typing
`akashi` without setting anything. Every printing command crashed there —
`audit`, `eval` and `explain` — because akashi's own headings carried an em
dash:

    UnicodeEncodeError: 'cp932' codec can't encode character '\\u2014'

CI never saw it and could not: a runner's locale is UTF-8, and adding more
runners of the same kind does not produce a machine that can fail this way. It
was found by somebody running the command on the machine that has the problem.

**The measurement environment hid it.** Every command in this project's own
development was run with `PYTHONUTF8=1` in front of it, which is exactly the
setting a reader does not have.

Two halves, and they are different problems.

**akashi's own prose must be ASCII.** It is the part akashi controls, and there
is no reason to spend a `?` on a character it chose.

**Everything else must degrade rather than crash.** akashi echoes text it did
not write — the answer, a segment, a source path — and a Chinese document on a
cp932 console cannot be represented at all. `errors="replace"` keeps what the
console can show exactly right and loses only what it cannot. `encoding="utf-8"`
would be worse: the characters become representable and the terminal decodes
them as cp932 anyway, so the Japanese akashi most often prints turns to
mojibake.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from akashi.application import audit
from akashi.domain.report import AuditReport
from akashi.evaluation import load_cases, run
from akashi.evaluation.rendering import as_text as eval_as_text
from akashi.infrastructure.languages import DEFAULT
from akashi.infrastructure.packages import load_package
from akashi.infrastructure.rendering import as_text, explain_segment

PACKAGES = Path(__file__).parent / "packages"
CASES = Path(__file__).parent / "cases"

#: Japanese, which `cp932` handles, with a figure that grounds and one that does
#: not — so the report carries findings, locations and a contradiction.
ANSWER = "テントは 2.4kg、ガスは 250mg カートリッジ。"


def report() -> AuditReport:
    return audit(ANSWER, load_package(PACKAGES / "gear-ja.json"), DEFAULT)


def test_the_text_report_prints_on_a_japanese_console() -> None:
    """Encoded strictly: no `errors="replace"`, so a single character akashi
    chose that `cp932` cannot carry fails here."""
    as_text(report()).encode("cp932")


def test_explain_prints_on_a_japanese_console() -> None:
    archived = json.loads(json.dumps(report().to_dict(), ensure_ascii=False))
    explain_segment(archived, "seg_001").encode("cp932")


def test_the_evaluation_report_prints_on_a_japanese_console() -> None:
    """The one that carries the most akashi-authored prose: floors, notes and
    the caveats under every figure."""
    breakdown, notes = run(load_cases(CASES), DEFAULT)
    eval_as_text(breakdown, notes, cases=30).encode("cp932")


def test_the_japanese_survives_rather_than_being_replaced() -> None:
    """The reason `errors="replace"` was chosen over `encoding="utf-8"`.

    A console that can show the text must show it, not a row of question marks.
    This is the half that `utf-8` would have broken.
    """
    printed = as_text(report())
    assert "テントは 2.4kg" in printed
    assert "テントは 2.4kg" in printed.encode("cp932").decode("cp932")


def test_the_console_helper_asks_for_replacement_rather_than_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The net, for text akashi did not write. A Chinese document audited on a
    `cp932` console still cannot be represented — and losing characters is a
    smaller failure than losing the audit after doing all of its work."""
    import io
    import sys

    from akashi.interfaces.cli.main import _tolerate_a_narrow_console

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp932")
    assert stream.errors != "replace"
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)
    _tolerate_a_narrow_console()
    assert stream.errors == "replace"


def test_a_document_the_console_cannot_show_degrades_rather_than_crashing() -> None:
    """Simplified Chinese on `cp932`. The characters are lost; the audit is
    not, and what is lost is visibly lost rather than silently dropped."""
    import io

    body = as_text(report()) + "\n重量为2.4千克，长度为3.1米。\n"
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp932", errors="replace")
    stream.write(body)
    stream.flush()

    with pytest.raises(UnicodeEncodeError):
        body.encode("cp932")


def test_the_non_conformance_note_prints_on_a_japanese_console() -> None:
    """Prose akashi chose, emitted only when a package carries a field its
    contract does not list -- so the report above never reaches these lines and
    the encoding of akashi's own words here went unmeasured."""
    from akashi.infrastructure.packages.contextpackage import read_package

    raw = json.loads((Path(__file__).parent / "packages" / "gear-ja.json").read_text("utf-8"))
    raw["invented"] = "whatever"
    printed = as_text(audit(ANSWER, read_package(raw), DEFAULT))
    assert "does not conform" in printed
    printed.encode("cp932")


# --- the other half: a document is not prose ---------------------------------
#
# `_tolerate_a_narrow_console` is right for prose and wrong for a document. A
# reader losing a character to `?` keeps the audit; a *program* reading a `?`
# in a report has corruption. akashi read input as UTF-8 deliberately -- the
# docstring on `_read` says so -- and wrote output in whatever the console was,
# by accident.


def cp932_console() -> io.TextIOWrapper:
    """A stdout that behaves like the owner's, bytes and all."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp932", errors="replace")


def written(stream: io.TextIOWrapper) -> bytes:
    stream.flush()
    buffer = stream.buffer
    assert isinstance(buffer, io.BytesIO)
    return buffer.getvalue()


def test_the_json_report_is_utf8_on_a_japanese_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """`akashi audit --json > report.json` on the owner's machine wrote
    `cp932`: not valid JSON (RFC 8259 requires UTF-8), refused by `recheck`,
    `explain` and `certificate`, and carrying a `response_hash` taken over
    UTF-8 bytes the file did not contain.

    **akashi could not read the document akashi had just written.**
    """
    from akashi.interfaces.cli.main import main

    stream = cp932_console()
    monkeypatch.setattr(sys, "stdout", stream)
    answer = Path(__file__).parent / "answers" / "gear-ja.txt"
    code = main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(answer),
            "--json",
        ]
    )
    assert code == 0
    raw = written(stream)
    body = json.loads(raw.decode("utf-8"))
    assert body["answer"] == answer.read_text(encoding="utf-8")
    assert "�" not in body["answer"], "a replacement character is corruption in a document"


def test_the_text_report_still_goes_through_the_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """The half that must *not* change. Prose degrades rather than crashing,
    which is what #75 decided; a fix that sent everything out as UTF-8 bytes
    would put mojibake on the owner's screen instead."""
    from akashi.interfaces.cli.main import main

    stream = cp932_console()
    monkeypatch.setattr(sys, "stdout", stream)
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(Path(__file__).parent / "answers" / "gear-ja.txt"),
        ]
    )
    raw = written(stream)
    assert "テントは".encode("cp932") in raw
    assert "テントは".encode() not in raw


def test_the_report_akashi_wrote_is_a_report_akashi_can_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round trip, which is the whole claim of `docs/audit-report.md`. It
    was false on this machine for every version that had a `--json`."""
    from akashi.infrastructure.reports import load_report
    from akashi.interfaces.cli.main import main

    stream = cp932_console()
    monkeypatch.setattr(sys, "stdout", stream)
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(Path(__file__).parent / "answers" / "gear-ja.txt"),
            "--json",
        ]
    )
    archive = tmp_path / "report.json"
    archive.write_bytes(written(stream))

    document = load_report(archive)
    assert document["contract"].startswith("akashi.audit-report/")

    from akashi.infrastructure.rendering import certificate

    assert "<h2>Traced</h2>" in certificate(document)


def test_the_attestation_is_utf8_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one most likely to be signed, and therefore the one where a byte
    that is not what the signer thinks it is costs the most."""
    from akashi.interfaces.cli.main import main

    stream = cp932_console()
    monkeypatch.setattr(sys, "stdout", stream)
    main(
        [
            "audit",
            "--package",
            str(PACKAGES / "gear-ja.json"),
            "--response",
            str(Path(__file__).parent / "answers" / "gear-ja.txt"),
            "--attestation",
        ]
    )
    statement = json.loads(written(stream).decode("utf-8"))
    assert statement["_type"].startswith("https://in-toto.io/Statement/")
