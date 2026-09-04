"""The report as one HTML file, for somebody who will sign it.

`akashi audit` prints for a reader at a terminal. This is the artefact that
leaves the machine: attached to a filing, forwarded to a reviewer, held for
however long the filing is held. Everything below follows from that one
difference.

**It reads the report and nothing else.** No package, no response, no re-audit
-- the same discipline as `explain`, and for the same reason: a report is a
document (ADR-0002), and a document that needs its inputs beside it to be read
is not one.

**It is a pure function of the report.** Two runs over the same report produce
the same bytes, so there is no timestamp, no host name and no ordering that
depends on a dictionary's insertion. A signature is over bytes; a certificate
that differed between runs would mean a signature over one copy did not verify
the other, and the difference would be in a field nobody looks at.

**No scripts, no network, no fonts.** One file, and opening it does not fetch
anything. A certificate that phoned a CDN would tell that CDN who was reading a
compliance artefact and when, and would render differently once the CDN was
gone -- for a document meant to outlive the machine that made it, both are
disqualifying. The style is inline, the fonts are whatever the reader has, and a
test asserts the absence rather than the intention.

**Standing is never carried by colour alone.** Underline shape and a mark
before the text carry it; colour is added on top. Printed in monochrome and read
by somebody who does not distinguish the hues, the page still says which
particulars are grounded.

**And it says what its holder cannot check** (#53). A span into the answer
points *inward*, at text printed on this page. A location points *outward*, at a
document the holder does not have, and asserts that a range of it contains a
given string. The first is checkable here; the second is akashi's word. The page
divides them rather than letting a signer assume that everything under one
heading has one status.
"""

from __future__ import annotations

from html import escape
from typing import Any

from akashi.domain.verdict import Verdict
from akashi.errors import ContractError

__all__ = ["certificate"]

#: Standing to (mark, css class). The mark is what survives monochrome
#: printing and a reader who does not separate the colours.
_MARKS = {
    "grounded": ("+", "grounded"),
    "floating": ("!", "floating"),
}

_STYLE = """
:root { color-scheme: light }
body { margin: 0 auto; padding: 2.5rem 1.5rem; max-width: 46rem;
       font-family: Georgia, 'Times New Roman', serif; line-height: 1.6;
       color: #1a1a1a; background: #fff }
h1 { font-size: 1.3rem; margin: 0 0 .2rem; letter-spacing: .02em }
h2 { font-size: 1rem; margin: 2.2rem 0 .6rem; padding-bottom: .25rem;
     border-bottom: 1px solid #d8d8d8; letter-spacing: .04em;
     text-transform: uppercase; font-weight: 600 }
p, li { margin: .4rem 0 }
.sub { color: #555; font-size: .85rem; margin: 0 0 1.6rem }
.mono { font-family: 'DejaVu Sans Mono', Consolas, monospace; font-size: .8rem;
        word-break: break-all }
.answer { padding: 1rem 1.2rem; border-left: 3px solid #d8d8d8;
          background: #fafafa; white-space: pre-wrap }
mark { background: none; padding: 0 }
mark.grounded { border-bottom: 2px solid #2f6f4f }
mark.floating { border-bottom: 2px dotted #a33; }
.mk { font-size: .7em; vertical-align: super; font-family: monospace;
      padding-right: .1em }
.mk.grounded { color: #2f6f4f }
.mk.floating { color: #a33 }
table { border-collapse: collapse; width: 100%; font-size: .85rem;
        margin: .6rem 0 }
th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #e6e6e6;
         vertical-align: top }
th { font-weight: 600; color: #444; white-space: nowrap }
td.where { font-family: 'DejaVu Sans Mono', Consolas, monospace; font-size: .78rem }
.note { border: 1px solid #d8d8d8; padding: .8rem 1rem; margin: 1rem 0;
        background: #fcfcfa; font-size: .88rem }
.note b { display: block; margin-bottom: .3rem }
ul { padding-left: 1.2rem }
.empty { color: #555; font-style: italic }
""".strip()


