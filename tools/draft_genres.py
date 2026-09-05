"""Draft corpus vocabulary with a local model, for a person to review.

    python tools/draft_genres.py --language en --count 4
    python tools/draft_genres.py --language ja --from-file drafts.json

Prints JSON to stdout. **Nothing here writes a fixture.** The output is read,
edited and committed by a person into `evaluation/genres/{en,ja,zh}.py`, and
`generate_cases.py` stays deterministic — CI calls no model and ADR-0003 is
untouched.

## Why a model is involved at all

Every genre in this corpus was written by whoever was writing the extractor at
the time, so the questions, the documents and — the part that matters — **the
way a quantity is spelled** all came from one head. `docs/measurements.md`
already records what that costs: the corpus cannot tell `normalized` from
`exact` because no answer in it ever re-spaces a quantity, and #42 could not be
measured at all because `2.4 kilogrammes` and `2.4 furlongs` look structurally
identical when the same person invented both.

Asking something else for the words is the cheap way to get vocabulary that was
not chosen with the implementation in mind. `tsumugi` did this and its trap rate
went from 6.0% to 25.8% with no change to its code.

## What the model is not trusted with

Correctness, and nothing here decides whether a plant is a plant. Every draft is
checked mechanically before a person sees it, and **a rejected draft is printed
with its reason rather than dropped**, because the reason is the measurement.

One of those checks is the point of the whole exercise: **akashi's own extractor
must find the drafted value in the drafted sentence.** A value another head
wrote that akashi cannot see is not a bad draft — it is a recall gap that this
corpus was structurally unable to contain, and it is counted separately from the
drafts that are merely malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from akashi.domain.extraction import extract_from_answer
from akashi.domain.segment import segment_answer
from akashi.infrastructure.languages import packs

#: What a genre contributes. Narrower than `GenreSpec` on purpose: a model
#: inventing document ids, source paths and plant kinds is a model inventing the
#: parts a person has to check hardest, for no gain. What is wanted here is
#: vocabulary — a subject, an attribute, and above all **a value written the way
#: that domain writes it**.
FIELDS = (
    "key",
    "language",
    "subject",
    "attribute",
    "value",
    "sentence",
    "neighbour",
    "superseded_value",
    "heading",
    "paraphrase",
)

DEFAULT_MODEL = "qwen2.5:14b-instruct"
DEFAULT_URL = "http://localhost:11434/api/generate"

_LANGUAGE_NAMES = {"en": "English", "ja": "Japanese", "zh": "Simplified Chinese"}

_PROMPT = """\
Invent {count} evaluation genres for a document-audit test corpus, in {language}.

A genre is one everyday subject somebody keeps records about, one factual
attribute of it, and the value of that attribute **written the way that field
actually writes it**. Vary the domains widely: shipping, pharmacy, allotments,
motorsport, tailoring, brewing, surveying, aviation maintenance, school
timetables, anything ordinary and specific.

The value is the important part. Use whatever unit and formatting that domain
really uses -- fractions, mixed units, ranges, abbreviations, a currency written
as that trade writes it. Do NOT default to plain metric decimals.

Return JSON and nothing else:

{{"genres": [{{
  "key": "kebab-case-identifier-in-english",
  "subject": "the thing, in {language}",
  "attribute": "a factual property of it, in {language}",
  "value": "the value of that property as that field writes it, in {language}",
  "sentence": "one sentence from a document stating that value, in {language},
               containing the value verbatim",
  "neighbour": "a DIFFERENT thing sharing the subject's vocabulary, in {language}",
  "superseded_value": "an older, different value of the same property, in {language}",
  "heading": "a short document heading, in {language}",
  "paraphrase": "how a person would ask for that attribute, WITHOUT using the attribute's own words"
}}]}}

Rules:
- Everything invented. No real people, companies, addresses or numbers.
- `sentence` must contain `value` character for character.
- `neighbour` must be a different subject, not a synonym of `subject`.
- `superseded_value` must differ from `value`.
- `paraphrase` must not contain `attribute`. If the attribute is "weight", ask
  "how heavy", not "what weight".
