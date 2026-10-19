"""ConvFinQA (Chen et al. 2022), dev split: multi-turn numeric conversations.

One item per conversation: `turns` holds the earlier questions, `question` the final turn,
and the gold value is the final turn's executed result. Per-turn gold answers and programs
are kept in meta so turn-level accuracy can still be computed. Read straight from data.zip.
"""

import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

from loupe.datasets.loaders.finqa import page_context, program_answer
from loupe.eval.schema import EvalItem, GoldEvidence

NAME = "convfinqa"


def _answer_text(fields: dict) -> str | None:
    if fields["kind"] != "numeric":
        return None
    return f"{fields['answer_value']:.6g}{'%' if fields['answer_unit'] == '%' else ''}"


def load(root: Path) -> Iterator[EvalItem]:
    with zipfile.ZipFile(root / "data.zip") as z:
        records = json.loads(z.read("data/dev.json"))
    for r in records:
        ann = r["annotation"]
        dialogue = ann["dialogue_break"]
        answers = ann["exe_ans_list"]
        # the final turn belongs to the last original FinQA question (qa, or qa_1 for "Double")
        qa = r.get("qa") or r.get(f"qa_{ann['qa_split'][-1]}") or {}
        fields = program_answer(answers[-1], qa.get("answer"))
        meta = {
            "filename": r.get("filename"),
            "turn_answers": answers,
            "turn_programs": ann.get("turn_program"),
            "qa_split": ann.get("qa_split"),
            "original_question": qa.get("question"),
            "original_answer": qa.get("answer"),
            "source_split": "dev",
            **fields.pop("meta"),
        }
        evidence = [GoldEvidence(text=t) for t in (qa.get("gold_inds") or {}).values()]
        yield EvalItem(
            item_id=f"{NAME}:{r['id']}",
            dataset=NAME,
            question=dialogue[-1],
            turns=dialogue[:-1],
            answer=_answer_text(fields) or str(answers[-1]),
            mode="context",
            context=page_context(r),
            evidence=evidence,
            split="dev",
            category=r["id"].split("_", 1)[0].lower(),  # "single" or "double" conversation
            meta=meta,
            **fields,
        )