def certificate(report: dict[str, Any]) -> str:
    """One self-contained HTML document from a report dictionary.

    Takes the plain data ``to_dict`` produces or ``read_report`` returns, not
    the domain objects: a reader of an archived report holds the bytes, and
    rebuilding the objects in order to render them would put an interpretation
    between the bytes and the page.
    """
    if not isinstance(report, dict) or "segments" not in report:
        raise ContractError(
            "a certificate is rendered from an audit report; this is "
            f"{type(report).__name__} with no 'segments'. Pass the JSON that "
            f"'akashi audit --json' wrote."
        )

    answer = report.get("answer", "")
    if not isinstance(answer, str):
        raise ContractError("the report's 'answer' is not text, so nothing can be marked in it")

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>akashi audit {escape(_short(report.get('report_id', '')))}</title>",
        f"<style>{_STYLE}</style>",
        "</head><body>",
        *_head(report),
        *_not_checked(report),
        *_answer(report, answer),
        *_traced(report),
        *_findings(report),
        *_coverage(report),
        *_provenance(report),
        *_limits(report),
        *_what_you_cannot_check(report),
        "</body></html>",
    ]
    return "\n".join(parts) + "\n"


# --- the sections, in the order a signer reads them --------------------------


def _head(report: dict[str, Any]) -> list[str]:
    return [
        "<h1>akashi &mdash; audit certificate</h1>",
        f'<p class="sub mono">{escape(str(report.get("contract", "")))}<br>'
        f"{escape(str(report.get('report_id', '')))}</p>",
    ]


def _not_checked(report: dict[str, Any]) -> list[str]:
    """First on the page, as in every other rendering (ADR-0005).

    A reader takes away the score whatever else is here, so what precedes the
    score is what bounds it. On a certificate that is not a stylistic
    preference: the signer is the person for whom a missed exclusion is
    expensive.
    """
    lines = ["<h2>Not checked</h2>"]
    unchecked = _list(report.get("unchecked"))
    coverage = _dict(report.get("coverage"))
    by_rule: dict[str, int] = {}
    for skip in unchecked:
        rule = str(_dict(skip).get("rule", ""))
        by_rule[rule] = by_rule.get(rule, 0) + 1

    items = [
        f"<li>{count} segment{'' if count == 1 else 's'}: {escape(rule)}</li>"
        for rule, count in sorted(by_rule.items())
    ]
    kinds = [str(kind) for kind in _list(coverage.get("kinds_not_extracted"))]
    if kinds:
        items.append(f"<li>no rule covers: {escape(', '.join(kinds))}</li>")
    if not items:
        lines.append('<p class="empty">Nothing; every segment was examined and bore something.</p>')
    else:
        lines.append("<ul>" + "".join(items) + "</ul>")
    return lines


def _answer(report: dict[str, Any], answer: str) -> list[str]:
    """The answer, with every particular marked where it stands.

    The whole reason the certificate exists rather than a printed text report:
    a reader sees which words were checked *in the sentence*, and how much of
    the page carries no mark at all.
    """
    marked = _mark(answer, _particulars(report))
    return [
        "<h2>The answer</h2>",
        f'<div class="answer">{marked}</div>',
        '<p class="sub"><span class="mk grounded">+</span> found in the text that was sent'
        ' &nbsp; <span class="mk floating">!</span> in none of it'
        " &nbsp; unmarked text bore nothing akashi checks.</p>",
    ]


def _traced(report: dict[str, Any]) -> list[str]:
    """Every grounded particular and where it was found.

    Promoted to the middle of the page because this is the part a signer is
    signing: the claim *this figure came from your document, at this offset*.
    The findings matter to whoever fixes the answer; this is what the artefact
    is for.
    """
    rows = []
    for segment, one in _walk(report):
        if one.get("standing") != "grounded":
            continue
        for location in _list(one.get("locations")):
            rows.append((segment, one, _dict(location)))

    lines = ["<h2>Traced</h2>"]
    if not rows:
        lines.append(
            '<p class="empty">Nothing in this answer resolved to the text that was sent.</p>'
        )
        return lines

    lines.append(
        "<table><tr><th>Segment</th><th>Particular</th><th>In the answer</th><th>Found in</th></tr>"
    )
    for segment, one, location in rows:
        lines.append(
            "<tr>"
            f"<td>{escape(str(segment.get('segment_id', '')))}</td>"
            f"<td>{escape(str(one.get('text', '')))}</td>"
            f'<td class="where">{_span(one.get("span"))}</td>'
            f'<td class="where">{_location(location)}</td>'
            "</tr>"
        )
    lines.append("</table>")
    return lines


