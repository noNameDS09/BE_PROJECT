"""Vals.ai Finance Agent benchmark, public splits of v1 and v2 (agent questions over EDGAR).

No documents ship with the questions: the agent must find them (mode "corpus"). Grading is
rubric-based, so each item carries its parsed rubric in meta. v2's public file has no answers.
"""

import ast
import csv
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from loupe.datasets.loaders.common import apply_numeric, numeric_fields
from loupe.eval.schema import EvalItem


def _rubric(raw: str | None) -> list[Any] | str | None:
    if not raw:
        return None
    for parse in (json.loads, ast.literal_eval):
        try:
            return parse(raw)
        except (ValueError, SyntaxError):
            continue
    return raw  # keep unparsed text rather than drop it


def _load(root: Path, name: str, rel: str) -> Iterator[EvalItem]:
    with (root / rel).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for n, r in enumerate(rows, 1):
        answer = (r.get("Answer") or "").strip() or None
        meta: dict[str, Any] = {
            "row": n,
            "rubric": _rubric(r.get("Rubric")),
            "expert_time_mins": int(r["Expert time (mins)"])
            if (r.get("Expert time (mins)") or "").isdigit()
            else None,
        }
        numeric = numeric_fields(answer, r["Question"])
        yield EvalItem(
            item_id=f"{name}:{n:03d}",
            dataset=name,
            question=r["Question"],
            answer=answer,
            mode="corpus",
            category=r.get("Question Type"),
            meta=meta,
            **(apply_numeric(numeric, meta) if numeric else {"kind": "text"}),
        )


def load_v1(root: Path) -> Iterator[EvalItem]:
    return _load(root, "finance_agent_v1", "finance_agent_benchmark.csv")


def load_v2(root: Path) -> Iterator[EvalItem]:
    return _load(root, "finance_agent_v2", "data/public.csv")


LOADERS: dict[str, Callable[[Path], Iterator[EvalItem]]] = {
    "finance_agent_v1": load_v1,
    "finance_agent_v2": load_v2,
}
