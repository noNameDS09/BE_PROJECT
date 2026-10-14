"""Command-line entry point: `loupe ...`."""

import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from loupe.core.settings import get_settings
from loupe.llm import Gateway, ModelRegistry
from loupe.llm.check import probe

app = typer.Typer(no_args_is_help=True, help="Loupe research toolkit.")
models_app = typer.Typer(no_args_is_help=True, help="LLM model registry.")
app.add_typer(models_app, name="models")
console = Console()

STATUS_STYLE = {"ok": "[green]ok[/]", "fail": "[red]fail[/]", "skip": "[dim]skip[/]"}


def _logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=verbose)],
    )


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


@app.command("ingest")
def ingest_cmd(
    companies: Annotated[
        list[str] | None, typer.Option(help="Tickers to ingest; default all.")
    ] = None,
    split: Annotated[str | None, typer.Option(help="Only dev or only test.")] = None,
    forms: Annotated[list[str] | None, typer.Option(help="Filing forms to fetch.")] = None,
    start: Annotated[str | None, typer.Option(help="Corpus window start (YYYY-MM-DD).")] = None,
    end: Annotated[str | None, typer.Option(help="Corpus window end (YYYY-MM-DD).")] = None,
    limit: Annotated[int | None, typer.Option(help="Max filings per company (debugging).")] = None,
    facts: Annotated[bool, typer.Option(help="Fetch XBRL facts.")] = True,
    prices: Annotated[bool, typer.Option(help="Fetch daily closes.")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Download filings and XBRL facts into the local store."""
    _logging(verbose)
    from loupe.ingest import runner
    from loupe.sources import identity, us
    from loupe.store import db

    s = get_settings()
    s.ensure_dirs()
    us.set_cache_dir(s.cache_dir / "edgar")
    us.configure_identity(s.sec_user_agent)

    universe = identity.resolve_universe(
        s.companies_config, s.sec_user_agent, s.processed_dir / "tickers.json"
    )
    if split:
        universe = [c for c in universe if c.split == split]
    if companies:
        wanted = {t.upper() for t in companies}
        universe = [c for c in universe if c.ticker in wanted]
    if not universe:
        console.print("[yellow]No companies selected.[/]")
        raise typer.Exit(1)

    runner.configure_db(s.duckdb_path)
    conn = db.connect(s.duckdb_path)
    db.save_companies(conn, universe)
    conn.close()

    console.print(
        f"Ingesting [bold]{len(universe)}[/] companies, {s.corpus_start} to {s.corpus_end}"
    )
    table = Table("ticker", "filings", "sections", "chunks", "facts", "prices", "notes")
    for company in universe:
        with console.status(f"[cyan]{company.ticker}[/]"):
            stats = runner.ingest_company(
                company,
                start=start or s.corpus_start,
                end=end or s.corpus_end,
                forms=tuple(forms) if forms else us.CORPUS_FORMS,
                with_facts=facts,
                with_prices=prices,
                max_filings=limit,
            )
        table.add_row(
            stats.ticker,
            str(stats.filings),
            str(stats.sections),
            str(stats.chunks),
            str(stats.facts),
            str(stats.prices),
            f"[red]{len(stats.errors)} errors[/]" if stats.errors else "",
        )
        for message in stats.errors[:3]:
            console.print(f"  [dim]{stats.ticker}: {message}[/]")
    console.print(table)
    console.print(f"Store: [dim]{s.duckdb_path}[/]")


@app.command("coverage")
def coverage_cmd() -> None:
    """Report what has been ingested, per company."""
    from loupe.store import db

    s = get_settings()
    conn = db.connect(s.duckdb_path, read_only=True)
    try:
        rows = db.coverage_report(conn)
    finally:
        conn.close()

    if not rows:
        console.print("[yellow]Nothing ingested yet. Run `loupe ingest` first.[/]")
        return

    table = Table("ticker", "filings", "sections", "chunks", "facts", "prices")
    for row in rows:
        table.add_row(
            row["ticker"],
            str(row["filings"]),
            str(row["sections"]),
            str(row["chunks"]),
            str(row["facts"]),
            str(row["price_rows"]),
        )
    console.print(table)

    empty = [r["ticker"] for r in rows if not r["chunks"]]
    if empty:
        console.print(f"[yellow]No chunks for:[/] {', '.join(empty)}")
    covered = sum(1 for r in rows if r["chunks"])
    console.print(f"Coverage: [bold]{covered}/{len(rows)}[/] companies have chunks")


@app.command("scan-risk")
def scan_risk_cmd(
    limit: Annotated[int, typer.Option(help="How many candidates to report.")] = 25,
    min_risk: Annotated[int, typer.Option(help="Minimum risk-item 8-Ks to report.")] = 1,
    output: Annotated[
        str | None, typer.Option(help="Write JSON here instead of the table.")
    ] = None,
) -> None:
    """Rank companies by notable 8-K risk events, for universe selection.

    Reads the filing index only, so it is cheap. Pairs with `loupe ingest` to
    freeze the second half of the 25-company universe.
    """
    _logging(False)
    import json

    from loupe.sources import identity, us
    from loupe.sources import scan as scan_mod

    s = get_settings()
    us.set_cache_dir(s.cache_dir / "edgar")
    us.configure_identity(s.sec_user_agent)

    universe = identity.resolve_universe(
        s.companies_config, s.sec_user_agent, s.processed_dir / "tickers.json"
    )
    console.print(f"Scanning [bold]{len(universe)}[/] companies for 8-K risk items...")

    def progress(company, error=None):
        if error:
            console.print(f"  [yellow]{company.ticker}: {error}[/]")

    profiles = scan_mod.scan(universe, min_risk=min_risk, on_progress=progress)
    rows = [p.as_dict() for p in profiles[:limit]]

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(rows, indent=2))
        console.print(f"Wrote {len(rows)} rows to [bold]{output}[/]")
        return

    table = Table("ticker", "risk 8-Ks", "items", "latest")
    for row in rows:
        items = ", ".join(f"{k}x{v}" for k, v in row["items"].items())
        table.add_row(row["ticker"], str(row["risk_8k"]), items, row["latest"] or "")
    console.print(table)
    console.print(f"[dim]Scanned {len(universe)}; {len(profiles)} have >= {min_risk} risk 8-Ks.[/]")


@app.command("search")
def search_cmd(
    query: Annotated[str, typer.Argument(help="What to search for.")],
    company: Annotated[str | None, typer.Option(help="Restrict to one ticker.")] = None,
    top_k: Annotated[int, typer.Option(help="How many chunks to return.")] = 10,
    full: Annotated[bool, typer.Option(help="Print full chunk text.")] = False,
) -> None:
    """Search the ingested corpus and print cited chunks."""
    from loupe.index.search import load_chunks
    from loupe.store import db

    s = get_settings()
    conn = db.connect(s.duckdb_path, read_only=True)
    try:
        if not conn.execute("SELECT count(*) FROM chunks").fetchone()[0]:
            console.print("[yellow]No chunks yet. Run `loupe ingest` first.[/]")
            raise typer.Exit(1)
        index = load_chunks(conn)
        hits = index.search(query, top_k=top_k, company_id=company.upper() if company else None)
    finally:
        conn.close()

    if not hits:
        console.print(f"[yellow]No hits for {query!r}[/]")
        return

    for rank, hit in enumerate(hits, start=1):
        header = f"[bold]{rank}.[/] {hit.chunk_id}  [dim]score {hit.score:.4f}[/]"
        console.print(header)
        body = hit.text if full else hit.text[:320] + ("..." if len(hit.text) > 320 else "")
        console.print(body)
        console.print(f"   [dim]quote:[/] {hit.citation.quote[:200]}")
        console.print()


if __name__ == "__main__":
    app()
