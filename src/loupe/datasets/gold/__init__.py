"""Loupe-Gold: our own evaluation sets, built deterministically from XBRL facts and EDGAR.

Each builder takes a GoldContext and returns EvalItems; `loupe ... gold build` writes them to
data/gold/<set>.jsonl (versioned in git) and `gold verify` recomputes every item.
"""

from collections.abc import Callable
from pathlib import Path

from loupe.datasets.gold import calc, events, num, plan, trick
from loupe.datasets.gold.common import GOLD_DIR, GoldContext
from loupe.eval.schema import EvalItem

BUILDERS: dict[str, Callable[[GoldContext], list[EvalItem]]] = {
    num.NAME: num.build,
    calc.NAME: calc.build,
    trick.NAME: trick.build,
    events.NAME: events.build,
    plan.NAME: plan.build,
}


def write_items(path: Path, items: list[EvalItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")


def read_items(path: Path) -> list[EvalItem]:
    return [
        EvalItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]


__all__ = ["BUILDERS", "GOLD_DIR", "GoldContext", "read_items", "write_items"]