def _findings(report: dict[str, Any]) -> list[str]:
    lines = ["<h2>Findings</h2>"]
    findings = [
        segment
        for segment in _list(report.get("segments"))
        if _verdict_is_finding(_dict(segment).get("verdict"))
    ]
    if not findings:
        lines.append('<p class="empty">None.</p>')
        return lines

    for raw in findings:
        segment = _dict(raw)
        lines.append(
            f"<p><b>{escape(str(segment.get('segment_id', '')))}</b> "
            f"&mdash; {escape(str(segment.get('verdict', '')))}</p>"
        )
        lines.append(f'<div class="answer">{escape(str(segment.get("text", "")))}</div>')
        rows = []
        for one in _list(segment.get("particulars")):
            one = _dict(one)
            contradiction = _dict(one.get("contradiction"))
            if contradiction:
                said = (
                    f"the source says <b>{escape(str(contradiction.get('found', '')))}</b> "
                    f"at {_location(contradiction)}"
                )
            elif one.get("standing") == "floating":
                said = "is in none of the text that was sent"
                # And what the text does say of this kind, near here. A reader
                # handed only the refusal has to go and read the evidence again;
                # akashi already read it. Worded so it cannot be taken for a
                # correction -- there is no similarity behind this list.
                near = [_dict(entry) for entry in _list(one.get("nearby_in_evidence"))]
                if near:
                    said += (
                        '<br><span class="where">the evidence carries, near here: '
                        + " &middot; ".join(
                            f"<b>{escape(str(entry.get('text', '')))}</b> at {_location(entry)}"
                            for entry in near
                        )
                        + " &mdash; listed, not proposed</span>"
                    )
            else:
                said = " &middot; ".join(
                    _location(_dict(location)) for location in _list(one.get("locations"))
                )
            rows.append(
                f"<tr><td>{escape(str(one.get('text', '')))}</td>"
                f'<td class="where">{_span(one.get("span"))}</td>'
                f"<td>{said}</td></tr>"
            )
        if rows:
            lines.append("<table>" + "".join(rows) + "</table>")
    return lines


def _coverage(report: dict[str, Any]) -> list[str]:
    coverage = _dict(report.get("coverage"))
    counts = _dict(_dict(report.get("counts")).get("particulars"))
    share = _dict(report.get("counts")).get("grounded_share")
    grounded = _int(counts.get("grounded"))
    floating = _int(counts.get("floating"))

    lines = ["<h2>Coverage</h2>", "<table>"]
    for label, value in [
        ("Segments", coverage.get("segments")),
        ("Bore something akashi checks", coverage.get("bearing")),
        ("Bore nothing", coverage.get("unbearing")),
        ("Not examined", coverage.get("unexamined")),
        ("Particulars checked", coverage.get("checked")),
    ]:
        lines.append(f"<tr><th>{label}</th><td>{escape(str(value))}</td></tr>")
    if share is None:
        # Not 0% and not 100%. An answer with nothing checkable has not scored,
        # and a percentage here would be read as though it had.
        scored = "nothing in this answer could be checked"
    else:
        scored = f"{grounded} of {grounded + floating} particulars grounded ({float(share):.0%})"
    lines.append(f"<tr><th>Grounded</th><td>{escape(scored)}</td></tr>")
    lines.append("</table>")
    return lines


def _provenance(report: dict[str, Any]) -> list[str]:
    provenance = _dict(report.get("provenance"))
    audited = _dict(report.get("audited"))
    lines = ["<h2>Provenance</h2>", "<table>"]

    def row(label: str, value: str) -> None:
        lines.append(f'<tr><th>{label}</th><td class="mono">{escape(value)}</td></tr>')

    row("Report", str(report.get("report_id", "")))
    if audited.get("package_id"):
        row("Package", str(audited["package_id"]))
    row("Answer", str(audited.get("response_hash", "")))
    if audited.get("akashi_version"):
        row("akashi", str(audited["akashi_version"]))
    if audited.get("packs"):
        row("Language packs", ", ".join(str(pack) for pack in _list(audited.get("packs"))))
    if provenance.get("protection_by"):
        row("Protected by", str(provenance["protection_by"]))
    if provenance.get("restored_by"):
        # ADR-0013. A restoration akashi watched and one it was told about are
        # different claims, and a certificate that printed one wording for both
        # would be the single place that difference must not be lost.
        asserted = bool(provenance.get("restoration_asserted"))
        who = str(provenance["restored_by"])
        row(
            "Restored by",
            f"asserted {who}; akashi did not verify it" if asserted else who,
        )
    lines.append("</table>")

    withheld = _list(provenance.get("withheld"))
    if withheld:
        listed = ", ".join(
            f"{_int(_dict(entry).get('count'))} {_dict(entry).get('rule')}" for entry in withheld
        )
        lines.append(
            f'<div class="note"><b>The package withheld {escape(listed)}.</b>'
            " akashi cannot check an answer against text that was not sent, and this"
            " does not explain any finding above (ADR-0012).</div>"
        )

    unrecognised = [str(path) for path in _list(provenance.get("unrecognised"))]
    if unrecognised:
        lines.append(
            '<div class="note"><b>The package carried fields its contract does not list:'
            f" {escape(', '.join(unrecognised))}.</b>"
            " Version 1 of that contract is closed, so the package does not conform to it."
            " akashi read past them and audited the rest (ADR-0016).</div>"
        )
    return lines


