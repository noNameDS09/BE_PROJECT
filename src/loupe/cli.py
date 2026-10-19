"""Command-line entry point: `loupe ...`."""

import json
import time
from datetime import date
from pathlib import Path
from typing import Annotated

import httpx
import typer
import yaml
from rich.console import Console
from rich.table import Table

from loupe.core.jsonl import jsonl_lines
from loupe.core.schemas import Chunk, Company, Document
from loupe.core.settings import get_settings
from loupe.datasets import public
from loupe.datasets.public import load_specs
from loupe.eval.cli import app as eval_app
from loupe.extract.cli import app as extract_app
from loupe.index.chunk import chunk_document, context_header
from loupe.index.embed import EMBEDDERS, FastEmbedder, agreement, make_embedder
from loupe.index.search import SearchFilter, SearchIndex, build_index
from loupe.ingest.build import build_corpus
from loupe.llm import Gateway, ModelRegistry
from loupe.llm.check import probe
from loupe.sources.us import edgar, fetch, universe, xbrl
from loupe.sources.us.sec_client import SecClient

DATASETS_CONFIG = Path("configs/datasets.yaml")
COMPANIES_CONFIG = Path("configs/companies_us.yaml")

app = typer.Typer(no_args_is_help=True, help="Loupe research toolkit.")
models_app = typer.Typer(no_args_is_help=True, help="LLM model registry.")
datasets_app = typer.Typer(no_args_is_help=True, help="Public evaluation datasets.")
universe_app = typer.Typer(no_args_is_help=True, help="US company universe.")
sec_app = typer.Typer(no_args_is_help=True, help="SEC EDGAR corpus.")
ingest_app = typer.Typer(no_args_is_help=True, help="Parse filings into documents.")
index_app = typer.Typer(no_args_is_help=True, help="Chunk + embed + BM25 search index.")
app.add_typer(models_app, name="models")
app.add_typer(datasets_app, name="datasets")
app.add_typer(universe_app, name="universe")
app.add_typer(sec_app, name="sec")
app.add_typer(ingest_app, name="ingest")
app.add_typer(index_app, name="index")
app.add_typer(eval_app, name="eval")
app.add_typer(extract_app, name="extract")
console = Console()

STATUS_STYLE = {"ok": "[green]ok[/]", "fail": "[red]fail[/]", "skip": "[dim]skip[/]"}


def _gateway() -> Gateway:
    s = get_settings()
    registry = ModelRegistry.from_yaml(s.models_config)
    return Gateway(registry, cache_dir=s.cache_dir, log_path=s.logs_dir / "llm_calls.jsonl")


@models_app.command("list")
def models_list() -> None:
    """Show registered models and whether their provider key is set."""
    table = Table("alias", "model", "provider", "rpm", "key")
    for spec in _gateway().registry.all():
        missing = spec.missing_key()
        table.add_row(spec.alias, spec.model, spec.provider, str(spec.rpm), missing or "set")
    console.print(table)


@models_app.command("check")
def models_check(
    only: Annotated[list[str] | None, typer.Option(help="Probe only these aliases.")] = None,
) -> None:
    """Probe each model for reachability, tool calling and JSON mode."""
    gateway = _gateway()
    specs = [s for s in gateway.registry.all() if not only or s.alias in only]
    table = Table("alias", "reachable", "tools", "json", "latency ms", "note")
    for spec in specs:
        with console.status(f"probing {spec.alias}"):
            r = probe(gateway, spec)
        table.add_row(
            r.alias,
            STATUS_STYLE[r.reachable],
            STATUS_STYLE[r.tools],
            STATUS_STYLE[r.json_mode],
            str(r.latency_ms or ""),
            r.note,
        )
    console.print(table)


@datasets_app.command("list")
def datasets_list() -> None:
    """Show the public datasets in configs/datasets.yaml and whether they are downloaded."""
    root = get_settings().data_dir / "raw" / "public"
    table = Table("name", "licence", "role", "downloaded")
    for spec in load_specs(DATASETS_CONFIG).values():
        manifest = root / spec.name / "MANIFEST.json"
        if manifest.exists():
            mb = json.loads(manifest.read_text())["total_bytes"] / 1e6
            status = f"[green]{mb:.1f} MB[/]"
        else:
            status = "[dim]deferred[/]" if spec.defer else "[dim]no[/]"
        table.add_row(spec.name, spec.licence, spec.role, status)
    console.print(table)


