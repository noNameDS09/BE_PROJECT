"""Run datasets x arms x models, score every answer, store the rows.

- Resumable: a (config, item) pair already stored without error is skipped, and the LLM
  cache makes any re-run free.
- Test-split guard: test items run only with final=True, and every final run is logged
  in docs/research-log.md (docs/hypotheses.md section 5).
- Modes: corpus (our SEC index), docs (the item's own documents, via a docs-<dataset>
  index), context (text given with the question; search is disabled).
"""

import json
import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from loupe.agent.tools import ToolBox
from loupe.core.jsonl import jsonl_lines
from loupe.core.schemas import Answer, Citation, RunConfig
from loupe.eval.judge import judge
from loupe.eval.metrics import numeric_correct, plan_scores, retrieval_recall, support_stats
from loupe.eval.schema import EvalItem, ResultRow
from loupe.eval.store import ResultStore
from loupe.index.embed import FastEmbedder
from loupe.index.retriever import RetrievalConfig, Retriever
from loupe.index.search import SearchFilter, SearchIndex
from loupe.orchestrators import ARMS, RunContext


class RunSpec(BaseModel):
    dataset: str
    arms: list[str]
    models: list[str]
    split: str | None = "dev"
    limit: int | None = None
    kinds: list[str] | None = None
    judge_model: str | None = None
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    tools_enabled: bool = True
    max_steps: int = 8
    final: bool = False
    seed: int = 20261013  # for limited (sampled) runs


def dataset_path(data_dir: Path, name: str) -> Path:
    gold = Path("data/gold") / f"{name}.jsonl"
    return gold if gold.exists() else data_dir / "processed" / "eval" / f"{name}.jsonl"


def load_items(data_dir: Path, name: str) -> list[EvalItem]:
    path = dataset_path(data_dir, name)
    if not path.exists():
        raise FileNotFoundError(f"No dataset file for {name!r} (looked for {path})")
    return [EvalItem.model_validate_json(line) for line in jsonl_lines(path)]


def select(items: list[EvalItem], spec: RunSpec) -> list[EvalItem]:
    out = [i for i in items if spec.split is None or i.split in (spec.split, None)]
    if spec.kinds:
        out = [i for i in out if i.kind in spec.kinds]
    if spec.split == "test" and not spec.final:
        raise PermissionError("Test-split runs need final=True (--final); see docs/hypotheses.md")
    if not spec.limit or len(out) <= spec.limit:
        return out
    # a limited run samples across companies (seeded round-robin), not the first N in file order
    rng = random.Random(spec.seed)
    groups: dict[str, list[EvalItem]] = {}
    for item in out:
        groups.setdefault(item.companies[0] if item.companies else "_", []).append(item)
    keys = sorted(groups)
    rng.shuffle(keys)
    for k in keys:
        rng.shuffle(groups[k])
    picked: list[EvalItem] = []
    while len(picked) < spec.limit:
        for k in keys:
            if groups[k] and len(picked) < spec.limit:
                picked.append(groups[k].pop())
    return picked


def config_for(spec: RunSpec, arm: str, model: str) -> RunConfig:
    return RunConfig(
        arm=arm,
        model=model,
        tools_enabled=spec.tools_enabled,
        toolset=getattr(ARMS[arm], "toolset", "harness"),
        retrieval={**spec.retrieval.model_dump(), "max_steps": spec.max_steps},
    )


def prepare(item: EvalItem, ctx: RunContext) -> str:
    """Question text for the arm, plus any context preloaded into the evidence ledger."""
    question = item.question
    if item.turns:
        question = (
            "Earlier questions in this conversation:\n"
            + "\n".join(f"- {t}" for t in item.turns)
            + (f"\n\nCurrent question: {item.question}")
        )
    if item.mode == "context" and item.context:
        ev = ctx.ledger.add("chunk", item.context, Citation(doc_id=item.item_id))
        question += f"\n\nContext [{ev.id}]:\n{item.context}"
    return question


def score(
    item: EvalItem,
    answer: Answer,
    judge_fn: Callable[[EvalItem, str], tuple[float | None, str]] | None,
):
    meta: dict = {}
    correct: float | None = None
    if item.kind == "numeric":
        correct = float(numeric_correct(answer.text, item))
    elif item.kind == "refusal":
        if answer.abstained:
            correct = 1.0
        elif judge_fn:
            correct, meta["judge_rationale"] = judge_fn(item, answer.text)
    elif item.kind == "text" and judge_fn:
        correct, meta["judge_rationale"] = judge_fn(item, answer.text)
    elif item.kind == "plan":
        meta.update(plan_scores(answer, item))
        correct = meta.get("tool_recall")
    supported_rate, hallucinated = support_stats(answer)
    return correct, supported_rate, hallucinated, retrieval_recall(answer, item), meta