"""


def fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def malformed(genre: dict[str, Any]) -> list[str]:
    """Everything wrong with a draft, so a reader can judge it at a glance.

    Kept separate from `unextractable` below: a draft that contradicts itself is
    a bad draft, and a draft akashi cannot read is a finding about akashi.
    Counting them together would let one hide inside the other.
    """
    found: list[str] = []
    for field in FIELDS:
        if field == "language":
            continue
        value = genre.get(field)
        if not isinstance(value, str) or not value.strip():
            found.append(f"missing {field}")
    if found:
        return found

    if genre["value"] not in genre["sentence"]:
        found.append(f"sentence does not contain the value {genre['value']!r} verbatim")
    if fold(genre["neighbour"]) == fold(genre["subject"]):
        found.append("neighbour repeats subject")
    if fold(genre["superseded_value"]) == fold(genre["value"]):
        found.append("superseded_value repeats value")

    # The attribute must move, not the subject. tsumugi's first version of this
    # check measured the shared run against the whole question and rejected
    # every Chinese draft for keeping the subject -- which is what a paraphrase
    # does. A person asking about their tent still says "tent".
    attribute = fold(genre["attribute"])
    if attribute and attribute in fold(genre["paraphrase"]):
        found.append(f"paraphrase still uses the attribute {genre['attribute']!r}")
    return found


def unextractable(genre: dict[str, Any]) -> str:
    """Why akashi's extractor could not take the drafted value, or ``""``.

    **This is the measurement, not a quality gate.** A value that another head
    wrote and akashi cannot see is a recall gap the old corpus could not contain,
    because the old corpus only ever contained values akashi's own author wrote.

    Run through the real segmenter and the real extractor, at the real defaults,
    so that what is being tested is what ships.
    """
    chosen = packs(genre["language"])
    segmentation = segment_answer(genre["sentence"], chosen)
    found = extract_from_answer(segmentation, chosen)
    texts = [one.text for one in found]
    if genre["value"] in texts:
        return ""

    # A sub-span is not automatically a miss, and which kind it is turns on
    # what was LEFT BEHIND rather than on the digits.
    #
    #   `5.2%`   out of `5.2% ABV`     leftover " ABV"   -> a separate word, fine
    #   `20,000 m` out of `20,000 m3`  leftover "3"      -> glued on, and the unit
    #                                                       just became a length
    #   `1:45`   out of `1:45.32`      leftover ".32"    -> a different lap time
    #
    # Two earlier versions of this check were wrong. The first demanded exact
    # equality and called three correct extractions a miss. The second compared
    # digit strings, and `fold` is NFKC, which turns the superscript in `m3`
    # into a digit -- so it reported a real defect for a reason that was not
    # true. A check that reaches the right answer by the wrong route is one
    # input away from the wrong answer.
    for text in texts:
        if not text or text not in genre["value"]:
            continue
        at = genre["value"].index(text)
        after = genre["value"][at + len(text) :]
        before = genre["value"][:at]
        if _detached(before[-1:]) and _detached(after[:1]):
            return ""

    # A compound value is decomposed, not truncated: `2.4m x 1.2m` is two
    # particulars and akashi is right to report two.
    covering = [one for one in texts if one and one in genre["value"]]
    if covering and _decomposes(covering, genre["value"]):
        return ""
    if covering:
        # Which side the leftover is on says whose problem it is, and the
        # arithmetic is dishonest without the split. A leftover glued on the
        # RIGHT is akashi cutting a unit short -- `5.5%` out of `5.5%vol`. One
        # glued on the LEFT is the model having put a whole clause in a field
        # asked for a value -- `25毫克` out of `每次25毫克，每日三次`, where
        # akashi took the quantity correctly and the draft is what is wrong.
        at = genre["value"].index(covering[0])
        left_glued = not _detached(genre["value"][:at][-1:])
        right = genre["value"][at + len(covering[0]) :]
        if left_glued and _detached(right[:1]):
            return (
                f"DRAFT: the value {genre['value']!r} is a clause, not a value; akashi "
                f"took {covering} out of it, which is the quantity in it"
            )
        return (
            f"extracted {covering} from the value {genre['value']!r}; what is left of it "
            f"is attached to what came out, so the value changed rather than narrowed"
        )
    return f"extracted {texts or 'nothing'}; the value {genre['value']!r} is not among them"


def _detached(edge: str) -> bool:
    """Whether a boundary character means the neighbouring text is a separate word."""
    return edge == "" or edge.isspace() or edge in ",;:、，；"


def _decomposes(parts: list[str], value: str) -> bool:
    """Whether ``parts`` are the whole of ``value`` apart from separators."""
    remaining = value
    for part in parts:
        at = remaining.find(part)
        if at < 0:
            return False
        remaining = remaining[at + len(part) :]
    left = value
    for part in parts:
        left = left.replace(part, " ", 1)
    return not any(character.isalnum() for character in left)


def ask(prompt: str, model: str, url: str, timeout: float) -> str:
    """One generation from a local ollama, over the standard library.

    `urllib` rather than a client library: this is `tools/`, outside the package
    the no-network contract covers, and akashi's dependency count stays zero
    even for the things that are not shipped.
    """
    body = json.dumps(
        {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.9}}
    ).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - a localhost URL the caller passed
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return str(json.loads(response.read().decode("utf-8")).get("response", ""))


def parse(answer: str) -> list[dict[str, Any]]:
    text = answer.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"the model did not return JSON:\n{answer[:400]}")
    body = json.loads(text[start : end + 1])
    if not isinstance(body, dict):
        return []
    # `genres` is what the model returns; `drafts` is what this tool prints. The
    # output has to be readable back in, or a saved run cannot be re-checked
    # after the extractor changes -- which is the whole reason to keep it.
    genres = body.get("genres") or body.get("drafts") or []
    return [one for one in genres if isinstance(one, dict)]


def _say(line: str) -> None:
    """One diagnostic line, as UTF-8, whatever the console claims to be."""
    sys.stderr.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    sys.stderr.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=sorted(_LANGUAGE_NAMES))
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="read drafts from a JSON file instead of calling a model, so the checks "
        "can be re-run on a saved draft without spending a generation",
    )
    arguments = parser.parse_args()

    if arguments.from_file is not None:
        drafted = parse(arguments.from_file.read_text(encoding="utf-8"))
    else:
        prompt = _PROMPT.format(count=arguments.count, language=_LANGUAGE_NAMES[arguments.language])
        try:
            drafted = parse(ask(prompt, arguments.model, arguments.url, arguments.timeout))
        except (urllib.error.URLError, TimeoutError) as error:
            _say(f"no model answered at {arguments.url}: {error}")
            return 1
        except (ValueError, json.JSONDecodeError) as error:
            _say(f"{error}")
            return 1

    drafts: list[dict[str, Any]] = []
    counts = {"usable": 0, "malformed": 0, "missed": 0}
    for genre in drafted:
        genre.setdefault("language", arguments.language)
        genre.pop("verdict", None)
        genre.pop("why", None)
        problems = malformed(genre)
        if problems:
            counts["malformed"] += 1
            _say(f"# MALFORMED {genre.get('key')}: {'; '.join(problems)}")
            drafts.append(genre | {"verdict": "malformed", "why": problems})
            continue
        record = {field: genre[field] for field in FIELDS} | {
            "origin": "drafted",
            "drafter": arguments.model,
        }
        why = unextractable(genre)
        if why.startswith("DRAFT: "):
            counts["malformed"] += 1
            _say(f"# MALFORMED {genre['key']}: {why[7:]}")
            drafts.append(record | {"verdict": "malformed", "why": [why[7:]]})
            continue
        if why:
            counts["missed"] += 1
            _say(f"# akashi MISSED {genre['key']}: {why}")
            drafts.append(record | {"verdict": "missed", "why": [why]})
            continue
        counts["usable"] += 1
        drafts.append(record | {"verdict": "usable", "why": []})

    # Every draft is printed, including the rejected ones. A tool that printed
    # only what passed would throw away the finding and keep the material.
    # Written to the buffer as UTF-8 rather than through whatever the console
    # happens to be. akashi ships `akashi doctor` because a Windows console is
    # cp932 by default and dies on the first Chinese character -- and this tool
    # did exactly that on its first Chinese run, after the lesson was already
    # written down elsewhere in this repository.
    sys.stdout.buffer.write(
        (json.dumps({"drafts": drafts}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    sys.stdout.flush()
    total = len(drafted)
    _say(
        f"# {total} drafts: {counts['usable']} usable, {counts['malformed']} malformed, "
        f"{counts['missed']} that akashi could not extract"
    )
    well_formed = total - counts["malformed"]
    if well_formed:
        _say(
            f"# extraction miss rate on well-formed drafts: "
            f"{counts['missed'] / well_formed * 100:.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
