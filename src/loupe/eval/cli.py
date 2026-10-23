"""`loupe eval ...`: run experiments, report results, index benchmark documents."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from loupe.core.settings import get_settings
from loupe.eval.report import leaderboard
from loupe.eval.runner import Runner, RunSpec, load_items, select
from loupe.eval.store import ResultStore
from loupe.index.retriever import RetrievalConfig

app = typer.Typer(
    no_args_is_help=True, help="Experiments: run, report, benchmark document indexes."
)
console = Console()


def store() -> ResultStore:
    settings = get_settings()
    d = settings.data_dir / "processed"
    return ResultStore(d / settings.results_db, d / "runs")


def _fmt(m: dict) -> str:
    if m.get("mean") is None:
        return "-"
    if m.get("lo") is None:
        return f"{m['mean']:.2f}"
    return f"{m['mean']:.2f} [{m['lo']:.2f}, {m['hi']:.2f}]"


def _log_row(r) -> None:
    ok = f"correct={r.correct} halluc={r.hallucinated}"
    outcome = f"ERROR {r.error[:120]}" if r.error else ok
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"{stamp} {r.dataset} {r.arm} {r.model} {r.item_id} {outcome}", flush=True)


@app.command("run")
def run(
    dataset: str,
    arm: Annotated[list[str], typer.Option(help="Arm(s); see `loupe arms`.")] = ["b0", "loupe"],  # noqa: B006
    model: Annotated[list[str], typer.Option(help="Model alias(es).")] = ["nim-nemotron-ultra"],  # noqa: B006
    split: Annotated[str, typer.Option(help="dev | test | all")] = "dev",
    limit: Annotated[int | None, typer.Option(help="Max items.")] = None,
    kind: Annotated[list[str] | None, typer.Option(help="Only these item kinds.")] = None,
    judge: Annotated[str | None, typer.Option(help="Judge model for text/refusal items.")] = None,
    rerank: Annotated[
        str | None, typer.Option(help="minilm-l12 | minilm-l6 | bge-base | none")
    ] = "minilm-l12",
    rewrite: Annotated[bool, typer.Option(help="Multi-query rewriting.")] = False,
    mode: Annotated[str, typer.Option(help="Retrieval: hybrid | dense | bm25")] = "hybrid",
    k: Annotated[int, typer.Option(help="Passages per search.")] = 8,
    tools: Annotated[bool, typer.Option(help="Number tools on/off.")] = True,
    final: Annotated[bool, typer.Option(help="Allow the test split (logged as FINAL).")] = False,
) -> None:
    """Run arms x models over a dataset (resumable; results go to the results store)."""
    from loupe.engine import Engine

    spec = RunSpec(
        dataset=dataset,
        arms=arm,
        models=model,
        split=None if split == "all" else split,
        limit=limit,
        kinds=kind,
        judge_model=judge,
        retrieval=RetrievalConfig(
            mode=mode,  # type: ignore[arg-type]
            k=k,
            rerank=None if rerank in (None, "none") else rerank,
            query_rewrite="multi" if rewrite else "none",
        ),
        tools_enabled=tools,
        final=final,
    )
    if judge and any(judge.split("-")[0] == m.split("-")[0] for m in model):
        console.print("[yellow]Warning: judge and a judged model share a provider family.[/]")
    runner = Runner(Engine(), store())
    if sys.stdout.isatty():
        with console.status("running") as status:
            rows = runner.run(spec, progress=status.update)
    else:  # detached run: one plain line per result, for the log file
        rows = runner.run(spec, on_row=_log_row)
    errors = [r for r in rows if r.error]
    console.print(f"[green]{len(rows)} new results[/] ({len(errors)} errors)")
    for r in errors[:5]:
        console.print(f"  [red]{r.item_id} {r.arm} {r.model}:[/] {r.error}")
    report(dataset=dataset)


@app.command("report")
def report(
    dataset: Annotated[str | None, typer.Option(help="Only this dataset.")] = None,
    model: Annotated[str | None, typer.Option(help="Only this model.")] = None,
) -> None:
    """Leaderboard with 95% cluster-bootstrap confidence intervals."""
    where, params = [], []
    if dataset:
        where.append("dataset = ?")
        params.append(dataset)
    if model:
        where.append("model = ?")
        params.append(model)
    rows = store().rows(("WHERE " + " AND ".join(where)) if where else "", params)
    table = Table(
        "dataset",
        "arm",
        "model",
        "n",
        "accuracy",
        "hallucination",
        "supported",
        "abstain",
        "tokens",
    )
    for r in leaderboard(rows):
        m = r["metrics"]
        table.add_row(
            r["dataset"],
            r["arm"],
            r["model"],
            str(r["n"]),
            _fmt(m["accuracy"]),
            _fmt(m["hallucination_rate"]),
            _fmt(m["supported_rate"]),
            _fmt(m["abstain_rate"]),
            f"{r['tokens']:,.0f}",
        )
    console.print(table)


@app.command("index-docs")
def index_docs(
    dataset: str,
    chunks_only: Annotated[
        bool, typer.Option(help="Only write chunks.jsonl (embed elsewhere, e.g. on a GPU).")
    ] = False,
) -> None:
    """Index the documents a benchmark ships with (FinanceBench PDFs, FinDER 10-Ks).

    With --chunks-only, writes data/processed/index/docs-<dataset>/chunks.jsonl for
    `loupe index build --from-chunks ... --out ...` on a GPU machine (docs/GPU-INDEX-BUILD.md)."""
    import hashlib

    from loupe.eval.docs_index import build_docs_index, collect_chunks
    from loupe.index.embed import FastEmbedder

    data = get_settings().data_dir
    items = [i for i in load_items(data, dataset) if i.mode == "docs"]
    if not items:
        raise typer.BadParameter(f"{dataset} has no docs-mode items")
    out = data / "processed" / "index" / f"docs-{dataset}"
    with console.status("indexing") as status:
        if chunks_only:
            chunks = collect_chunks(items, data, progress=status.update)
            out.mkdir(parents=True, exist_ok=True)
            path = out / "chunks.jsonl"
            with path.open("w") as f:
                for ch in chunks:
                    f.write(ch.model_dump_json() + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            console.print(f"[green]{len(chunks):,} chunks written to {path}[/]\nsha256 {digest}")
            return
        n = build_docs_index(items, data, out, FastEmbedder(), progress=status.update)
    console.print(f"[green]{n:,} chunks from {dataset} documents indexed in {out}[/]")


@app.command("export")
def export(
    out: Path,
    dataset: Annotated[str | None, typer.Option(help="Only this dataset.")] = None,
) -> None:
    """Export results (rows + stored answers) to a zip, to merge on another machine."""
    from loupe.eval.store import export_results

    where, params = ("WHERE dataset = ?", [dataset]) if dataset else ("", [])
    n = export_results(store(), out, where, params)
    console.print(f"[green]{n:,} results exported to {out}[/]")


@app.command("import")
def import_(archive: Path) -> None:
    """Merge results exported by a teammate (`loupe eval export`) into this store."""
    from loupe.eval.store import import_results

    n = import_results(store(), archive)
    console.print(f"[green]{n:,} results imported from {archive}[/]")


@app.command("retrieval")
def retrieval(
    dataset: str,
    index: Annotated[
        str | None, typer.Option(help="Index folder name (default: docs-<dataset> or DEFAULT).")
    ] = None,
    mode: Annotated[str, typer.Option(help="hybrid | dense | bm25")] = "hybrid",
    rerank: Annotated[
        str | None, typer.Option(help="minilm-l12 | minilm-l6 | bge-base | none")
    ] = "minilm-l12",
    candidates: Annotated[int, typer.Option(help="Pool size before reranking.")] = 40,
    split: Annotated[str, typer.Option(help="dev | test | all")] = "all",
    limit: Annotated[int | None, typer.Option(help="Max items (seeded sample).")] = None,
) -> None:
    """Retrieval-only evaluation against gold evidence: recall@k and MRR (no LLM calls)."""
    import json as _json

    from loupe.eval.retrieval import evaluate
    from loupe.index.embed import FastEmbedder
    from loupe.index.retriever import CrossEncoder, RetrievalConfig, Retriever
    from loupe.index.search import SearchIndex

    data = get_settings().data_dir
    root = data / "processed" / "index"
    items = load_items(data, dataset)
    docs_mode = any(i.mode == "docs" for i in items)
    name = index or (f"docs-{dataset}" if docs_mode else (root / "DEFAULT").read_text().strip())
    path = root / name
    info = _json.loads((path / "INFO.json").read_text())
    spec = RunSpec(
        dataset=dataset,
        arms=["-"],
        models=["-"],
        split=None if split == "all" else split,
        limit=limit,
    )
    chosen = select(items, spec)
    rr = None if rerank in (None, "none") else rerank
    cfg = RetrievalConfig(mode=mode, k=10, candidates=candidates, rerank=rr)  # type: ignore[arg-type]
    retriever = Retriever(
        SearchIndex.load(path, FastEmbedder(info["embedder"])),
        cfg,
        CrossEncoder(rr) if rr else None,
    )
    with console.status("searching") as status:
        scores = evaluate(chosen, retriever, progress=status.update)
    out = data / "processed" / "retrieval"
    out.mkdir(parents=True, exist_ok=True)
    tag = f"{dataset}__{name}__{mode}__{rr or 'norerank'}__c{candidates}"
    (out / f"{tag}.json").write_text(scores.model_dump_json(indent=1))
    table = Table(
        "dataset", "index", "mode", "rerank", "n", "R@1", "R@3", "R@5", "R@10", "MRR", "no match"
    )
    r = scores.recall_at
    table.add_row(
        dataset,
        name,
        mode,
        rr or "none",
        str(scores.n),
        f"{r[1]:.3f}",
        f"{r[3]:.3f}",
        f"{r[5]:.3f}",
        f"{r[10]:.3f}",
        f"{scores.mrr:.3f}",
        f"{scores.no_match:.3f}",
    )
    console.print(table)
    console.print(f"[dim]saved {out / (tag + '.json')}[/]")
