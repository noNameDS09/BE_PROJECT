"""Hybrid retrieval over chunk text.

Two retrievers, one interface:

* BM25 (rank_bm25, already present as an edgartools dependency) for lexical
  precision on numbers, tickers and exact phrases.
* Optional dense vectors. Off by default in P1 because loading
  sentence-transformers pulls torch, and P1's "done when" only requires cited
  chunks. RQ4 turns it on.

`reciprocal_rank_fusion` combines them without needing score calibration,
which matters because BM25 and cosine scores are not comparable.
"""

import math
import re
import threading
from collections import defaultdict
from collections.abc import Iterable, Sequence

from loupe.core.schemas import Citation, SearchHit

TOKEN_RE = re.compile(r"[a-z0-9]+")
K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class BM25Index:
    """In-memory BM25 over a fixed chunk set."""

    def __init__(self, docs: Sequence[tuple[str, str]], k1: float = K1, b: float = B):
        self.k1 = k1
        self.b = b
        self.ids = [doc_id for doc_id, _ in docs]
        self.tokens = [tokenize(text) for _, text in docs]
        self.lengths = [len(t) for t in self.tokens]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0

        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for index, tokens in enumerate(self.tokens):
            for term, freq in _counts(tokens).items():
                self.postings[term].append((index, freq))
        self.n = len(self.tokens)

    def search(
        self, query: str, top_k: int, allowed: set[int] | None = None
    ) -> list[tuple[str, float]]:
        """Rank documents for a query. `allowed` restricts scoring to a subset
        of document indices, so filtering by company happens before ranking."""
        scores: dict[int, float] = defaultdict(float)
        for term in tokenize(query):
            postings = self.postings.get(term)
            if not postings:
                continue
            df = len(postings)
            # Robertson/Sparck-Jones idf, floored so a term in every document
            # cannot contribute a negative score.
            idf = max(math.log((self.n - df + 0.5) / (df + 0.5) + 1.0), 1e-6)
            for index, freq in postings:
                if allowed is not None and index not in allowed:
                    continue
                length = self.lengths[index] or 1
                denominator = freq + self.k1 * (1 - self.b + self.b * length / (self.avgdl or 1.0))
                scores[index] += idf * freq * (self.k1 + 1) / denominator
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [(self.ids[i], s) for i, s in ranked[:top_k]]


def _counts(tokens: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


class DenseIndex:
    """Optional embedding index. Requires sentence-transformers."""

    def __init__(self, ids: Sequence[str], model_name: str = "BAAI/bge-small-en-v1.5"):
        from sentence_transformers import SentenceTransformer

        self.ids = list(ids)
        self.name = model_name
        self.model = SentenceTransformer(model_name)
        self._lock = threading.Lock()

    def build(self, texts: Sequence[str], batch_size: int = 64) -> None:
        vectors = self.model.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        import numpy as np

        self.matrix = np.asarray(vectors, dtype="float32")

    def search(
        self, query: str, top_k: int, allowed: set[int] | None = None
    ) -> list[tuple[str, float]]:
        import numpy as np

        vector = np.asarray(
            self.model.encode([query], normalize_embeddings=True)[0], dtype="float32"
        )
        with self._lock:
            scores = self.matrix @ vector
            if allowed is not None:
                mask = np.full(len(self.ids), -np.inf, dtype="float32")
                mask[sorted(allowed)] = 0.0
                scores = scores + mask
            order = np.argsort(-scores)[:top_k]
        return [(self.ids[i], float(scores[i])) for i in order]


class HybridIndex:
    """BM25 + optional dense, fused by reciprocal rank fusion.

    rrf_constant 60 is the value from the original RRF paper and is large
    enough that top-k churn below ~30 positions does not change the order.
    """

    def __init__(
        self,
        docs: Sequence[tuple[str, str]],
        dense_model: str | None = None,
        companies: dict[str, str] | None = None,
        metadata: dict[str, dict] | None = None,
    ):
        self.texts: dict[str, str] = dict(docs)
        # chunk_id -> company, used to filter retrieval by company before
        # scoring, which is what docs/PLAN.md requires of every arm.
        self.companies: dict[str, str] = dict(companies or {})
        self.metadata: dict[str, dict] = dict(metadata or {})
        # A chunk_id is "<section_id>:<index>", so the document cannot be
        # recovered by splitting the id; it comes from the caller's metadata.
        self.doc_ids: dict[str, str] = {
            cid: meta["doc_id"] for cid, meta in self.metadata.items() if "doc_id" in meta
        }
        self.bm25 = BM25Index(docs)
        self.dense = DenseIndex(list(self.texts), dense_model) if dense_model else None
        if self.dense is not None:
            self.dense.build([text for _, text in docs])

    def search(
        self,
        query: str,
        top_k: int = 10,
        candidate_k: int | None = None,
        company_id: str | None = None,
    ) -> list[SearchHit]:
        candidate_k = candidate_k or max(top_k * 4, 40)
        allowed = None
        if company_id is not None:
            allowed = {
                i for i, cid in enumerate(self.bm25.ids) if self.companies.get(cid) == company_id
            }
            if not allowed:
                return []

        pools: list[list[tuple[str, float]]] = [
            self.bm25.search(query, candidate_k, allowed=allowed)
        ]
        if self.dense is not None:
            pools.append(self.dense.search(query, candidate_k, allowed=allowed))

        fused = _rrf(pools, k=60)
        hits: list[SearchHit] = []
        for chunk_id, score, components in fused:
            text = self.texts.get(chunk_id, "")
            hits.append(
                SearchHit(
                    chunk_id=chunk_id,
                    doc_id=self.doc_ids.get(chunk_id, ""),
                    company_id=self.companies.get(chunk_id, ""),
                    text=text,
                    score=score,
                    citation=Citation(
                        chunk_id=chunk_id,
                        quote=_snippet(text, query),
                        verified=False,
                    ),
                    scores=components,
                    metadata=self.metadata.get(chunk_id, {}),
                )
            )
            if len(hits) >= top_k:
                break
        return hits


def _rrf(
    pools: Sequence[Sequence[tuple[str, float]]], k: int = 60
) -> list[tuple[str, float, dict[str, float]]]:
    accumulated: dict[str, float] = defaultdict(float)
    components: dict[str, dict[str, float]] = defaultdict(dict)
    for name, pool in zip(("bm25", "dense"), pools, strict=False):
        for rank, (chunk_id, score) in enumerate(pool, start=1):
            accumulated[chunk_id] += 1.0 / (k + rank)
            components[chunk_id][name] = float(score)
    ranked = sorted(accumulated.items(), key=lambda kv: kv[1], reverse=True)
    return [(cid, score, components[cid]) for cid, score in ranked]


def _snippet(text: str, query: str, width: int = 320) -> str:
    """A window of text around the first query term, for the citation quote."""
    lowered = text.lower()
    position = -1
    for term in tokenize(query):
        position = lowered.find(term)
        if position != -1:
            break
    if position == -1:
        return text[:width]
    start = max(0, position - width // 3)
    return text[start : start + width]


def load_chunks(conn, dense_model: str | None = None) -> HybridIndex:
    """Build a HybridIndex from everything already ingested."""
    from loupe.store.db import iter_chunks

    chunks = list(iter_chunks(conn))
    rows = [(c["chunk_id"], c["text"]) for c in chunks]
    companies = {c["chunk_id"]: c["company_id"] for c in chunks}
    metadata = {
        c["chunk_id"]: {k: v for k, v in c.items() if k not in {"chunk_id", "text"}} for c in chunks
    }
    return HybridIndex(rows, dense_model=dense_model, companies=companies, metadata=metadata)
