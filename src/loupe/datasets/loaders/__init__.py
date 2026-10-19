"""Public evaluation datasets -> EvalItems (src/loupe/eval/schema.py).

Each loader takes that dataset's raw folder (data/raw/public/<name>/) and yields EvalItems.
Only evaluation splits are read (never training splits).
"""

from collections.abc import Callable, Iterator
from pathlib import Path

from loupe.datasets.loaders import (
    convfinqa,
    failsafeqa,
    finance_agent,
    financebench,
    finder,
    finqa,
    indfin_bench,
    indiafinbench,
    secque,
    tatqa,
)
from loupe.eval.schema import EvalItem

Loader = Callable[[Path], Iterator[EvalItem]]

LOADERS: dict[str, Loader] = {
    "financebench": financebench.load,
    "finder": finder.load,
    "failsafeqa": failsafeqa.load,
    "secque": secque.load,
    **finance_agent.LOADERS,
    "finqa": finqa.load,
    "convfinqa": convfinqa.load,
    "tatqa": tatqa.load,
    "indfin_bench": indfin_bench.load,
    "indiafinbench": indiafinbench.load,
}

__all__ = ["LOADERS", "Loader"]
