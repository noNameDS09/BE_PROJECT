"""FinQA (Chen et al. 2021), test split: numeric reasoning over an earnings-report page.

The gold number is the executed program result (`exe_ans`), as in FinQA's execution accuracy.
When the published answer is a percentage ("14%"), `exe_ans` is a fraction (0.14464), so it
is scaled to percent and the unit set to "%". Numbers are in the units of the page (often
millions), so `answer_unit` is left empty unless the answer shows one.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from loupe.datasets.loaders.common import flatten_table, parse_number, tolerance_for
from loupe.eval.schema import EvalItem, GoldEvidence

NAME = "finqa"


def page_context(record: dict[str, Any]) -> str:
    parts = [" ".join(record.get("pre_text") or [])]
    table = record.get("table_ori") or record.get("table") or []
    if table:
        parts.append(flatten_table(table))
    parts.append(" ".join(record.get("post_text") or []))
    return "\n\n".join(p for p in parts if p.strip())


def program_answer(exe_ans: Any, answer_text: str | None) -> dict[str, Any]:
    """EvalItem fields + meta for a FinQA-style program result."""
    if isinstance(exe_ans, str):
        try:
            exe_ans = float(exe_ans)
        except ValueError:
            return {"kind": "text", "meta": {}}  # yes/no questions
    if exe_ans is None:
        return {"kind": "text", "meta": {}}
    parsed = parse_number(answer_text)
    value, unit = float(exe_ans), None

    def close(a: float, b: float) -> bool:
        return abs(a - b) <= max(abs(b) * 0.05, 1.0)

    if parsed is not None and parsed.unit == "%" and close(value * 100, parsed.value):
        value, unit = value * 100, "%"  # fraction -> percent
    elif parsed is not None and close(value, parsed.value):
        unit = parsed.unit
    else:
        parsed = None  # the text answer describes a different number; trust the program
    tol = tolerance_for(parsed, value) if parsed is not None else 0.01
    return {
        "kind": "numeric",
        "answer_value": value,
        "answer_unit": unit,
        "tolerance": tol,
        "meta": {"abs_tolerance": parsed.half_ulp if parsed else None, "exe_ans": exe_ans},
    }


def load(root: Path) -> Iterator[EvalItem]:
    records = json.loads((root / "dataset" / "test.json").read_text())
    for r in records:
        qa = r["qa"]
        fields = program_answer(qa.get("exe_ans"), qa.get("answer"))
        meta = {
            "filename": r.get("filename"),
            "program": qa.get("program"),
            "source_split": "test",
            **fields.pop("meta"),
        }
        evidence = [GoldEvidence(text=t) for t in (qa.get("gold_inds") or {}).values()]
        yield EvalItem(
            item_id=f"{NAME}:{r['id']}",
            dataset=NAME,
            question=qa["question"],
            answer=str(qa.get("answer") or qa.get("exe_ans")),
            mode="context",
            context=page_context(r),
            evidence=evidence,
            split="test",
            meta=meta,
            **fields,
        )