def _limits(report: dict[str, Any]) -> list[str]:
    limits = [str(limit) for limit in _list(report.get("limits"))]
    if not limits:
        return []
    return [
        "<h2>What this does not establish</h2>",
        "<ul>" + "".join(f"<li>{escape(limit)}</li>" for limit in limits) + "</ul>",
    ]


def _what_you_cannot_check(report: dict[str, Any]) -> list[str]:
    """#53, on the artefact designed to circulate without the package.

    The split is by whether the holder can check the claim, and the two kinds
    of offset on this page fall on opposite sides of it. Saying so is cheap;
    letting a signer assume one status for both is what this section exists to
    prevent.
    """
    outward = any(
        one.get("locations") or one.get("contradiction") for _segment, one in _walk(report)
    )
    lines = [
        "<h2>What this page lets you check</h2>",
        "<p>Offsets into the answer point at text printed above. You can check those"
        " here: count the characters, or find the marked words in the sentence.</p>",
    ]
    if outward:
        lines.append(
            "<p><b>Offsets into a source document you cannot.</b> akashi read those"
            " documents; you are reading what it wrote down. Every entry under"
            " <i>Found in</i> asserts that a range of a file you do not have contains"
            " a given string, and nothing on this page can confirm or contradict it."
            " Opening the document is what turns that assertion into something you"
            " have seen.</p>"
        )
    lines.append(
        "<p>akashi compared strings. It did not decide whether the answer is true,"
        " whether the documents are, or whether the right documents were sent.</p>"
    )
    return lines


# --- marking the answer ------------------------------------------------------


def _mark(answer: str, particulars: list[dict[str, Any]]) -> str:
    """The answer with each particular wrapped where it stands.

    Overlapping spans are dropped rather than nested. A `<mark>` inside a
    `<mark>` renders as one underline of an unclear extent, which would make
    the page say something neither akashi nor the reader can pin down -- and a
    dropped mark is visible as an unmarked figure, where a wrong one is not.
    """
    spans: list[tuple[int, int, str]] = []
    for one in particulars:
        span = one.get("span")
        if not (isinstance(span, list) and len(span) == 2):
            continue
        start, end = span
        if not (isinstance(start, int) and isinstance(end, int)):
            continue
        if not 0 <= start < end <= len(answer):
            continue
        standing = str(one.get("standing", ""))
        if standing in _MARKS:
            spans.append((start, end, standing))

    out: list[str] = []
    cursor = 0
    for start, end, standing in sorted(spans):
        if start < cursor:
            continue
        mark, css = _MARKS[standing]
        out.append(escape(answer[cursor:start]))
        out.append(f'<span class="mk {css}">{mark}</span>')
        out.append(f'<mark class="{css}">{escape(answer[start:end])}</mark>')
        cursor = end
    out.append(escape(answer[cursor:]))
    return "".join(out)


# --- reading the report defensively ------------------------------------------


def _walk(report: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (segment, _dict(one))
        for raw in _list(report.get("segments"))
        for segment in [_dict(raw)]
        for one in _list(segment.get("particulars"))
    ]


def _particulars(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [one for _segment, one in _walk(report)]


def _location(entry: dict[str, Any]) -> str:
    where = str(entry.get("source_path") or entry.get("document_id") or entry.get("item_id") or "")
    section = entry.get("section")
    if section:
        where = f"{where} ({section})"
    span = entry.get("span")
    return escape(where) + _span(span)


def _span(value: Any) -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"[{value[0]}:{value[1]}]"
    return "[?]"


def _verdict_is_finding(value: Any) -> bool:
    try:
        return Verdict(str(value)).is_finding
    except ValueError:
        # A verdict from a newer akashi. Not a finding here, and not an error:
        # this renderer reads a document, and a document may outlive the reader.
        return False


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _short(value: str) -> str:
    return value.split(":")[-1][:12] if value else "report"
