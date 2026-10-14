"""Command-line entry point: `loupe ...`."""

import json
from pathlib import Path
from typing import Annotated

import httpx
import typer
import yaml
from rich.console import Console
from rich.table import Table

from loupe.core.schemas import Company
from loupe.core.settings import get_settings
from loupe.datasets import public
from loupe.datasets.public import load_specs
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
app.add_typer(models_app, name="models")
app.add_typer(datasets_app, name="datasets")
app.add_typer(universe_app, name="universe")
app.add_typer(sec_app, name="sec")
app.add_typer(ingest_app, name="ingest")
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


if __name__ == "__main__":
    app()
