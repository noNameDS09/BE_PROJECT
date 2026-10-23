"""HTTP API for the Loupe Bench (docs/api.md). Run with `loupe serve`.

The engine, indexes and databases are loaded once and shared. Model runs are serialised
with a lock: the free-tier gateway throttles per provider anyway, and DuckDB connections
must not be used from two threads at once.
"""

import json
import threading
import uuid
from functools import cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from loupe.agent.tools import TOOL_SPECS
from loupe.api.models import (
    ArmInfo,
    ChatRequest,
    CompanyInfo,
    CompareRequest,
    CompareResponse,
    ConfigResponse,
    DatasetInfo,
    DocumentResponse,
    Gold,
    ItemsResponse,
    LeaderboardResponse,
    ModelInfo,
    OpenRouterModel,
    OpenRouterModelsResponse,
    RunRequest,
    RunResult,
    RunsResponse,
    StagesResponse,
)
from loupe.core.jsonl import jsonl_lines
from loupe.core.schemas import Document
from loupe.eval.report import leaderboard, stages
from loupe.eval.runner import Runner, RunSpec, prepare, score
from loupe.eval.schema import EvalItem, ResultRow
from loupe.eval.store import ResultStore
from loupe.orchestrators import ARMS, RunContext
from loupe.orchestrators.base import TOOLSETS

