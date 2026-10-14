"""Split filing text into its standard sections (10-K / 10-Q Items, 8-K Items).

Headings like "Item 7. Management's Discussion..." also appear in the table of
contents. TOC rows are recognised (a trailing page number) and dropped; if an item
still appears more than once, the longest body wins. Some filers drop the word
"Item" from body headings, so key sections fall back to their standard titles.
"""

import itertools
import re
from dataclasses import dataclass

DASHES = "\u2013\u2014"
SEP = r"[ \t]*[.:\-" + DASHES + r"]?[ \t]*"  # "Item 7." / "Item 7 -" / en/em dash
# Lookaheads instead of \b: filers write "Item 2.02Results" with no space.
PERIODIC_NUMBER = r"((?:1[abc]|7a|9[abc])(?-i:(?![a-z0-9]))|(?:1[0-6]|[1-9])(?![0-9]))"
PERIODIC_ITEM = re.compile(
    r"^[ \t]*item\s*" + PERIODIC_NUMBER + SEP + r"([^\n]{0,120})", re.I | re.M
)
EIGHT_K_ITEM = re.compile(
    r"^[ \t]*item\s*(\d{1,2}\.\d{2})(?![0-9])" + SEP + r"([^\n]{0,160})", re.I | re.M
)
EIGHT_K_CODE = re.compile(r"item\s*(\d{1,2}\.\d{2})(?![0-9])", re.I)
PART = re.compile(r"^[ \t]*part\s+(ii|i)(?![a-z])([^\n]{0,120})", re.I | re.M)
# TOC rows end in a page number: "Item 7. | MD&A | 23" or "Item 7. MD&A 23"
TOC_TITLE = re.compile(r"[|\s]\s*\d{1,3}\s*$")

MDA = r"management['" + "\u2019" + r"]?s\s+discussion\s+and\s+analysis"
FALLBACK_TITLES = {
    "10-K": {
        "1A": r"risk\s+factors",
        "7": MDA,
        "8": r"financial\s+statements\s+and\s+supplementa(?:l|ry)\s+data",
    },
    "10-Q": {
        "I-1": r"(?:condensed\s+)?(?:consolidated\s+)?financial\s+statements",
        "I-2": MDA,
    },
}


def _is_toc(title: str) -> bool:
    return bool(TOC_TITLE.search(title))


@dataclass
class Span:
    item: str  # "7", "1A", "II-1A", "2.02"
    title: str
    start: int
    end: int


def _fallback(text: str, form: str, have: set[str]) -> list[tuple[str, str, int]]:
    """Heading lines that are just a standard section title, for items not found by number."""
    found = []
    for item, title in FALLBACK_TITLES.get(form, {}).items():
        if item in have:
            continue
        pattern = re.compile(r"^[ \t]*(" + title + r"[^\n]{0,100})$", re.I | re.M)
        found += [(item, m.group(1), m.start()) for m in pattern.finditer(text)]
    return found


def _spans(text: str, matches: list[tuple[str, str, int]]) -> list[Span]:
    """Turn heading matches into spans, dropping TOC rows and keeping the longest per item."""
    matches = sorted((m for m in matches if not _is_toc(m[1])), key=lambda m: m[2])
    raw = []
    for i, (item, title, start) in enumerate(matches):
        end = matches[i + 1][2] if i + 1 < len(matches) else len(text)
        raw.append(Span(item, title.strip(), start, end))
    best: dict[str, Span] = {}
    for span in raw:
        if span.item not in best or (span.end - span.start) > (
            best[span.item].end - best[span.item].start
        ):
            best[span.item] = span
    ordered = sorted(best.values(), key=lambda s: s.start)
    # re-close each span at the next kept heading so sections never overlap
    for a, b in itertools.pairwise(ordered):
        a.end = b.start
    if ordered:
        ordered[-1].end = len(text)
    return ordered


def _with_fallback(text: str, form: str, matches: list[tuple[str, str, int]]) -> list[Span]:
    have = {m[0] for m in matches if not _is_toc(m[1])}
    return _spans(text, matches + _fallback(text, form, have))


def split_10k(text: str) -> list[Span]:
    matches = [(m.group(1).upper(), m.group(2), m.start()) for m in PERIODIC_ITEM.finditer(text)]
    return _with_fallback(text, "10-K", matches)


def split_10q(text: str) -> list[Span]:
    # Part II follows Part I, and the table of contents repeats both headings, so the
    # last "Part II" heading is the boundary: items before it are Part I.
    part_two = [
        m.start()
        for m in PART.finditer(text)
        if m.group(1).upper() == "II" and not _is_toc(m.group(2))
    ]
    boundary = part_two[-1] if part_two else len(text)
    matches = [
        (f"{'II' if m.start() > boundary else 'I'}-{m.group(1).upper()}", m.group(2), m.start())
        for m in PERIODIC_ITEM.finditer(text)
    ]
    return _with_fallback(text, "10-Q", matches)


def split_8k(text: str) -> list[Span]:
    matches = [(m.group(1), m.group(2), m.start()) for m in EIGHT_K_ITEM.finditer(text)]
    spans = _spans(text, matches)
    # "Item 2.02 ... and Item 7.01 ..." in one heading: both items share the section
    have = {s.item for s in spans}
    for span in list(spans):
        for code in EIGHT_K_CODE.findall(span.title):
            if code not in have:
                spans.append(Span(code, span.title, span.start, span.end))
                have.add(code)
    return sorted(spans, key=lambda s: (s.start, s.item))


def split(form: str, text: str) -> list[Span]:
    if form == "10-K":
        return split_10k(text)
    if form == "10-Q":
        return split_10q(text)
    if form == "8-K":
        return split_8k(text)
    return [Span(form, form, 0, len(text))]
