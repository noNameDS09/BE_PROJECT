"""SEC filing HTML -> clean plain text that keeps paragraphs and table rows.

Inline-XBRL filings carry a hidden header block (ix:header, display:none) with
machine data; it is dropped. Tables become one line per row with cells joined by
" | " so numbers stay next to their labels for retrieval and quote checking.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

BLOCK_TAGS = {
    "p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "section", "article", "ul", "ol", "center", "pre", "hr",
}  # fmt: skip
DROP_TAGS = {"script", "style", "head", "title", "ix:header", "noscript"}
HIDDEN = re.compile(r"display\s*:\s*none", re.I)


def _cell_text(cell: Tag) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


def _table_lines(table: Tag) -> list[str]:
    lines = []
    for row in table.find_all("tr"):
        cells = [_cell_text(c) for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c and c not in {"$", "%", ")"}]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def html_to_text(html: str | bytes) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(list(DROP_TAGS)):
        tag.decompose()
    for tag in soup.find_all(style=HIDDEN):
        tag.decompose()

    parts: list[str] = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                if child.name == "table":
                    parts.append("\n" + "\n".join(_table_lines(child)) + "\n")
                    continue
                block = child.name in BLOCK_TAGS
                if block:
                    parts.append("\n")
                walk(child)
                if block:
                    parts.append("\n")

    walk(soup.body or soup)
    text = "".join(parts).replace("\xa0", " ").replace("​", "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out, blank = [], False
    for line in lines:
        if line:
            out.append(line)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip() + "\n"
