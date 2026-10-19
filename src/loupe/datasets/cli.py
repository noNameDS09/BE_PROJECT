"""`convert` public datasets to EvalItems, `stats` on them, and `gold build | verify` Loupe-Gold.

Registered by the main CLI as a sub-app; also runnable as `python -m loupe.datasets.cli`.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from loupe.core.settings import get_settings
from loupe.datasets.gold import BUILDERS, GOLD_DIR, GoldContext, read_items, write_items
from loupe.datasets.gold.verify import VERIFIERS
from loupe.datasets.loaders import LOADERS
from loupe.eval.schema import EvalItem

app = typer.Typer(no_args_is_help=True, help="Evaluation sets: public datasets and Loupe-Gold.")
gold_app = typer.Typer(no_args_is_help=True, help="Loupe-Gold sets in data/gold/.")
app.add_typer(gold_app, name="gold")
console = Console()
KINDS = ("numeric", "text", "refusal", "event", "plan", "retrieval")


def _eval_dir() -> Path:
    return get_settings().data_dir / "processed" / "eval"


def numeric_candidate(item: EvalItem) -> bool:
    """A short gold answer with a digit that is not a list or a bare year: what the numeric
    parser should be able to read (denominator of the parse rate)."""
    a = (item.answer or "").strip()
    return (
        bool(a)
        and len(a.split()) <= 4
        and any(ch.isdigit() for ch in a)
        and ";" not in a
        and not re.fullmatch(r"(19|20)\d\d", a)
    )


def parse_rate(items: list[EvalItem]) -> tuple[int, int]:
    """(numeric items, numeric-looking answers); numeric items count even if not short."""
    cands = [i for i in items if i.kind == "numeric" or (i.kind == "text" and numeric_candidate(i))]
    return sum(i.kind == "numeric" for i in cands), len(cands)


def _check_unique(items: list[EvalItem], name: str) -> None:
    dupes = [k for k, v in Counter(i.item_id for i in items).items() if v > 1]
    if dupes:
        raise typer.BadParameter(f"{name}: {len(dupes)} duplicate item_ids, e.g. {dupes[:3]}")


def _kind_row(name: str, items: list[EvalItem]) -> list[str]:
    kinds = Counter(i.kind for i in items)
    n, d = parse_rate(items)
    rate = f"{n}/{d} ({n / d:.0%})" if d else "-"
    return [name, str(len(items)), *[str(kinds.get(k, "")) for k in KINDS], rate]


@app.command("convert")
def convert(
    names: Annotated[list[str] | None, typer.Argument(help="Datasets (default: all).")] = None,
) -> None:
    """Convert raw public datasets into data/processed/eval/<name>.jsonl (EvalItem per line)."""
    unknown = set(names or []) - LOADERS.keys()
    if unknown:
        raise typer.BadParameter(f"unknown datasets: {', '.join(sorted(unknown))}")
    raw = get_settings().data_dir / "raw" / "public"
    out = _eval_dir()
    table = Table("dataset", "items", *KINDS, "numeric parsed")
    for name in names or list(LOADERS):
        folder = raw / name
        if not folder.exists():
            console.print(f"[yellow]{name}: not downloaded ({folder})[/]")
            continue
        with console.status(f"converting {name}"):
            items = list(LOADERS[name](folder))
        _check_unique(items, name)
        write_items(out / f"{name}.jsonl", items)
        table.add_row(*_kind_row(name, items))
    console.print(table)
    console.print(f"[green]Wrote to {out}[/]")


@app.command("stats")
def stats(
    names: Annotated[list[str] | None, typer.Argument(help="Datasets (default: all).")] = None,
    gold: Annotated[bool, typer.Option(help="Also include Loupe-Gold sets.")] = True,
) -> None:
    """Counts per dataset by kind, split and category (converted public sets + Loupe-Gold)."""
    paths = sorted(_eval_dir().glob("*.jsonl")) + (sorted(GOLD_DIR.glob("*.jsonl")) if gold else [])
    paths = [p for p in paths if not names or p.stem in names]
    table = Table("dataset", "items", *KINDS, "numeric parsed")
    details = []
    for path in paths:
        items = read_items(path)
        table.add_row(*_kind_row(path.stem, items))
        splits = Counter(i.split or "-" for i in items)
        cats = Counter(i.category or "-" for i in items).most_common(8)
        details.append(
            f"[bold]{path.stem}[/] split {dict(splits)} · categories "
            + ", ".join(f"{c} {n}" for c, n in cats)
        )
    console.print(table)
    for line in details:
        console.print(line, highlight=False)


@gold_app.command("build")
def gold_build(
    sets: Annotated[list[str] | None, typer.Argument(help="Gold sets (default: all).")] = None,
    out: Annotated[Path, typer.Option(help="Output folder.")] = GOLD_DIR,
) -> None:
    """Build Loupe-Gold sets from XBRL facts and the SEC manifest into data/gold/."""
    unknown = set(sets or []) - BUILDERS.keys()
    if unknown:
        raise typer.BadParameter(f"unknown sets: {', '.join(sorted(unknown))}")
    ctx = GoldContext.open(get_settings().data_dir)
    table = Table("set", "items", "dev", "test", "categories")
    for name in sets or list(BUILDERS):
        with console.status(f"building {name}"):
            items = BUILDERS[name](ctx)
        _check_unique(items, name)
        write_items(out / f"{name}.jsonl", items)
        splits = Counter(i.split for i in items)
        cats = Counter(i.category for i in items)
        top = ", ".join(f"{c} {n}" for c, n in cats.most_common(6))
        table.add_row(name, str(len(items)), str(splits["dev"]), str(splits["test"]), top)
    console.print(table)
    console.print(f"[green]Wrote to {out}[/]")


@gold_app.command("verify")
def gold_verify(
    sets: Annotated[list[str] | None, typer.Argument(help="Gold sets (default: all).")] = None,
    folder: Annotated[Path, typer.Option(help="Gold folder.")] = GOLD_DIR,
) -> None:
    """Recompute every gold item from the data and report mismatches (exit 1 if any)."""
    ctx = GoldContext.open(get_settings().data_dir)
    table = Table("set", "items", "mismatches")
    failures: list[str] = []
    for name in sets or list(VERIFIERS):
        path = folder / f"{name}.jsonl"
        if not path.exists():
            console.print(f"[yellow]{name}: {path} missing[/]")
            failures.append(f"{name}: missing")
            continue
        items = read_items(path)
        errs = VERIFIERS[name](ctx, items)
        dupes = [k for k, v in Counter(i.item_id for i in items).items() if v > 1]
        errs += [f"{name}: duplicate item_id {d}" for d in dupes]
        failures += errs
        table.add_row(name, str(len(items)), f"[{'red' if errs else 'green'}]{len(errs)}[/]")
    console.print(table)
    for e in failures[:50]:
        console.print(f"  [red]{e}[/]", highlight=False)
    if failures:
        raise typer.Exit(1)


@app.command("show")
def show(item_id: str) -> None:
    """Print one item (from data/processed/eval or data/gold) as JSON."""
    dataset = item_id.split(":", 1)[0]
    for path in (_eval_dir() / f"{dataset}.jsonl", GOLD_DIR / f"{dataset}.jsonl"):
        if path.exists():
            for item in read_items(path):
                if item.item_id == item_id:
                    data = item.model_dump(mode="json")
                    if data.get("context") and len(data["context"]) > 2000:
                        data["context"] = data["context"][:2000] + " ..."
                    console.print_json(json.dumps(data))
                    return
    raise typer.BadParameter(f"{item_id} not found")


if __name__ == "__main__":
    app()
