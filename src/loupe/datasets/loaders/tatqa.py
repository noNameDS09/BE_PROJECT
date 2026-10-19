"""TAT-QA (Zhu et al. 2021), dev + test_gold: hybrid table + text QA with an answer scale.

Arithmetic and count answers, and spans that are a single number, are numeric: the scale
(thousand/million/billion) is applied so `answer_value` is in base units, and "percent"
sets the unit to "%". Other spans and multi-span answers are text.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from loupe.datasets.loaders.common import (
    SCALES,
    flatten_table,
    is_year,
    parse_number,
    tolerance_for,
)
from loupe.eval.schema import EvalItem

NAME = "tatqa"
FILES = {"dev": "tatqa_dataset_dev.json", "test": "tatqa_dataset_test_gold.json"}


def _answer_text(answer: Any, scale: str) -> str:
    text = "; ".join(str(a) for a in answer) if isinstance(answer, list) else str(answer)
    if scale == "percent":
        return text if text.endswith("%") else f"{text}%"
    if scale and scale not in text.lower():
        return f"{text} {scale}"
    return text


def numeric(answer: Any, answer_type: str, scale: str) -> dict[str, Any] | None:
    if isinstance(answer, list):
        if len(answer) != 1:
            return None
        answer = answer[0]
    if answer_type not in ("arithmetic", "count", "span"):
        return None
    parsed = parse_number(str(answer))
    if parsed is None or (answer_type == "span" and not scale and is_year(parsed, str(answer))):
        return None
    factor = 1.0 if parsed.scaled else SCALES.get(scale, 1.0)  # "$(9.8) million" is scaled
    unit = "%" if scale == "percent" else parsed.unit
    value = parsed.value * factor
    parsed = parsed.model_copy(update={"value": value, "half_ulp": parsed.half_ulp * factor})
    return {
        "kind": "numeric",
        "answer_value": value,
        "answer_unit": unit,
        "tolerance": tolerance_for(parsed),
        "abs_tolerance": parsed.half_ulp,
    }


def context(doc: dict[str, Any]) -> str:
    table = flatten_table(doc["table"]["table"])
    paragraphs = sorted(doc.get("paragraphs") or [], key=lambda p: p.get("order", 0))
    return "\n\n".join([table, *(p["text"] for p in paragraphs)])


def load(root: Path) -> Iterator[EvalItem]:
    for split, filename in FILES.items():
        path = root / "dataset_raw" / filename
        if not path.exists():
            continue
        for doc in json.loads(path.read_text()):
            ctx = context(doc)
            for q in doc["questions"]:
                scale = q.get("scale") or ""
                meta = {
                    "answer_from": q.get("answer_from"),
                    "derivation": q.get("derivation"),
                    "scale": scale,
                    "raw_answer": q.get("answer"),
                    "rel_paragraphs": q.get("rel_paragraphs"),
                    "req_comparison": q.get("req_comparison"),
                    "table_uid": doc["table"].get("uid"),
                    "source_split": "test_gold" if split == "test" else split,
                }
                fields = numeric(q.get("answer"), q.get("answer_type", ""), scale)
                if fields:
                    meta["abs_tolerance"] = fields.pop("abs_tolerance")
                yield EvalItem(
                    item_id=f"{NAME}:{q['uid']}",
                    dataset=NAME,
                    question=q["question"],
                    answer=_answer_text(q.get("answer"), scale),
                    mode="context",
                    context=ctx,
                    split=split,  # type: ignore[arg-type]
                    category=q.get("answer_type"),
                    meta=meta,
                    **(fields or {"kind": "text"}),
                )
