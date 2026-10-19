"""Hybrid retrieval over the chunk index: exact dense search + BM25, fused with RRF.

Search is exact (no approximate nearest neighbours): at ~10^5 chunks a filtered dot
product takes milliseconds, and exact search keeps retrieval results reproducible.
Filters (company, form, item, period) are applied before ranking.
"""

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal

import bm25s
import numpy as np
from pydantic import BaseModel

from loupe.core.jsonl import jsonl_lines
from loupe.core.schemas import Chunk
from loupe.index.chunk import context_header
from loupe.index.embed import Embedder

Mode = Literal["hybrid", "dense", "bm25"]
RRF_K = 60


class SearchFilter(BaseModel):
    doc_ids: list[str] | None = None
    companies: list[str] | None = None
    forms: list[str] | None = None
    items: list[str] | None = None
    period_from: date | None = None
    period_to: date | None = None


class Hit(BaseModel):
    chunk: Chunk
    score: float
    dense_rank: int | None = None
    bm25_rank: int | None = None


def tokenize(texts: list[str]):
    return bm25s.tokenize(texts, stopwords="en", show_progress=False)


def build_index(
    chunks: list[Chunk],
    out: Path,
    embedder: Embedder,
    batch: int = 512,
    progress: Callable[[str], None] = lambda _: None,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "chunks.jsonl").open("w") as f:
        for c in chunks:
            f.write(c.model_dump_json() + "\n")
    texts = [context_header(c) + c.text for c in chunks]
    vectors = []
    for i in range(0, len(texts), batch):
        progress(f"embedding {i:,}/{len(texts):,}")
        vectors.append(embedder.passages(texts[i : i + batch]))
    np.save(
        out / "dense.npy", np.concatenate(vectors) if vectors else np.zeros((0, 384), np.float32)
    )
    progress("building BM25")
    bm25 = bm25s.BM25()
    bm25.index(tokenize(texts), show_progress=False)
    bm25.save(str(out / "bm25"))
    (out / "INFO.json").write_text(
        json.dumps({"chunks": len(chunks), "embedder": embedder.name, "context_header": True})
    )


class SearchIndex:
    def __init__(
        self, chunks: list[Chunk], dense: np.ndarray, bm25: bm25s.BM25, embedder: Embedder
    ):
        self.chunks = chunks
        self.dense = dense
        self.bm25 = bm25
        self.embedder = embedder
        self._company = np.array([c.company_id for c in chunks])
        self._doc = np.array([c.doc_id for c in chunks])
        self._form = np.array([c.metadata.get("form") for c in chunks])
        self._period = np.array([c.metadata.get("period_end") or "" for c in chunks], dtype=object)
        self._items = [set(c.metadata.get("items") or []) for c in chunks]

    @classmethod
    def load(cls, path: Path, embedder: Embedder) -> "SearchIndex":
        chunks = [Chunk.model_validate_json(x) for x in jsonl_lines(path / "chunks.jsonl")]
        dense = np.load(path / "dense.npy")
        bm25 = bm25s.BM25.load(str(path / "bm25"))
        return cls(chunks, dense, bm25, embedder)

    def _mask(self, f: SearchFilter | None) -> np.ndarray:
        mask = np.ones(len(self.chunks), dtype=bool)
        if not f:
            return mask
        if f.doc_ids:
            mask &= np.isin(self._doc, f.doc_ids)
        if f.companies:
            mask &= np.isin(self._company, f.companies)
        if f.forms:
            mask &= np.isin(self._form, f.forms)
        if f.items:
            wanted = set(f.items)
            mask &= np.array([bool(s & wanted) for s in self._items])
        if f.period_from:
            mask &= np.array([p >= f.period_from.isoformat() for p in self._period])
        if f.period_to:
            mask &= np.array([bool(p) and p <= f.period_to.isoformat() for p in self._period])
        return mask

    def search(
        self, query: str, k: int = 10, filter: SearchFilter | None = None, mode: Mode = "hybrid"
    ) -> list[Hit]:
        mask = self._mask(filter)
        candidates = np.flatnonzero(mask)
        if candidates.size == 0:
            return []
        dense_rank = bm25_rank = None
        if mode in ("hybrid", "dense"):
            scores = self.dense[candidates] @ self.embedder.query(query)
            dense_rank = candidates[np.argsort(-scores)]
        if mode in ("hybrid", "bm25"):
            scores = self.bm25.get_scores(_query_tokens(query))[candidates]
            order = np.argsort(-scores)
            bm25_rank = candidates[order[scores[order] > 0]]
        fused: dict[int, float] = {}
        ranks: dict[int, dict[str, int]] = {}
        for name, ranking in (("dense", dense_rank), ("bm25", bm25_rank)):
            if ranking is None:
                continue
            for r, idx in enumerate(ranking[: max(k * 10, 100)]):
                fused[int(idx)] = fused.get(int(idx), 0.0) + 1.0 / (RRF_K + r + 1)
                ranks.setdefault(int(idx), {})[name] = r + 1
        top = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [
            Hit(
                chunk=self.chunks[i],
                score=s,
                dense_rank=ranks[i].get("dense"),
                bm25_rank=ranks[i].get("bm25"),
            )
            for i, s in top
        ]


def _query_tokens(query: str) -> list[str]:
    """Query terms as strings (same tokenizer as the index), for BM25 scoring."""
    tokens = tokenize([query])
    inverse = {v: k for k, v in tokens.vocab.items()}
    return [inverse[t] for t in tokens.ids[0]]
