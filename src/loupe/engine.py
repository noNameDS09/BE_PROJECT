"""Wires data, tools, models and orchestrators together: `Engine().ask(question, arm, model)`."""

import json
from functools import cached_property
from pathlib import Path

import yaml

from loupe.agent.tools import ToolBox
from loupe.core.schemas import Answer, Company
from loupe.core.settings import get_settings
from loupe.index.embed import FastEmbedder
from loupe.index.retriever import CrossEncoder, RetrievalConfig, Retriever
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
        self._rerankers: dict[str, CrossEncoder] = {}

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
    def index_path(self) -> Path:
        root = self.settings.data_dir / "processed" / "index"
        return root / (self._variant or (root / "DEFAULT").read_text().strip())

    @cached_property
    def index(self) -> SearchIndex:
        info = json.loads((self.index_path / "INFO.json").read_text())
        return SearchIndex.load(self.index_path, FastEmbedder(info["embedder"]))

    @cached_property
    def facts(self) -> FactsStore:
        db = self.settings.data_dir / "processed" / "loupe.duckdb"
        return FactsStore(db, load_metrics(METRICS), {c.id: c.cik for c in self.companies if c.cik})

    def reranker(self, name: str | None) -> CrossEncoder | None:
        if not name:
            return None
        if name not in self._rerankers:
            self._rerankers[name] = CrossEncoder(name)
        return self._rerankers[name]

    def tools(self, retrieval: RetrievalConfig | None = None) -> ToolBox:
        cfg = retrieval or RetrievalConfig()
        retriever = Retriever(self.index, cfg, self.reranker(cfg.rerank))
        return ToolBox(retriever, self.facts, self.companies)

    def context(
        self,
        model: str,
        retrieval: RetrievalConfig | None = None,
        tools_enabled: bool = True,
        max_steps: int = 8,
    ) -> RunContext:
        cfg = retrieval or RetrievalConfig()
        return RunContext(
            gateway=self.gateway,
            model=model,
            tools=self.tools(cfg),
            tools_enabled=tools_enabled,
            query_rewrite=cfg.query_rewrite == "multi",
            max_steps=max_steps,
        )

    def ask(
        self,
        question: str,
        arm: str = "loupe",
        model: str = "nim-nemotron-super",
        retrieval: RetrievalConfig | None = None,
        tools_enabled: bool = True,
    ) -> Answer:
        if arm not in ARMS:
            raise KeyError(f"Unknown arm {arm!r}; available: {', '.join(ARMS)}")
        return ARMS[arm].run(question, self.context(model, retrieval, tools_enabled))
