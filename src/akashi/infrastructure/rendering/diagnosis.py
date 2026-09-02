"""What `akashi doctor` prints.

Facts first, and the one thing that is wrong named where a reader will hit it
rather than at the end. Somebody running `doctor` is already suspicious of
something; the output has to be readable by them before they know which line
they came for.

Nothing here decides anything, in the same way and for the same reason as every
other renderer in this package. `inspect` looked; this prints what it saw.
"""

from __future__ import annotations

from akashi.infrastructure.installation import Installation

__all__ = ["as_text"]

_INDENT = "  "


def as_text(installation: Installation) -> str:
    lines: list[str] = ["akashi doctor", ""]

    lines += _missing(installation)
    lines += [
        "Installation",
        f"{_INDENT}akashi {installation.akashi_version}",
        f"{_INDENT}Python {installation.python_version} on {installation.platform}",
        f"{_INDENT}{installation.location}",
        "",
        "The contract it ships",
        f"{_INDENT}{installation.contract.detail}",
        "",
    ]

    if installation.packs:
        lines.append("Language packs")
        lines.extend(f"{_INDENT}{pack.detail}" for pack in installation.packs)
        lines.append("")

    lines.append("This console")
    lines.append(
        f"{_INDENT}stdout {installation.console_encoding}, errors={installation.stdout_errors}"
    )
    lines.append("")

    lines.append("Siblings")
    for sibling in installation.siblings:
        lines.append(f"{_INDENT}{sibling.what:<9} {sibling.detail}")
    lines.append(f"{_INDENT}None of these is required. akashi runs without every one of them,")
    lines.append(f"{_INDENT}and a caller who holds a session hands it over.")
    lines.append("")

    if installation.notes:
        lines.append("What that means here")
        for note in installation.notes:
            lines.extend(_wrap(note, 76))
        lines.append("")

    lines += [
        "What this does not establish",
        f"{_INDENT}That akashi is correct. This is what is present, not what it computes.",
        f"{_INDENT}That another machine looks like this one. Run it there.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _missing(installation: Installation) -> list[str]:
    """The broken half, first.

    A `doctor` that printed twenty sound lines and one broken one at the bottom
    would be a `doctor` whose single job -- telling somebody what is wrong --
    depends on them reading to the end.
    """
    missing = installation.missing
    if not missing:
        return []
    lines = ["Missing"]
    for one in missing:
        lines.extend(_wrap(f"{one.what}: {one.detail}", 76))
    return [*lines, ""]


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(f"{_INDENT}{current}")
            current = word
        else:
            current = candidate
    if current:
        lines.append(f"{_INDENT}{current}")
    return lines