app = FastAPI(title="Loupe API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_lock = threading.Lock()


@cache
def engine():
    from loupe.engine import Engine

    return Engine(patient=False)  # live requests: quick retries, then a visible error


@cache
def store() -> ResultStore:
    settings = engine().settings
    d = settings.data_dir / "processed"
    return ResultStore(d / settings.results_db, d / "runs")


@cache
def runner() -> Runner:
    return Runner(engine(), store())


def _dataset_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    for p in sorted((engine().settings.data_dir / "processed" / "eval").glob("*.jsonl")):
        files[p.stem] = p
    for p in sorted(Path("data/gold").glob("*.jsonl")):
        files[p.stem] = p  # our gold sets win on name clashes
    return files


@cache
def _items(name: str) -> list[EvalItem]:
    path = _dataset_files().get(name)
    if path is None:
        raise HTTPException(404, f"unknown dataset {name}")
    return [EvalItem.model_validate_json(x) for x in jsonl_lines(path)]


def _find_item(item_id: str) -> EvalItem:
    dataset = item_id.split(":", 1)[0]
    for it in _items(dataset):
        if it.item_id == item_id:
            return it
    raise HTTPException(404, f"unknown item {item_id}")


@cache
def _documents() -> dict[str, Document]:
    path = engine().settings.data_dir / "processed" / "sec" / "documents.jsonl"
    docs = (Document.model_validate_json(x) for x in jsonl_lines(path))
    return {d.doc_id: d for d in docs}


# --- endpoints ----------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    e = engine()
    models = e.gateway.registry.all()
    try:
        index = e.index_path.name
    except FileNotFoundError:
        index = None
    return {
        "ok": True,
        "index": index,
        "models_with_keys": sum(m.missing_key() is None for m in models),
    }


def arm_tools(toolset: str) -> list[str]:
    allowed = TOOLSETS[toolset]
    return [t["function"]["name"] for t in TOOL_SPECS] if allowed is None else list(allowed)


@app.get("/api/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    e = engine()
    datasets = []
    for name in _dataset_files():
        items = _items(name)
        datasets.append(
            DatasetInfo(name=name, items=len(items), kinds=sorted({i.kind for i in items}))
        )
    return ConfigResponse(
        arms=[
            ArmInfo(
                name=a.name,
                label=a.label,
                description=a.description,
                toolset=a.toolset,
                tools=arm_tools(a.toolset),
            )
            for a in ARMS.values()
        ],
        models=[
            ModelInfo(
                alias=m.alias, provider=m.provider, model=m.model, available=m.missing_key() is None
            )
            for m in e.gateway.registry.all()
        ],
        datasets=datasets,
        companies=[
            CompanyInfo(id=c.id, name=c.name, sector=c.sector, split=c.split, group=c.group)
            for c in e.companies
        ],
    )


def _run(question: str | None, arm: str, model: str, item_id: str | None) -> RunResult:
    if arm not in ARMS:
        raise HTTPException(400, f"unknown arm {arm}; see /api/config")
    item = _find_item(item_id) if item_id else None
    if item is None and not question:
        raise HTTPException(400, "question or item_id is required")
    q = question or item.question  # type: ignore[union-attr]
    run_id = f"r_{uuid.uuid4().hex[:12]}"
    try:
        with _lock:
            e = engine()
            if item is not None:
                spec = RunSpec(dataset=item.dataset, arms=[arm], models=[model])
                ctx = RunContext(
                    gateway=e.gateway, model=model, tools=runner().toolbox_for(item, spec)
                )
                answer = ARMS[arm].run(prepare(item, ctx), ctx)
                correct, *_ = score(item, answer, None)
                gold = Gold(answer=item.answer, correct=correct)
            else:
                answer = ARMS[arm].run(q, e.context(model))
                gold = None
    except HTTPException:
        raise
    except Exception as exc:
        return RunResult(run_id=run_id, arm=arm, model=model, question=q, answer=None,
                         error=f"{type(exc).__name__}: {exc}"[:500])  # fmt: skip
    empty = None
    if not answer.text.strip():
        last = answer.trace[-1] if answer.trace else None
        budget = last is not None and last.tokens_out >= 3900
        empty = ("The model returned an empty answer" + (
            ": it used its whole output budget reasoning without writing one. Try another model."
            if budget else "."))  # fmt: skip
    return RunResult(
        run_id=run_id, arm=arm, model=model, question=q, answer=answer, tokens=answer.tokens,
        latency_ms=answer.latency_ms, cost_usd=answer.cost_usd, gold=gold, error=empty,
    )  # fmt: skip


@app.post("/api/runs", response_model=RunResult)
def run(req: RunRequest) -> RunResult:
    return _run(req.question, req.arm, req.model, req.item_id)


@app.post("/api/compare", response_model=CompareResponse)
def compare(req: CompareRequest) -> CompareResponse:
    if not req.configs:
        raise HTTPException(400, "at least one config is required")
    return CompareResponse(
        results=[_run(req.question, c.arm, c.model, req.item_id) for c in req.configs]
    )


@app.post("/api/chat", response_model=RunResult)
def chat(req: ChatRequest) -> RunResult:
    users = [m for m in req.messages if m.role == "user"]
    if not users:
        raise HTTPException(400, "no user message")
    history = req.messages[:-1][-8:]
    question = users[-1].content
    if history:
        convo = "\n".join(f"{m.role}: {m.content[:800]}" for m in history)
        question = f"Conversation so far:\n{convo}\n\nCurrent question: {question}"
    return _run(question, req.arm, req.model, None)


_openrouter_cache: dict[str, OpenRouterModelsResponse] = {}


@app.get("/api/openrouter/models", response_model=OpenRouterModelsResponse)
def openrouter_models(free_only: bool = True, refresh: bool = False) -> OpenRouterModelsResponse:
    """OpenRouter's live model list (cached for an hour), for the Bench's model picker."""
    import time

    import httpx

    key = f"free={free_only}"
    cached = _openrouter_cache.get(key)
    if cached and not refresh and time.time() - cached.fetched_at < 3600:
        return cached
    try:
        data = httpx.get("https://openrouter.ai/api/v1/models", timeout=20).json()["data"]
    except Exception as exc:
        if cached:
            return cached
        raise HTTPException(502, f"could not reach OpenRouter: {type(exc).__name__}") from exc
    models = []
    for m in data:
        pricing = m.get("pricing") or {}
        free = m["id"].endswith(":free") or (
            str(pricing.get("prompt")) == "0" and str(pricing.get("completion")) == "0"
        )
        if free_only and not free:
            continue
        models.append(OpenRouterModel(
            alias=f"openrouter/{m['id']}", id=m["id"], name=m.get("name") or m["id"],
            context_length=m.get("context_length"),
            tools="tools" in (m.get("supported_parameters") or []), free=free,
        ))  # fmt: skip
    models.sort(key=lambda m: (not m.tools, m.name.lower()))
    result = OpenRouterModelsResponse(models=models, fetched_at=time.time())
    _openrouter_cache[key] = result
    return result


@app.get("/api/datasets/{name}/items", response_model=ItemsResponse)
def dataset_items(
    name: str,
    offset: int = 0,
    limit: int = Query(50, le=500),
    split: str | None = None,
    kind: str | None = None,
    q: str | None = None,
) -> ItemsResponse:
    items = _items(name)
    if split:
        items = [i for i in items if i.split == split]
    if kind:
        items = [i for i in items if i.kind == kind]
    if q:
        needle = q.lower()
        items = [
            i
            for i in items
            if needle in i.question.lower() or needle in " ".join(i.companies).lower()
        ]
    return ItemsResponse(total=len(items), items=items[offset : offset + limit])


@app.get("/api/datasets/{name}/items/{item_id}", response_model=EvalItem)
def dataset_item(name: str, item_id: str) -> EvalItem:
    return _find_item(item_id)


def _where(**filters) -> tuple[str, list]:
    clauses, params = [], []
    for col, val in filters.items():
        if val is not None:
            clauses.append(f"{col} = ?")
            params.append(val)
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


@app.get("/api/results/leaderboard", response_model=LeaderboardResponse)
def results_leaderboard(
    dataset: str | None = None,
    split: str | None = None,
    model: str | None = None,
    arm: str | None = None,
) -> LeaderboardResponse:
    where, params = _where(dataset=dataset, model=model, arm=arm)
    rows = store().rows(where, params)
    if split:
        rows = [r for r in rows if (json.loads(r["meta"] or "{}") if isinstance(r["meta"], str)
                                    else r["meta"] or {}).get("split") == split]  # fmt: skip
    return LeaderboardResponse(rows=leaderboard(rows))


@app.get("/api/results/stages", response_model=StagesResponse)
def results_stages(dataset: str | None = None, model: str | None = None) -> StagesResponse:
    where, params = _where(dataset=dataset, model=model)
    return StagesResponse(steps=stages(store().rows(where, params)))


@app.get("/api/results/runs", response_model=RunsResponse)
def results_runs(
    dataset: str | None = None,
    arm: str | None = None,
    model: str | None = None,
    correct: bool | None = None,
    limit: int = Query(50, le=500),
) -> RunsResponse:
    where, params = _where(dataset=dataset, arm=arm, model=model)
    rows = store().rows(where + " ORDER BY created_at DESC", params)
    if correct is not None:
        rows = [r for r in rows if r["correct"] is not None and (r["correct"] >= 0.5) == correct]
    out = []
    for r in rows[:limit]:
        r = dict(r)
        r["meta"] = json.loads(r["meta"]) if isinstance(r["meta"], str) else (r["meta"] or {})
        answer = store().answer(r["run_id"])  # full answer for the Runs drill-down
        if answer is not None:
            r["meta"]["answer"] = answer.model_dump()
        out.append(ResultRow(**r))
    return RunsResponse(rows=out)


@app.get("/api/results/runs/{run_id}/answer")
def results_answer(run_id: str):
    answer = store().answer(run_id)
    if answer is None:
        raise HTTPException(404, f"no stored answer for {run_id}")
    return answer


@app.get("/api/documents/{doc_id}", response_model=DocumentResponse)
def document(doc_id: str, start: int | None = None, end: int | None = None, context: int = 600):
    doc = _documents().get(doc_id)
    if doc is None:
        raise HTTPException(404, f"unknown document {doc_id}")
    text = (engine().settings.data_dir / "processed" / "sec" / "text" / f"{doc_id}.txt").read_text()
    if start is not None and end is not None:
        lo, hi = max(0, start - context), min(len(text), end + context)
        snippet, highlight = text[lo:hi], [start - lo, end - lo]
    else:
        snippet, highlight = text[:20000], None
    return DocumentResponse(
        doc_id=doc_id, company_id=doc.company_id, form=doc.form,
        period_end=doc.period_end.isoformat() if doc.period_end else None,
        url=doc.url, text=snippet, highlight=highlight,
    )  # fmt: skip


def mount_web(dist: Path = Path("web/dist")) -> None:
    """Serve the built React app at / when it exists (after `npm run build`)."""
    if dist.exists() and not any(getattr(r, "path", "") == "/" for r in app.routes):
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
