"""`loupe extract ...`: build the 8-K events table; evaluate extraction against SEC item codes."""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Annotated

import duckdb
import typer
from rich.console import Console
from rich.table import Table

from loupe.core.schemas import Document
from loupe.core.settings import get_settings
from loupe.extract.events import EXTRACT_ITEMS, EventExtractor, to_event

app = typer.Typer(no_args_is_help=True, help="8-K risk-event extraction.")
console = Console()

SCHEMA = """
CREATE TABLE IF NOT EXISTS events_extracted (
    event_id VARCHAR PRIMARY KEY, company_id VARCHAR, event_type VARCHAR, doc_id VARCHAR,
    occurred_on DATE, quote VARCHAR, quote_match DOUBLE, quality_score INTEGER, fields JSON,
    model VARCHAR
)
"""


def _docs(companies: list[str] | None) -> list[tuple[Document, str]]:
    root = get_settings().data_dir / "processed" / "sec"
    out = []
    for line in (root / "documents.jsonl").read_text().splitlines():
        doc = Document.model_validate_json(line)
        if doc.form != "8-K" or (companies and doc.company_id not in companies):
            continue
        out.append((doc, (root / "text" / f"{doc.doc_id}.txt").read_text()))
    return out


def _extractor(model: str, scorer: str | None) -> EventExtractor:
    from loupe.engine import Engine

    return EventExtractor(Engine().gateway, model, scorer)


@app.command("events")
def events(
    model: Annotated[str, typer.Option(help="Extraction model alias.")] = "groq-llama-70b",
    scorer: Annotated[str | None, typer.Option(help="Second-pass scoring model.")] = None,
    company: Annotated[list[str] | None, typer.Option(help="Only these tickers.")] = None,
    limit: Annotated[int | None, typer.Option(help="Max 8-K sections.")] = None,
) -> None:
    """Guided extraction: one call per material 8-K item section -> events_extracted table."""
    ex = _extractor(model, scorer)
    db = get_settings().data_dir / "processed" / "loupe.duckdb"
    jobs = [
        (doc, text[s.start_char : s.end_char], s.item)
        for doc, text in _docs(company)
        for s in doc.sections
        if s.item in EXTRACT_ITEMS
    ][:limit]
    found = Counter()
    with duckdb.connect(str(db)) as con, console.status("extracting") as status:
        con.execute(SCHEMA)
        for n, (doc, section, item) in enumerate(jobs, 1):
            status.update(f"{n}/{len(jobs)} {doc.doc_id} item {item}")
            for ev in ex.guided(item, section):
                e = to_event(doc, ev, model)
                con.execute(
                    "INSERT OR REPLACE INTO events_extracted VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [e.event_id, e.company_id, e.event_type, e.doc_id, e.occurred_on, e.quote,
                     e.quote_match_score, e.quality_score, json.dumps(e.fields), model],
                )  # fmt: skip
                found[item] += 1
    console.print(f"[green]{sum(found.values())} events from {len(jobs)} sections[/] {dict(found)}")


@app.command("eval-blind")
def eval_blind(
    model: Annotated[str, typer.Option(help="Extraction model alias.")] = "groq-llama-70b",
    scorer: Annotated[str | None, typer.Option(help="Second-pass scoring model.")] = None,
    split: Annotated[str, typer.Option(help="dev | test | all")] = "dev",
    limit: Annotated[int, typer.Option(help="8-Ks to sample (seeded).")] = 60,
) -> None:
    """Blind test: the model names the 8-K items from the text alone; SEC's item codes are gold.

    Reports micro precision / recall / F1 and precision by second-pass quality score
    (Paper 2's calibration test)."""
    import yaml

    companies = yaml.safe_load(Path("configs/companies_us.yaml").read_text())["companies"]
    splits = {c["id"]: c["split"] for c in companies}
    manifest = get_settings().data_dir / "raw" / "sec" / "manifest.jsonl"
    gold = {}
    for line in manifest.read_text().splitlines():
        r = json.loads(line)
        if r["form"] == "8-K" and (split == "all" or splits.get(r["company_id"]) == split):
            items = set(r["items"]) & set(EXTRACT_ITEMS)
            if items:
                gold[f"{r['company_id']}_8-K_{r['accession']}"] = items
    docs = {d.doc_id: t for d, t in _docs(None) if d.doc_id in gold}
    sample = sorted(docs)
    random.Random(20261013).shuffle(sample)
    ex = _extractor(model, scorer)
    tp = fp = fn = 0
    by_score: dict[int, list[bool]] = defaultdict(list)
    with console.status("extracting") as status:
        for n, doc_id in enumerate(sample[:limit], 1):
            status.update(f"{n}/{min(limit, len(sample))} {doc_id}")
            events = ex.blind(docs[doc_id])
            pred = {e.item for e in events}
            tp += len(pred & gold[doc_id])
            fp += len(pred - gold[doc_id])
            fn += len(gold[doc_id] - pred)
            for e in events:
                if e.score:
                    by_score[e.score].append(e.item in gold[doc_id])
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    console.print(f"8-Ks: {min(limit, len(sample))} · precision {p:.3f} · recall {r:.3f} · "
                  f"F1 {2 * p * r / (p + r) if p + r else 0:.3f}")  # fmt: skip
    table = Table("quality score", "events", "precision")
    for score in sorted(by_score):
        hits = by_score[score]
        table.add_row(str(score), str(len(hits)), f"{sum(hits) / len(hits):.2f}")
    console.print(table)
