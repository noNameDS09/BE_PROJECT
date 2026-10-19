"""SECQUE: analyst-style questions over 10-K excerpts (Analysis, Comparison, Ratio, Risk)."""

import re
from collections.abc import Iterator
from pathlib import Path

from loupe.datasets.loaders.common import flatten_markdown_tables, read_jsonl
from loupe.datasets.universe import company_split, load_universe
from loupe.eval.schema import EvalItem, GoldEvidence

NAME = "secque"
PARTS = ["Analysis", "Comparison", "Ratio", "Risk"]
_HEADER = re.compile(r"^(.+?) 10-K form for the fiscal year ended (\d{4})-\d{2}-\d{2}, page", re.M)


def _split_list(value: str | None) -> list[str]:
    return [v.strip() for v in re.split(r"[;,]", value or "") if v.strip()]


def load(root: Path) -> Iterator[EvalItem]:
    by_name = {c.name.upper(): c.id for c in load_universe().values()}
    for part in PARTS:
        path = root / f"SECQUE_benchmark_{part}.jsonl"
        if not path.exists():
            continue
        for r in read_jsonl(path):
            context = r.get("context_markdown_with_headers") or ""
            headers = _HEADER.findall(context)
            names = list(dict.fromkeys(n.strip() for n, _ in headers))
            years = {int(y) for _, y in headers}
            tickers = [by_name[n.upper()] for n in names if n.upper() in by_name]
            accessions = list(dict.fromkeys(_split_list(r.get("accession_number"))))
            items = [s.strip() for s in (r.get("item") or "").split(";") if s.strip()]
            evidence = [
                GoldEvidence(accession=a, item=items[0] if len(set(items)) == 1 else None)
                for a in accessions
            ]
            splits = {company_split(t) for t in tickers}
            yield EvalItem(
                item_id=f"{NAME}:{r['QID']}",
                dataset=NAME,
                question=r["Question"],
                kind="text",
                answer=r.get("ground_truth_answer"),
                mode="context",
                context=flatten_markdown_tables(context),
                evidence=evidence,
                companies=tickers,
                fiscal_year=years.pop() if len(years) == 1 else None,
                split=splits.pop() if len(splits) == 1 and tickers else None,  # type: ignore[arg-type]
                category=r.get("question_type") or part,
                meta={
                    "company_names": names,
                    "pages": _split_list(r.get("page_number")),
                    "items": items,
                },
            )