@datasets_app.command("download")
def datasets_download(
    names: Annotated[list[str] | None, typer.Argument(help="Datasets (default: all).")] = None,
    include_deferred: Annotated[bool, typer.Option(help="Also fetch large deferred sets.")] = False,
    refresh: Annotated[bool, typer.Option(help="Re-download files already on disk.")] = False,
) -> None:
    """Download public datasets into data/raw/public/ with a provenance manifest."""
    specs = load_specs(DATASETS_CONFIG)
    unknown = set(names or []) - specs.keys()
    if unknown:
        raise typer.BadParameter(f"unknown datasets: {', '.join(sorted(unknown))}")
    if names:
        chosen = [specs[n] for n in names]
    else:
        chosen = [s for s in specs.values() if include_deferred or not s.defer]
    root = get_settings().data_dir / "raw" / "public"
    with httpx.Client(timeout=120.0, follow_redirects=True) as http:
        for spec in chosen:
            manifest = public.download(
                spec, root, http, refresh=refresh, progress=lambda f: console.print(f"  {f}")
            )
            mb = manifest["total_bytes"] / 1e6
            console.print(f"[green]{spec.name}[/]: {len(manifest['files'])} files, {mb:.1f} MB")


def _sec_client() -> SecClient:
    s = get_settings()
    if not s.sec_user_agent:
        raise typer.BadParameter("Set SEC_USER_AGENT in .env (see .env.example)")
    return SecClient(s.sec_user_agent, s.data_dir / "raw" / "sec")


class _QuotingDumper(yaml.SafeDumper):
    """Quote digit-only strings (CIKs, fiscal year ends) so no YAML reader turns them into ints."""


_QuotingDumper.add_representer(
    str,
    lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="'" if s.isdigit() else None),
)


@universe_app.command("build")
def universe_build() -> None:
    """Resolve CIKs, check eligibility and assign dev/test for configs/companies_us.yaml."""
    cfg = yaml.safe_load(COMPANIES_CONFIG.read_text())
    start, end = cfg["window"]["start"], cfg["window"]["end"]
    selection = [universe.Selection(**row) for row in cfg["selection"]]
    client = _sec_client()
    tickers = edgar.ticker_map(client)
    split = universe.stratified_split(
        {s.ticker: s.sector for s in selection}, cfg["split"]["n_dev"], cfg["split"]["seed"]
    )
    table = Table("ticker", "name", "group", "sector", "10-K", "10-Q", "8-K", "risk items", "split")
    companies, failed = [], []
    for sel in selection:
        info = tickers.get(sel.ticker)
        if info is None:
            failed.append(f"{sel.ticker}: not in SEC ticker file")
            continue
        subs = edgar.submissions(client, info.cik, since=start)
        elig = universe.eligibility(subs["filings"], start, end)
        if not elig.eligible():
            failed.append(f"{sel.ticker}: {elig.n_10k} 10-K, {elig.n_10q} 10-Q in window")
        companies.append(
            {
                "id": sel.ticker,
                "name": info.title,
                "cik": info.cik,
                "country": "US",
                "sector": sel.sector,
                "group": sel.group,
                "split": split[sel.ticker],
                "fiscal_year_end": subs["meta"].get("fiscalYearEnd"),
                "n_10k": elig.n_10k,
                "n_10q": elig.n_10q,
                "n_8k": elig.n_8k,
                "risk_items": elig.risk_items,
            }
        )
        risk = ", ".join(f"{k}x{v}" for k, v in sorted(elig.risk_items.items()))
        table.add_row(
            sel.ticker, info.title[:28], sel.group, sel.sector, str(elig.n_10k),
            str(elig.n_10q), str(elig.n_8k), risk, split[sel.ticker],
        )  # fmt: skip
    console.print(table)
    if failed:
        console.print("[red]Not eligible:[/]\n  " + "\n  ".join(failed))
        raise typer.Exit(1)
    text = COMPANIES_CONFIG.read_text()
    head = text[: text.index("\ncompanies:")]
    body = yaml.dump({"companies": companies}, Dumper=_QuotingDumper, sort_keys=False, width=100)
    COMPANIES_CONFIG.write_text(f"{head}\n{body}")
    console.print(f"[green]Wrote {len(companies)} companies to {COMPANIES_CONFIG}[/]")


