"""Split filing text into its standard sections (10-K / 10-Q Items, 8-K Items).

Headings like "Item 7. Management's Discussion..." also appear in the table of
contents. TOC rows are recognised (table cells, or a trailing page number) and
dropped; if an item still appears more than once, the longest body wins.
"""

import itertools
import re
from dataclasses import dataclass

SEP = r"[ \t]*[.:\-\u2013\u2014]?[ \t]*"  # "Item 7." / "Item 7 -" / "Item 7 \u2014"
PERIODIC_ITEM = re.compile(
    r"^[ \t]*item\s*(1a|1b|1c|1|2|3|4|5|6|7a|7|8|9a|9b|9c|9|10|11|12|13|14|15|16)\b"
    + SEP
    + r"([^\n]{0,120})",
    re.I | re.M,
)
EIGHT_K_ITEM = re.compile(
    r"^[ \t]*item\s*(\d{1,2}\.\d{2})\b" + SEP + r"([^\n]{0,160})", re.I | re.M
)
PART = re.compile(r"^[ \t]*part\s+(ii|i)\b(?!\w)", re.I | re.M)
# TOC rows end in a page number: "Item 7. | MD&A | 23" or "Item 7. MD&A 23"
TOC_TITLE = re.compile(r"[|\s]\s*\d{1,3}\s*$")


def _is_toc(title: str) -> bool:
    return bool(TOC_TITLE.search(title))


@dataclass
class Span:
    item: str  # "7", "1A", "II-1A", "2.02"
    title: str
    start: int
    end: int


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


def split_10k(text: str) -> list[Span]:
    matches = [(m.group(1).upper(), m.group(2), m.start()) for m in PERIODIC_ITEM.finditer(text)]
    return _spans(text, matches)


def split_10q(text: str) -> list[Span]:
    parts = [(m.start(), m.group(1).upper()) for m in PART.finditer(text)]
    matches = []
    for m in PERIODIC_ITEM.finditer(text):
        part = "I"
        for pos, name in parts:
            if pos <= m.start():
                part = name
        matches.append((f"{part}-{m.group(1).upper()}", m.group(2), m.start()))
    return _spans(text, matches)


def split_8k(text: str) -> list[Span]:
    matches = [(m.group(1), m.group(2), m.start()) for m in EIGHT_K_ITEM.finditer(text)]
    return _spans(text, matches)


def split(form: str, text: str) -> list[Span]:
    if form == "10-K":
        return split_10k(text)
    if form == "10-Q":
        return split_10q(text)
    if form == "8-K":
        return split_8k(text)
    return [Span(form, form, 0, len(text))]
