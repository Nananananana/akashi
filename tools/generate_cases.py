#!/usr/bin/env python3
"""Build the labelled corpus, or check that the committed one still matches.

    python tools/generate_cases.py --seed 20260830 --out tests/cases
    python tools/generate_cases.py --seed 20260830 --out tests/cases --check-only

``--check-only`` runs in CI on every push, and that is not belt-and-braces. A
generated case that is broken fails a *correct* implementation, so the oracle
has to be checked as often as the code it is checking. Without it a bad fixture
looks exactly like a regression, and somebody spends an afternoon fixing the
wrong thing.

No model runs here. A model wrote the prose once, at authoring time, and it is
committed under ``src/akashi/evaluation/genres/``. This composes it (ADR-0003).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from akashi.evaluation.generation import GENERATOR, rendered
from akashi.evaluation.genres import genres

#: How many cases each genre is cut into. Every sentence a genre carries is
#: used exactly once across its cases, so this decides how many sentences sit
#: together rather than how much material there is.
PER_GENRE = 4

DEFAULT_SEED = 20260830


def _all_files(seed: int, per_genre: int, languages: Sequence[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for spec in genres(*languages):
        total = min(per_genre, len(spec.sentences))
        for index in range(total):
            files.update(rendered(spec, seed, index, total))
    return files


def _write(out: Path, files: dict[str, str], fresh: bool) -> int:
    if fresh and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, body in sorted(files.items()):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
    cases = len({name.split("/")[0] for name in files})
    print(f"wrote {cases} cases ({len(files)} files) to {out}")
    return 0


def _check(out: Path, files: dict[str, str]) -> int:
    wrong: list[str] = []
    for name, body in sorted(files.items()):
        path = out / name
        if not path.is_file():
            wrong.append(f"{name}: missing")
        elif path.read_text(encoding="utf-8") != body:
            wrong.append(f"{name}: differs from what the generator produces")

    on_disk = {
        f"{folder.name}/{child.name}"
        for folder in out.iterdir()
        if folder.is_dir()
        for child in folder.iterdir()
    }
    for name in sorted(on_disk - set(files)):
        wrong.append(f"{name}: on disk and not generated")

    if wrong:
        print(f"{len(wrong)} case files disagree with the generator:", file=sys.stderr)
        for line in wrong[:20]:
            print(f"  {line}", file=sys.stderr)
        if len(wrong) > 20:
            print(f"  ... and {len(wrong) - 20} more", file=sys.stderr)
        print(
            "\nRegenerate with the same seed, or find out why the generator moved. "
            "A broken fixture fails a correct implementation.",
            file=sys.stderr,
        )
        return 1
    cases = len({name.split("/")[0] for name in files})
    print(f"{cases} cases match the generator ({GENERATOR}, seed in each manifest)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default="tests/cases", metavar="DIR")
    parser.add_argument("--per-genre", type=int, default=PER_GENRE, metavar="N")
    parser.add_argument(
        "--language", action="append", default=[], metavar="CODE", help="repeatable"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="re-derive every case and fail if the committed corpus differs",
    )
    arguments = parser.parse_args(argv)

    out = Path(arguments.out)
    files = _all_files(arguments.seed, arguments.per_genre, arguments.language)

    if arguments.check_only:
        if not out.is_dir():
            print(f"no corpus at {out}", file=sys.stderr)
            return 1
        return _check(out, files)
    return _write(out, files, fresh=not arguments.language)


if __name__ == "__main__":
    raise SystemExit(main())
