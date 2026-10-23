"""Request/response models for the HTTP API. Mirrors docs/api.md; keep both in sync."""

from typing import Any

from pydantic import BaseModel, Field

from loupe.core.schemas import Answer
from loupe.eval.schema import EvalItem, ResultRow


class ArmInfo(BaseModel):
    name: str
    label: str
    description: str
    toolset: str = "harness"  # "harness" (ours) | "generic" | "none" (decision D21)
    tools: list[str] = []  # tool names this arm may call


class ModelInfo(BaseModel):
    alias: str
    provider: str
    available: bool
    model: str = ""  # provider's model id


class DatasetInfo(BaseModel):
    name: str
    items: int
    kinds: list[str]


class CompanyInfo(BaseModel):
    id: str
    name: str
    sector: str | None
    group: str | None = None
    split: str | None = None


class ConfigResponse(BaseModel):
    arms: list[ArmInfo]
    models: list[ModelInfo]
    datasets: list[DatasetInfo]
    companies: list[CompanyInfo]


class RunRequest(BaseModel):
    question: str | None = None
    arm: str = "loupe"
    model: str
    item_id: str | None = None


class ConfigChoice(BaseModel):
    arm: str
    model: str


class CompareRequest(BaseModel):
    question: str | None = None
    item_id: str | None = None
    configs: list[ConfigChoice] = Field(max_length=4)


class Gold(BaseModel):
    answer: str | None
    correct: float | None


class RunResult(BaseModel):
    run_id: str
    arm: str
    model: str
    question: str
    answer: Answer | None
    tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    gold: Gold | None = None
    error: str | None = None


class CompareResponse(BaseModel):
    results: list[RunResult]


class ItemsResponse(BaseModel):
    total: int
    items: list[EvalItem]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str
    arm: str = "loupe"


class OpenRouterModel(BaseModel):
    alias: str  # "openrouter/<id>", usable anywhere a model alias is
    id: str
    name: str
    context_length: int | None = None
    tools: bool = False  # supports tool calling (needed by agent methods)
    free: bool = True


class OpenRouterModelsResponse(BaseModel):
    models: list[OpenRouterModel]
    fetched_at: float


class DocumentResponse(BaseModel):
    doc_id: str
    company_id: str
    form: str
    period_end: str | None
    url: str
    text: str
    highlight: list[int] | None = None


class LeaderboardResponse(BaseModel):
    rows: list[dict[str, Any]]


class StagesResponse(BaseModel):
    steps: list[dict[str, Any]]


class RunsResponse(BaseModel):
    rows: list[ResultRow]
