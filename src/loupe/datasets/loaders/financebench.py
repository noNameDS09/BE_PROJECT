"""FinanceBench open sample (150 questions over 10-K/10-Q/8-K PDFs with page evidence)."""

from collections.abc import Iterator
from pathlib import Path

from loupe.datasets.loaders.common import apply_numeric, numeric_fields, read_jsonl, unique_fy
from loupe.datasets.universe import company_split
from loupe.eval.schema import EvalDoc, EvalItem, GoldEvidence

NAME = "financebench"

# FinanceBench company names -> our tickers (configs/companies_us.yaml, group financebench)
TICKERS = {
    "3M": "MMM",
    "PepsiCo": "PEP",
    "Amcor": "AMCR",
    "Johnson & Johnson": "JNJ",
    "AMD": "AMD",
    "Best Buy": "BBY",
    "Boeing": "BA",
    "American Express": "AXP",
    "MGM Resorts": "MGM",
    "Pfizer": "PFE",
    "Ulta Beauty": "ULTA",
    "Adobe": "ADBE",
    "JPMorgan": "JPM",
    "Verizon": "VZ",
    "CVS Health": "CVS",
}


def _pdf(doc_name: str) -> EvalDoc:
    return EvalDoc(doc_id=doc_name, title=doc_name, path=f"raw/public/{NAME}/pdfs/{doc_name}.pdf")


def load(root: Path) -> Iterator[EvalItem]:
    info = {
        d["doc_name"]: d
        for d in read_jsonl(root / "data" / "financebench_document_information.jsonl")
    }
    for r in read_jsonl(root / "data" / "financebench_open_source.jsonl"):
        doc = info.get(r["doc_name"], {})
        ticker = TICKERS.get(r["company"])
        meta = {
            "company_name": r["company"],
            "question_reasoning": r.get("question_reasoning"),
            "justification": r.get("justification"),
            "domain_question_num": r.get("domain_question_num"),
            "doc_type": doc.get("doc_type"),
            "doc_period": doc.get("doc_period"),
            "doc_link": doc.get("doc_link"),
            "gics_sector": doc.get("gics_sector"),
            "page_index": "evidence_page_num as published by FinanceBench",
        }
        evidence = []
        doc_names = [r["doc_name"]]
        for ev in r.get("evidence") or []:
            name = ev.get("doc_name") or r["doc_name"]
            if name not in doc_names:
                doc_names.append(name)
            page = ev.get("evidence_page_num")
            evidence.append(
                GoldEvidence(
                    doc_id=name,
                    page=int(page) if page not in (None, "") else None,
                    text=ev.get("evidence_text"),
                )
            )
        fy = unique_fy(r["question"])
        if fy is None and doc.get("doc_type") == "10k":
            fy = doc.get("doc_period")
        numeric = numeric_fields(r["answer"], r["question"])
        yield EvalItem(
            item_id=f"{NAME}:{r['financebench_id']}",
            dataset=NAME,
            question=r["question"],
            answer=r["answer"],
            mode="docs",
            documents=[_pdf(n) for n in doc_names],
            evidence=evidence,
            companies=[ticker] if ticker else [],
            fiscal_year=fy,
            split=company_split(ticker) if ticker else None,  # type: ignore[arg-type]
            category=r.get("question_type"),
            meta=meta,
            **(apply_numeric(numeric, meta) if numeric else {"kind": "text"}),
        )
