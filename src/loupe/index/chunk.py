"""Section-aware chunking with exact character offsets.

Chunks never cross a section boundary (Item 1A text never mixes with Item 7), break
on paragraph, line or sentence boundaries where possible, and keep start/end offsets
into the document text so every citation can be checked against the source.
"""

from loupe.core.schemas import Chunk, Document

SEPARATORS = ("\n\n", "\n", ". ", " ")
MIN_CHARS = 40  # drop fragments such as lone page numbers


def _cut(text: str, start: int, end: int, size: int) -> int:
    """End offset of the next chunk: the last good separator in the second half of the window."""
    hard = min(start + size, end)
    if hard == end:
        return end
    floor = start + size // 2
    for sep in SEPARATORS:
        pos = text.rfind(sep, floor, hard)
        if pos != -1:
            return pos + len(sep)
    return hard


def split_region(text: str, start: int, end: int, size: int, overlap: int) -> list[tuple[int, int]]:
    spans = []
    pos = start
    while pos < end:
        cut = _cut(text, pos, end, size)
        s, e = pos, cut
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e - s >= MIN_CHARS:
            spans.append((s, e))
        if cut >= end:
            break
        nxt = max(cut - overlap, pos + 1)
        # start the overlap at a word boundary, never inside a word
        space = text.find(" ", nxt, cut)
        pos = space + 1 if space != -1 else cut
    return spans


def chunk_document(doc: Document, text: str, size: int = 1200, overlap: int = 150) -> list[Chunk]:
    # regions: cover page before the first section, then each distinct section range
    # (8-K aliases share a range; the chunk carries every item for that range)
    ranges: dict[tuple[int, int], list[str]] = {}
    for s in sorted(doc.sections, key=lambda s: s.start_char):
        ranges.setdefault((s.start_char, s.end_char), []).append(s.item or s.title)
    first = min((r[0] for r in ranges), default=len(text))
    regions = ([((0, first), [])] if first > 0 else []) + sorted(ranges.items())
    if not ranges:
        regions = [((0, len(text)), [doc.form])]

    chunks = []
    for (start, end), items in regions:
        for s, e in split_region(text, start, end, size, overlap):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}:{s}",
                    doc_id=doc.doc_id,
                    company_id=doc.company_id,
                    text=text[s:e],
                    start_char=s,
                    end_char=e,
                    section_id=f"{doc.doc_id}#{items[0]}" if items else None,
                    metadata={
                        "form": doc.form,
                        "items": items,
                        "accession": doc.accession,
                        "period_end": doc.period_end.isoformat() if doc.period_end else None,
                        "url": doc.url,
                    },
                )
            )
    return chunks


def context_header(chunk: Chunk) -> str:
    """Short header prepended before embedding (not stored): who, what filing, which section."""
    m = chunk.metadata
    items = ", ".join(m.get("items") or []) or "cover"
    return f"{chunk.company_id} {m.get('form')} period {m.get('period_end') or '?'}, item {items}\n"
