"""Wires data, tools, models and orchestrators together: `Engine().ask(question, arm, model)`."""

import json
from functools import cached_property
from pathlib import Path

import yaml

from loupe.agent.tools import ToolBox
from loupe.core.schemas import Answer, Company
from loupe.core.settings import get_settings
from loupe.index.embed import FastEmbedder
from loupe.index.search import SearchIndex
from loupe.llm import Gateway, ModelRegistry
from loupe.orchestrators import ARMS, RunContext
from loupe.tools.facts import FactsStore, load_metrics

COMPANIES = Path("configs/companies_us.yaml")
METRICS = Path("configs/metrics.yaml")


class Engine:
    def __init__(self, index_variant: str | None = None):
        self.settings = get_settings()
        self._variant = index_variant

    @cached_property
    def companies(self) -> list[Company]:
        return [Company(**c) for c in yaml.safe_load(COMPANIES.read_text())["companies"]]

    @cached_property
    def gateway(self) -> Gateway:
        s = self.settings
        return Gateway(
            ModelRegistry.from_yaml(s.models_config),
            cache_dir=s.cache_dir,
            log_path=s.logs_dir / "llm_calls.jsonl",
        )

    @cached_property
    def index(self) -> SearchIndex:
        root = self.settings.data_dir / "processed" / "index"
        variant = self._variant or (root / "DEFAULT").read_text().strip()
        path = root / variant
        info = json.loads((path / "INFO.json").read_text())
        return SearchIndex.load(path, FastEmbedder(info["embedder"]))

    @cached_property
    def facts(self) -> FactsStore:
        db = self.settings.data_dir / "processed" / "loupe.duckdb"
        return FactsStore(db, load_metrics(METRICS), {c.id: c.cik for c in self.companies if c.cik})

    @cached_property
    def tools(self) -> ToolBox:
        return ToolBox(self.index, self.facts, self.companies)

    def ask(self, question: str, arm: str = "react", model: str = "groq-llama-70b") -> Answer:
        if arm not in ARMS:
            raise KeyError(f"Unknown arm {arm!r}; available: {', '.join(ARMS)}")
        ctx = RunContext(gateway=self.gateway, model=model, tools=self.tools)
        return ARMS[arm].run(question, ctx)