def _companies(only: list[str] | None) -> list[Company]:
    rows = yaml.safe_load(COMPANIES_CONFIG.read_text())["companies"]
    if not rows:
        raise typer.BadParameter("No companies yet: run `loupe universe build` first")
    companies = [Company(**r) for r in rows]
    return [c for c in companies if not only or c.id in only]


@sec_app.command("fetch")
def sec_fetch(
    only: Annotated[list[str] | None, typer.Option(help="Only these tickers.")] = None,
) -> None:
    """Download 10-K, 10-Q, 8-K (+ EX-99.1) and XBRL facts for the company universe."""
    cfg = yaml.safe_load(COMPANIES_CONFIG.read_text())
    start, end = cfg["window"]["start"], cfg["window"]["end"]
    client = _sec_client()
    out = get_settings().data_dir / "raw" / "sec"
    records, coverage = [], []
    table = Table("ticker", "10-K", "10-Q", "8-K", "facts", "errors")
    with console.status("fetching") as status:
        for company in _companies(only):
            recs, cov = fetch.fetch_company(client, company, start, end, progress=status.update)
            records += recs
            coverage.append(cov)
            cells = [f"{cov.fetched.get(f, 0)}/{cov.listed.get(f, 0)}" for f in fetch.FORMS]
            table.add_row(
                company.id, *cells, "yes" if cov.facts else "[red]no[/]", str(len(cov.errors))
            )
    suffix = "" if not only else "-" + "-".join(only)
    fetch.write_manifest(out / f"manifest{suffix}.jsonl", records)
    fetch.write_coverage(out / f"coverage{suffix}.json", coverage)
    console.print(table)
    listed = sum(sum(c.listed.values()) for c in coverage)
    got = sum(sum(c.fetched.values()) for c in coverage)
    console.print(f"Coverage: {got}/{listed} filings ({100 * got / max(listed, 1):.1f}%)")


@sec_app.command("facts")
def sec_facts(
    only: Annotated[list[str] | None, typer.Option(help="Only these tickers.")] = None,
) -> None:
    """Load XBRL company facts into the DuckDB store (data/processed/loupe.duckdb)."""
    client = _sec_client()
    db = get_settings().data_dir / "processed" / "loupe.duckdb"
    table = Table("ticker", "facts", "concepts")
    for company in _companies(only):
        raw = edgar.company_facts(client, company.cik)
        n = xbrl.load_facts(db, company.id, raw)
        concepts = sum(len(v) for v in raw.get("facts", {}).values())
        table.add_row(company.id, f"{n:,}", f"{concepts:,}")
    console.print(table)
    console.print(f"[green]Facts loaded into {db}[/]")


@ingest_app.command("build")
def ingest_build() -> None:
    """Parse fetched SEC filings into clean text + sections; write a parse-quality report."""
    data = get_settings().data_dir
    raw = data / "raw" / "sec"
    out = data / "processed" / "sec"
    with console.status("parsing") as status:
        report = build_corpus(raw / "manifest.jsonl", raw, out, progress=status.update)
    table = Table("form", "filings", "all expected sections", "section recall")
    for form, r in report["by_form"].items():
        table.add_row(
            form, str(r["filings"]), f"{r['complete_rate']:.1%}", f"{r['item_recall']:.1%}"
        )
    console.print(table)
    console.print(f"{len(report['errors'])} errors · details in {out / 'parse_report.json'}")


def _index_dir(variant: str | None = None) -> Path:
    root = get_settings().data_dir / "processed" / "index"
    if variant is None:
        default = root / "DEFAULT"
        if not default.exists():
            raise typer.BadParameter("No index yet: run `loupe index build` first")
        variant = default.read_text().strip()
    return root / variant


