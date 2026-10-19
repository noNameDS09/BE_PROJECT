"""Bring-your-own-docs mode: index the documents a benchmark ships with (e.g. FinanceBench PDFs).

Each PDF page is chunked separately so every chunk knows its page number, which is what
FinanceBench's gold evidence refers to. The result is an ordinary index variant
(data/processed/index/docs-<dataset>/), searched with a doc_id filter per question.
"""

from collections.abc import Callable, Iterable
from pathlib import Path

from loupe.core.schemas import Chunk
from loupe.eval.schema import EvalItem
from loupe.index.chunk import split_region
from loupe.index.embed import Embedder
from loupe.index.search import build_index


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


def build_docs_index(
    items: Iterable[EvalItem],
    data_dir: Path,
    out: Path,
    embedder: Embedder,
    size: int = 1200,
    overlap: int = 150,
    progress: Callable[[str], None] = lambda _: None,
) -> int:
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
        elif path and path.lower().endswith(".pdf"):
            pages = pdf_pages(data_dir / path)
        elif path:
            pages = [(data_dir / path).read_text(errors="replace")]
        else:
            continue
        chunks += chunk_pages(doc_id, str(company), pages, size, overlap)
    build_index(chunks, out, embedder, progress=progress)
    return len(chunks)
