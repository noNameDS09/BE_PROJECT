"""Section-aware chunking.

Filing text is split inside a section, never across a section boundary, so a
chunk always has one item number and a stable citation. Chunks keep the
section's exact text region, because the verifier resolves quotes against the
stored text (see docs/decisions.md).
"""

from collections.abc import Iterable

from loupe.core.schemas import Chunk, Section

DEFAULT_SIZE = 1200
DEFAULT_OVERLAP = 200
# Paragraph, then line, then word, then character: the same order as
# LangChain's RecursiveCharacterTextSplitter, which splits at the most
# meaningful boundary available inside the window.
SEPARATORS = ("\n\n", "\n", " ", "")


def split_text(
    text: str, size: int = DEFAULT_SIZE, overlap: int = DEFAULT_OVERLAP
) -> list[tuple[int, int]]:
    """Character spans of at most `size`, with `overlap` chars of context."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    spans: list[tuple[int, int]] = []
    start = 0
    length = len(text)
    if length == 0:
        return spans

    while start < length:
        end = min(start + size, length)
        if end < length:
            window = text[start:end]
            cut = -1
            for sep in SEPARATORS:
                if sep and sep in window:
                    # Prefer a boundary in the back half so chunks stay near size.
                    idx = window.rfind(sep, size // 2)
                    if idx != -1:
                        cut = start + idx + len(sep)
                        break
            if cut != -1 and cut > start:
                end = cut
        spans.append((start, end))
        if end == length:
            break
        start = max(start + 1, end - overlap)
    return spans


def chunk_document(
    doc: object,
    sections: Iterable[Section],
    texts: dict[str, str],
    *,
    company_id: str,
    size: int = DEFAULT_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    min_chars: int = 80,
) -> list[Chunk]:
    """Chunk a document section by section.

    `doc` is anything carrying doc_id/form/accession (a Document);
    `sections` are its Section records; `texts` maps section_id to the exact
    text of that section, which is what quotes are verified against.
    """
    chunks: list[Chunk] = []
    for section in sections:
        text = texts.get(section.section_id, "")
        for index, (start, end) in enumerate(split_text(text, size, overlap)):
            piece = text[start:end]
            if len(piece.strip()) < min_chars:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{section.section_id}:{index:03d}",
                    doc_id=doc.doc_id,
                    company_id=company_id,
                    text=piece,
                    start_char=start,
                    end_char=end,
                    section_id=section.section_id,
                    metadata={
                        "title": section.title,
                        "item": section.item,
                        "part": section.part,
                        "form": getattr(doc, "form", None),
                        "accession": getattr(doc, "accession", None),
                        "period_end": (
                            doc.period_end.isoformat() if getattr(doc, "period_end", None) else None
                        ),
                        "fiscal_year": getattr(doc, "fiscal_year", None),
                        "fiscal_period": getattr(doc, "fiscal_period", None),
                        "chunk_index": index,
                    },
                )
            )
    return chunks


def dedupe_chunks(chunks: Iterable[Chunk]) -> list[Chunk]:
    seen: set[str] = set()
    out: list[Chunk] = []
    for chunk in chunks:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        out.append(chunk)
    return out
