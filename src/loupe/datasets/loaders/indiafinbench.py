"""IndiaFinBench (Pall 2026), dev + test: SEBI/RBI regulatory QA with the passage inline."""

from collections.abc import Iterator
from pathlib import Path

import pyarrow.parquet as pq

from loupe.datasets.loaders.common import apply_numeric, numeric_fields
from loupe.eval.schema import EvalItem, GoldEvidence

NAME = "indiafinbench"
PREFIX = "indiafinbench_"


def load(root: Path) -> Iterator[EvalItem]:
    for split in ("dev", "test"):
        path = root / "data" / f"{split}-00000-of-00001.parquet"
        if not path.exists():
            continue
        for r in pq.read_table(path).to_pylist():
            native = r["id"].removeprefix(PREFIX)
            meta = {
                "difficulty": r.get("difficulty"),
                "regulator": r.get("source"),
                "source_document": r.get("source_document"),
                "country": "IN",
            }
            numeric = numeric_fields(r["reference_answer"], r["question"])
            yield EvalItem(
                item_id=f"{NAME}:{native}",
                dataset=NAME,
                question=r["question"],
                answer=r["reference_answer"],
                mode="context",
                context=r.get("context"),
                evidence=[GoldEvidence(doc_id=r.get("source_document"), text=r.get("context"))],
                split=split,  # type: ignore[arg-type]
                category=r.get("task_type"),
                meta=meta,
                **(apply_numeric(numeric, meta) if numeric else {"kind": "text"}),
            )
