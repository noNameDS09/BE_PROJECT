"""Retrieval-only evaluation: does search find the gold evidence? No LLM involved.

For every item with gold evidence, the question is searched (restricted to the item's own
documents in docs mode, or to its companies in corpus mode) and each gold evidence item is
looked for among the ranked chunks. A chunk matches gold evidence when
  - it is on the gold page of the gold document (FinanceBench), or
  - it shares an 8-word passage with the gold evidence text (FinDER, FinanceBench), or
  - it comes from the gold filing (accession).
Reports recall@k for several k, MRR, and the share of items with no match at all, so
retrieval variants (RQ4) can be compared cheaply before any model is called.
"""

import re
from collections.abc import Callable, Iterable

from pydantic import BaseModel

from loupe.core.schemas import Chunk
from loupe.eval.schema import EvalItem, GoldEvidence
from loupe.index.retriever import Retriever
from loupe.index.search import SearchFilter

SHINGLE = 8


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _shingles(text: str) -> set[tuple[str, ...]]:
    w = _words(text)
    return {tuple(w[i : i + SHINGLE]) for i in range(max(0, len(w) - SHINGLE + 1))}


def matches(chunk: Chunk, gold: GoldEvidence, gold_shingles: set | None = None) -> bool:
    same_doc = gold.doc_id is None or chunk.doc_id == gold.doc_id
    if gold.page is not None and same_doc and chunk.page == gold.page:
        return True
    if gold.text and same_doc:
        shingles = gold_shingles if gold_shingles is not None else _shingles(gold.text)
        if shingles and shingles & _shingles(chunk.text):
            return True
    accession = gold.accession
    return bool(
        accession and (chunk.metadata.get("accession") == accession or accession in chunk.doc_id)
    )


class RetrievalScores(BaseModel):
    n: int
    recall_at: dict[int, float]
    mrr: float
    no_match: float
    per_item: list[dict]


def evaluate(
    items: Iterable[EvalItem],
    retriever: Retriever,
    ks: tuple[int, ...] = (1, 3, 5, 10),
    progress: Callable[[str], None] = lambda _: None,
) -> RetrievalScores:
    items = [i for i in items if i.evidence]
    recalls = {k: 0.0 for k in ks}
    mrr = 0.0
    misses = 0
    per_item = []
    for n, item in enumerate(items, 1):
        progress(f"{n}/{len(items)} {item.item_id}")
        if item.mode == "docs":
            f = SearchFilter(doc_ids=[d.doc_id for d in item.documents] or None)
        else:
            f = SearchFilter(companies=item.companies or None)
        hits = retriever.retrieve(item.question, filter=f)
        ranks = []  # rank of the first chunk matching each gold evidence item
        for gold in item.evidence:
            shingles = _shingles(gold.text) if gold.text else None
            rank = next(
                (r for r, h in enumerate(hits, 1) if matches(h.chunk, gold, shingles)), None
            )
            ranks.append(rank)
        for k in ks:
            recalls[k] += sum(1 for r in ranks if r is not None and r <= k) / len(ranks)
        found = [r for r in ranks if r is not None]
        mrr += 1 / min(found) if found else 0.0
        misses += not found
        per_item.append({"item_id": item.item_id, "ranks": ranks})
    count = max(len(items), 1)
    return RetrievalScores(
        n=len(items),
        recall_at={k: v / count for k, v in recalls.items()},
        mrr=mrr / count,
        no_match=misses / count,
        per_item=per_item,
    )
