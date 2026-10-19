"""IndFin-Bench (cofacto): 100 questions on Indian listed-company filings; no documents ship.

The gold is an "atomic fact"; when it is a single amount ("₹4,045.8 million", "₹91 crores")
the item is numeric in rupees, otherwise text for a judge.
"""

import csv
from collections.abc import Iterator
from pathlib import Path

from loupe.datasets.loaders.common import apply_numeric, numeric_fields
from loupe.eval.schema import EvalItem

NAME = "indfin_bench"


def load(root: Path) -> Iterator[EvalItem]:
    with (root / "IndFin-Bench.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            answer = (r.get("Atomic_Fact") or "").strip() or None
            meta = {"country": "IN", "corpus": "Indian company filings (not yet collected)"}
            numeric = numeric_fields(answer)
            yield EvalItem(
                item_id=f"{NAME}:{int(r['Question_Num']):03d}",
                dataset=NAME,
                question=r["Question"],
                answer=answer,
                mode="corpus",
                category=r.get("Complexity_Category"),
                meta=meta,
                **(apply_numeric(numeric, meta) if numeric else {"kind": "text"}),
            )
