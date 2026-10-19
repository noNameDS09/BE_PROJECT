"""Gold-Event labels: one item per material-event 8-K, labelled with its SEC item codes.

Labels come from EDGAR's own item list for the filing (the manifest), so they are exact.
Verbatim quotes and extracted fields are added later by an LLM pass (evidence text empty).
"""

from loupe.datasets.gold.common import GoldContext
from loupe.datasets.gold.sec_items import EVENT_ITEMS, ITEM_NAMES
from loupe.eval.schema import EvalDoc, EvalItem, GoldEvidence

NAME = "gold_event_labels"
QUESTION = "What material events does this 8-K report?"
NOT_EVENTS = {"9.01"}  # exhibit list, never an event


def documents(ctx: GoldContext, company: str, accession: str) -> list[EvalDoc]:
    base = f"{company}_8-K_{accession}"
    ids = [base, *sorted(d for d in ctx.doc_ids if d.startswith(f"{base}_ex"))]
    return [EvalDoc(doc_id=d, title=d) for d in ids if d in ctx.doc_ids]


def build(ctx: GoldContext) -> list[EvalItem]:
    items = []
    order = sorted(ctx.manifest, key=lambda r: (r["company_id"], r["filing_date"], r["accession"]))
    for r in order:
        if r["form"] != "8-K" or not set(EVENT_ITEMS) & set(r["items"]):
            continue
        company = r["company_id"]
        codes = [c for c in r["items"] if c not in NOT_EVENTS]
        labels = [{"code": c, "name": ITEM_NAMES.get(c, "unknown item")} for c in codes]
        docs = documents(ctx, company, r["accession"])
        main = docs[0].doc_id if docs else None
        items.append(
            EvalItem(
                item_id=f"{NAME}:{company}:{r['accession']}",
                dataset=NAME,
                question=QUESTION,
                kind="event",
                answer="; ".join(f"Item {x['code']} {x['name']}" for x in labels),
                mode="docs",
                documents=docs,
                evidence=[
                    GoldEvidence(doc_id=main, accession=r["accession"], item=c) for c in codes
                ],
                companies=[company],
                split=ctx.split(company),  # type: ignore[arg-type]
                category=",".join(c for c in codes if c in EVENT_ITEMS),
                meta={
                    "items": labels,
                    "event_items": [c for c in codes if c in EVENT_ITEMS],
                    "all_items": r["items"],
                    "accession": r["accession"],
                    "form": r["form"],
                    "filing_date": r["filing_date"],
                    "report_date": r.get("report_date"),
                    "url": r["url"],
                    "quotes": {},  # filled by the LLM quote pass, checked by code
                },
            )
        )
    return items