@index_app.command("build")
def index_build(
    size: Annotated[int, typer.Option(help="Max chunk size in characters.")] = 1200,
    overlap: Annotated[int, typer.Option(help="Overlap between chunks in characters.")] = 150,
    embedder: Annotated[str, typer.Option(help=f"One of: {', '.join(EMBEDDERS)}.")] = "bge-small",
    device: Annotated[str, typer.Option(help="cpu (ONNX) | cuda | mps")] = "cpu",
    from_chunks: Annotated[
        Path | None, typer.Option(help="Embed an existing chunks.jsonl instead of re-chunking.")
    ] = None,
    default: Annotated[bool, typer.Option(help="Make this variant the default.")] = True,
) -> None:
    """Chunk every parsed document (section-aware), embed, build BM25.

    On a CPU this takes hours for the full corpus; use --device cuda on an NVIDIA GPU
    (see docs/GPU-INDEX-BUILD.md)."""
    variant = f"c{size}o{overlap}-{embedder}"
    out = get_settings().data_dir / "processed" / "index" / variant
    if from_chunks is not None:
        chunks = [Chunk.model_validate_json(x) for x in jsonl_lines(from_chunks)]
        console.print(f"Loaded {len(chunks):,} chunks from {from_chunks}")
    else:
        data = get_settings().data_dir / "processed" / "sec"
        chunks = []
        with console.status("chunking"):
            for line in jsonl_lines(data / "documents.jsonl"):
                doc = Document.model_validate_json(line)
                text = (data / "text" / f"{doc.doc_id}.txt").read_text()
                chunks += chunk_document(doc, text, size, overlap)
    started = time.time()

    def progress(msg: str) -> None:
        console.log(f"{msg} · {time.time() - started:,.0f}s")

    console.log(f"loading {embedder} on {device}")
    build_index(chunks, out, make_embedder(embedder, device), progress=progress)
    if default:
        (out.parent / "DEFAULT").write_text(variant)
    console.print(
        f"[green]{len(chunks):,} chunks indexed in {out} ({time.time() - started:,.0f}s)[/]"
    )


@index_app.command("check")
def index_check(
    variant: Annotated[str | None, typer.Option(help="Index variant (default: DEFAULT).")] = None,
    sample: Annotated[int, typer.Option(help="Chunks to re-embed locally.")] = 64,
) -> None:
    """Verify an index built elsewhere (e.g. on a GPU): counts match, vectors agree with ONNX.

    A seeded sample of chunks is re-embedded locally; cosine with the stored vectors must be
    at least 0.99."""
    import random

    import numpy as np

    path = _index_dir(variant)
    info = json.loads((path / "INFO.json").read_text())
    lines = jsonl_lines(path / "chunks.jsonl")
    dense = np.load(path / "dense.npy", mmap_mode="r")
    ok = len(lines) == info["chunks"] == dense.shape[0]
    status = "[green]consistent[/]" if ok else "[red]MISMATCH[/]"
    console.print(
        f"chunks.jsonl {len(lines):,} · dense.npy {dense.shape} · "
        f"INFO {info['chunks']:,} -> {status}"
    )
    idx = sorted(random.Random(20261013).sample(range(len(lines)), min(sample, len(lines))))
    chunks = [Chunk.model_validate_json(lines[i]) for i in idx]
    fresh = FastEmbedder(info["embedder"]).passages([context_header(c) + c.text for c in chunks])
    cos = agreement(np.asarray(dense[idx]), fresh)
    good = bool(cos.min() >= 0.99)
    verdict = "[green]vectors match[/]" if good else "[red]vectors differ[/]"
    console.print(
        f"re-embedded {len(idx)} chunks: cosine min {cos.min():.4f}, "
        f"mean {cos.mean():.4f} -> {verdict}"
    )
    if not (ok and good):
        raise typer.Exit(1)


@app.command("search")
def search(
    query: str,
    company: Annotated[list[str] | None, typer.Option(help="Ticker(s).")] = None,
    form: Annotated[list[str] | None, typer.Option(help="10-K, 10-Q, 8-K, EX-99.1")] = None,
    item: Annotated[
        list[str] | None, typer.Option(help="Section item, e.g. 1A, 7, I-2, 2.02")
    ] = None,
    period_from: Annotated[str | None, typer.Option("--from", help="YYYY-MM-DD")] = None,
    period_to: Annotated[str | None, typer.Option("--to", help="YYYY-MM-DD")] = None,
    k: Annotated[int, typer.Option(help="Number of results.")] = 5,
    mode: Annotated[str, typer.Option(help="hybrid | dense | bm25")] = "hybrid",
    variant: Annotated[str | None, typer.Option(help="Index variant (default: DEFAULT).")] = None,
) -> None:
    """Search the filings and print cited passages."""
    path = _index_dir(variant)
    info = json.loads((path / "INFO.json").read_text())
    index = SearchIndex.load(path, FastEmbedder(info["embedder"]))
    f = SearchFilter(
        companies=company,
        forms=form,
        items=item,
        period_from=date.fromisoformat(period_from) if period_from else None,
        period_to=date.fromisoformat(period_to) if period_to else None,
    )
    for n, hit in enumerate(index.search(query, k=k, filter=f, mode=mode), 1):  # type: ignore[arg-type]
        c, m = hit.chunk, hit.chunk.metadata
        items = ",".join(m.get("items") or []) or "cover"
        console.rule(
            f"[{n}] {c.company_id} {m.get('form')} {m.get('period_end')} item {items} "
            f"[dim](dense #{hit.dense_rank}, bm25 #{hit.bm25_rank})[/]"
        )
        console.print(c.text[:700] + ("…" if len(c.text) > 700 else ""), highlight=False)
        console.print(f"[dim]{m.get('url')}  chars {c.start_char}-{c.end_char}[/]")


