"""Retrieval pipeline: (rewritten) queries -> hybrid candidates -> optional cross-encoder rerank.

Each stage is a switch in RetrievalConfig, so the stage ablations (RQ4) change one
setting at a time: dense vs BM25 vs hybrid, reranker on/off, query rewriting on/off,
candidate pool size and final k.
"""

from typing import Literal, Protocol

import numpy as np
from pydantic import BaseModel

from loupe.index.search import RRF_K, Hit, Mode, SearchFilter, SearchIndex

RERANKERS = {
    "minilm-l12": "Xenova/ms-marco-MiniLM-L-12-v2",  # 0.12 GB, default
    "minilm-l6": "Xenova/ms-marco-MiniLM-L-6-v2",
    "bge-base": "BAAI/bge-reranker-base",  # 1 GB, stronger, slower
}


class RetrievalConfig(BaseModel):
    mode: Mode = "hybrid"
    k: int = 8  # passages returned to the model
    candidates: int = 40  # pool size before reranking
    rerank: str | None = "minilm-l12"  # None = no reranker
    query_rewrite: Literal["none", "multi"] = "none"  # multi = LLM writes 3 alternative queries


class Reranker(Protocol):
    def scores(self, query: str, passages: list[str]) -> np.ndarray: ...


class CrossEncoder:
    """Local ONNX cross-encoder: scores (query, passage) pairs jointly."""

    def __init__(self, name: str = "minilm-l12"):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.name = name
        self._model = TextCrossEncoder(RERANKERS[name])

    def scores(self, query: str, passages: list[str]) -> np.ndarray:
        return np.array(list(self._model.rerank(query, passages)), dtype=np.float32)


class Retriever:
    def __init__(
        self, index: SearchIndex, config: RetrievalConfig, reranker: Reranker | None = None
    ):
        self.index = index
        self.config = config
        self.reranker = reranker if config.rerank else None

    def retrieve(
        self, query: str, filter: SearchFilter | None = None, extra_queries: list[str] | None = None
    ) -> list[Hit]:
        cfg = self.config
        queries = [query, *(extra_queries or [])]
        # fuse the candidate lists of all query variants by reciprocal rank
        fused: dict[str, float] = {}
        by_id: dict[str, Hit] = {}
        for q in queries:
            for rank, hit in enumerate(
                self.index.search(q, k=cfg.candidates, filter=filter, mode=cfg.mode)
            ):
                cid = hit.chunk.chunk_id
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
                by_id.setdefault(cid, hit)
        pool = [by_id[c] for c, _ in sorted(fused.items(), key=lambda kv: -kv[1])][: cfg.candidates]
        if not pool:
            return []
        if self.reranker is None:
            return [h.model_copy(update={"score": fused[h.chunk.chunk_id]}) for h in pool[: cfg.k]]
        scores = self.reranker.scores(query, [h.chunk.text for h in pool])
        order = np.argsort(-scores)[: cfg.k]
        return [pool[i].model_copy(update={"score": float(scores[i])}) for i in order]
