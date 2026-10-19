"""FailSafeQA (Kamble et al. 2025): robustness and context grounding on long 10-K contexts.

Every record yields one item per test condition of the paper:
- answerable (kind "text", gold = the record's answer): baseline, misspelled query,
  incomplete query, out-of-domain (reworded) query, OCR-corrupted context;
- should decline (kind "refusal"): missing context (query with no document) and irrelevant
  context (the record's out-of-scope query, written for another filing, asked of this one).
"""

import json
from collections.abc import Iterator
from pathlib import Path

from loupe.eval.schema import EvalItem, GoldEvidence

NAME = "failsafeqa"
DECLINE_MISSING = (
    "Decline: no context document was provided, so the question cannot be answered from it; "
    "the model should say the information is missing rather than answer from memory."
)
DECLINE_IRRELEVANT = (
    "Decline: the provided filing does not contain information about this question; "
    "the model should say so rather than invent an answer."
)

# condition -> (query field, context field or None, kind)
CONDITIONS = {
    "baseline": ("query", "context", "text"),
    "misspelled_query": ("error_query", "context", "text"),
    "incomplete_query": ("incomplete_query", "context", "text"),
    "out_of_domain_query": ("out-of-domain_query", "context", "text"),
    "ocr_context": ("query", "ocr_context", "text"),
    "missing_context": ("query", None, "refusal"),
    "irrelevant_context": ("out-of-scope_query", "context", "refusal"),
}


def load(root: Path) -> Iterator[EvalItem]:
    # the published ".jsonl" is a single JSON array
    records = json.loads((root / "FAILSAFEQA_benchmark_data-FINAL.jsonl").read_text())
    q2c_path = root / "query_to_class.json"
    q2c = json.loads(q2c_path.read_text()) if q2c_path.exists() else {}
    for r in records:
        for condition, (qf, cf, kind) in CONDITIONS.items():
            question = r.get(qf)
            if not question:
                continue
            refusal = kind == "refusal"
            answer = (
                (DECLINE_MISSING if condition == "missing_context" else DECLINE_IRRELEVANT)
                if refusal
                else r["answer"]
            )
            yield EvalItem(
                item_id=f"{NAME}:{r['idx']}:{condition}",
                dataset=NAME,
                question=question,
                kind=kind,  # type: ignore[arg-type]
                answer=answer,
                mode="context",
                context=r.get(cf) if cf else "",
                evidence=[] if refusal else [GoldEvidence(text=r.get("citations"))],
                category=condition,
                meta={
                    "record": r["idx"],
                    "original_query": r["query"],
                    "original_answer": r["answer"] if refusal else None,
                    "query_class": q2c.get(question),
                    "context_tokens": r.get("tokens"),
                },
            )