@app.command("ask")
def ask(
    question: str,
    arm: Annotated[
        list[str] | None, typer.Option(help="Arm name (repeat to compare). See `loupe arms`.")
    ] = None,
    model: Annotated[str, typer.Option(help="Alias from configs/models.yaml.")] = "groq-llama-70b",
    rerank: Annotated[
        str | None, typer.Option(help="Reranker: minilm-l12 | minilm-l6 | bge-base | none")
    ] = "minilm-l12",
    rewrite: Annotated[bool, typer.Option(help="Multi-query rewriting before search.")] = False,
    tools: Annotated[bool, typer.Option(help="Number tools on (off = LLM does the maths).")] = True,
    trace: Annotated[bool, typer.Option(help="Show every step and tool call.")] = False,
) -> None:
    """Answer a question with one or more arms; every claim is checked against evidence."""
    from loupe.engine import Engine
    from loupe.index.retriever import RetrievalConfig

    engine = Engine()
    retrieval = RetrievalConfig(
        rerank=None if rerank in (None, "none") else rerank,
        query_rewrite="multi" if rewrite else "none",
    )
    for name in arm or ["loupe"]:
        with console.status(f"{name} on {model}"):
            answer = engine.ask(
                question, arm=name, model=model, retrieval=retrieval, tools_enabled=tools
            )
        console.rule(f"[bold]{name}[/] · {model}")
        console.print(answer.text, highlight=False)
        checked = [c for c in answer.claims if c.supported is not None]
        ok = sum(bool(c.supported) for c in checked)
        console.print(
            f"[dim]claims verified {ok}/{len(checked)} · evidence {len(answer.evidence)} · "
            f"charts {len(answer.charts)} · tokens {answer.tokens:,} · "
            f"{answer.latency_ms / 1000:.1f}s · abstained {answer.abstained}[/]"
        )
        for c in answer.claims:
            if c.supported is False:
                console.print(f"  [red]unsupported:[/] {c.text[:160]}", highlight=False)
        if trace:
            for step in answer.trace:
                console.print(
                    f"  [cyan]{step.stage}:{step.name}[/] {str(step.input)[:120]}", highlight=False
                )


@app.command("arms")
def arms() -> None:
    """List orchestration arms (main arms and Loupe ablations)."""
    from loupe.orchestrators import ARMS

    table = Table("name", "label", "description")
    for a in ARMS.values():
        table.add_row(a.name, a.label, a.description)
    console.print(table)


@sec_app.command("events")
def sec_events() -> None:
    """Build the 8-K events table (one row per item per filing) in the DuckDB store."""
    from loupe.sources.us.events import load_events

    data = get_settings().data_dir
    n = load_events(data / "processed" / "loupe.duckdb", data / "raw" / "sec" / "manifest.jsonl")
    console.print(f"[green]{n:,} 8-K item rows loaded into filing_events[/]")


@app.command("serve")
def serve(
    host: Annotated[str, typer.Option(help="Bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port.")] = 8000,
    reload: Annotated[bool, typer.Option(help="Auto-reload on code changes.")] = False,
) -> None:
    """Start the API (and the built web app from web/dist, if present)."""
    import uvicorn

    from loupe.api.app import app as api
    from loupe.api.app import mount_web

    mount_web()
    if reload:
        uvicorn.run("loupe.api.app:app", host=host, port=port, reload=True)
    else:
        uvicorn.run(api, host=host, port=port)


if __name__ == "__main__":
    app()
