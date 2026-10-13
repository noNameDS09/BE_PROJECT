"""Command-line entry point: `loupe ...`."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from loupe.core.settings import get_settings
from loupe.llm import Gateway, ModelRegistry
from loupe.llm.check import probe

app = typer.Typer(no_args_is_help=True, help="Loupe research toolkit.")
models_app = typer.Typer(no_args_is_help=True, help="LLM model registry.")
app.add_typer(models_app, name="models")
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


if __name__ == "__main__":
    app()