class Runner:
    def __init__(self, engine, store: ResultStore, log: Path = Path("docs/research-log.md")):
        self.engine = engine
        self.store = store
        self.log = log
        self._docs_index: dict[str, SearchIndex] = {}

    def toolbox_for(self, item: EvalItem, spec: RunSpec) -> ToolBox:
        if item.mode == "corpus":
            return self.engine.tools(spec.retrieval)
        if item.mode == "context":  # the answer must come from the given context
            return ToolBox(None, self.engine.facts, self.engine.companies)  # type: ignore[arg-type]
        else:
            if item.dataset not in self._docs_index:
                path = (
                    self.engine.settings.data_dir / "processed" / "index" / f"docs-{item.dataset}"
                )
                if not (path / "INFO.json").exists():
                    raise FileNotFoundError(f"Run `loupe eval index-docs {item.dataset}` first")
                self._docs_index[item.dataset] = SearchIndex.load(path, FastEmbedder())
            index = self._docs_index[item.dataset]
            scope = SearchFilter(doc_ids=[d.doc_id for d in item.documents])
        retriever = Retriever(index, spec.retrieval, self.engine.reranker(spec.retrieval.rerank))
        return ToolBox(retriever, self.engine.facts, self.engine.companies, scope=scope)

    def run(
        self,
        spec: RunSpec,
        progress: Callable[[str], None] = lambda _: None,
        on_row: Callable[[ResultRow], None] = lambda _: None,
    ) -> list[ResultRow]:
        items = select(load_items(self.engine.settings.data_dir, spec.dataset), spec)
        judge_fn = None
        if spec.judge_model:

            def judge_fn(item: EvalItem, text: str):
                v = judge(self.engine.gateway, spec.judge_model, item, text)
                return v.score, v.rationale

        rows: list[ResultRow] = []
        for model in spec.models:
            for arm in spec.arms:
                cfg = config_for(spec, arm, model)
                h = cfg.config_hash()
                done = self.store.done(h)
                for n, item in enumerate(items, 1):
                    if item.item_id in done:
                        continue
                    progress(f"{arm} · {model} · {n}/{len(items)} {item.item_id}")
                    rows.append(self._one(item, arm, model, h, spec, judge_fn))
                    on_row(rows[-1])
        if spec.final:
            self._log_final(spec, len(rows))
        return rows

    def _one(self, item, arm, model, config_hash, spec, judge_fn) -> ResultRow:
        run_id = f"r_{uuid.uuid4().hex[:12]}"
        base = dict(run_id=run_id, item_id=item.item_id, dataset=item.dataset, arm=arm, model=model,
                    config_hash=config_hash, created_at=datetime.now(UTC))  # fmt: skip
        try:
            ctx = RunContext(
                gateway=self.engine.gateway,
                model=model,
                tools=self.toolbox_for(item, spec),
                tools_enabled=spec.tools_enabled,
                query_rewrite=spec.retrieval.query_rewrite == "multi",
                max_steps=spec.max_steps,
            )
            answer = ARMS[arm].run(prepare(item, ctx), ctx)
            correct, supported, halluc, recall, meta = score(item, answer, judge_fn)
            row = ResultRow(
                **base, answer=answer.text, correct=correct, supported_rate=supported,
                hallucinated=halluc, abstained=answer.abstained, retrieval_recall=recall,
                tokens=answer.tokens, latency_ms=answer.latency_ms, cost_usd=answer.cost_usd,
                meta={**meta, "kind": item.kind, "companies": item.companies, "split": item.split},
            )  # fmt: skip
        except Exception as exc:  # one failure must not stop a long run
            answer = None
            row = ResultRow(**base, answer="", error=f"{type(exc).__name__}: {exc}"[:500],
                            meta={"kind": item.kind, "companies": item.companies})  # fmt: skip
        self.store.add(row, answer)
        return row

    def _log_final(self, spec: RunSpec, n: int) -> None:
        line = (
            f"\n- {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · **FINAL** · dataset `{spec.dataset}` · "
            f"arms {', '.join(spec.arms)} · models {', '.join(spec.models)} · {n} new rows · "
            f"spec `{json.dumps(spec.model_dump(exclude={'final'}), default=str)}`\n"
        )
        with self.log.open("a") as f:
            f.write(line)
