"""Bring-your-own-docs mode: index the documents a benchmark ships with (e.g. FinanceBench PDFs).

Each PDF page is chunked separately so every chunk knows its page number, which is what
FinanceBench's gold evidence refers to. The result is an ordinary index variant
(data/processed/index/docs-<dataset>/), searched with a doc_id filter per question.
"""

import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path

from loupe.core.schemas import Chunk
from loupe.eval.schema import EvalItem
from loupe.index.chunk import split_region
from loupe.index.embed import Embedder
from loupe.index.search import build_index
from loupe.ingest.html_text import html_to_text


def pdf_pages(path: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(path) as doc:
        return [page.get_text("text") for page in doc]


def chunk_pages(
    doc_id: str, company_id: str, pages: list[str], size: int, overlap: int
) -> list[Chunk]:
    chunks = []
    for page_no, text in enumerate(pages):
        for s, e in split_region(text, 0, len(text), size, overlap):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}:p{page_no}:{s}",
                    doc_id=doc_id,
                    company_id=company_id,
                    text=text[s:e],
                    start_char=s,
                    end_char=e,
                    page=page_no,
                    metadata={
                        "form": "document",
                        "items": [f"p{page_no}"],
                        "period_end": None,
                        "url": None,
                    },
                )
            )
    return chunks


def read_document(data_dir: Path, path: str) -> list[str]:
    """Pages of a benchmark document: PDFs per page; HTML/text as one page.

    `archive.zip#member` reads a member straight from a zip (FinDER's 10-Ks) without
    extracting it into the raw data folder."""
    if "#" in path:
        archive, member = path.split("#", 1)
        with zipfile.ZipFile(data_dir / archive) as zf:
            raw = zf.read(member)
    else:
        if path.lower().endswith(".pdf"):
            return pdf_pages(data_dir / path)
        raw = (data_dir / path).read_bytes()
    if path.lower().endswith((".htm", ".html")):
        return [html_to_text(raw)]
    return [raw.decode("utf-8", errors="replace")]


def collect_chunks(
    items: Iterable[EvalItem],
    data_dir: Path,
    size: int = 1200,
    overlap: int = 150,
    progress: Callable[[str], None] = lambda _: None,
) -> list[Chunk]:
    docs: dict[str, tuple[str, str | None, str | None]] = {}
    for item in items:
        company = item.companies[0] if item.companies else item.meta.get("company", "")
        for d in item.documents:
            docs.setdefault(d.doc_id, (company, d.path, d.text))
    chunks: list[Chunk] = []
    for n, (doc_id, (company, path, text)) in enumerate(sorted(docs.items()), 1):
        progress(f"reading {n}/{len(docs)} {doc_id}")
        if text is not None:
            pages = [text]
        elif path:
            pages = read_document(data_dir, path)
        else:
            continue
        chunks += chunk_pages(doc_id, str(company), pages, size, overlap)
    return chunks


def build_docs_index(
    items: Iterable[EvalItem],
    data_dir: Path,
    out: Path,
    embedder: Embedder,
    size: int = 1200,
    overlap: int = 150,
    progress: Callable[[str], None] = lambda _: None,
) -> int:
    chunks = collect_chunks(items, data_dir, size, overlap, progress)
    build_index(chunks, out, embedder, progress=progress)
    return len(chunks)
