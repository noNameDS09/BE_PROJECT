"""Data contracts shared by every stage.

Source adapters (US, India) produce Documents, Facts and Events in these shapes;
everything downstream depends only on these types, never on a source's raw format.
"""

import hashlib
import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Company(BaseModel):
    id: str  # ticker (US) or NSE symbol (India)
    name: str
    country: Literal["US", "IN"]
    cik: str | None = None
    isin: str | None = None
    sector: str | None = None
    split: Literal["dev", "test"] | None = None


class Section(BaseModel):
    section_id: str
    doc_id: str
    title: str
    item: str | None = None  # e.g. "1A", "7", "2.02"
    start_char: int
    end_char: int


class Document(BaseModel):
    doc_id: str
    company_id: str
    source: str  # e.g. "sec_edgar", "nse"
    form: str  # e.g. "10-K", "8-K", "announcement"
    url: str
    content_hash: str
    accession: str | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None  # "FY", "Q1".."Q4"
    period_end: date | None = None
    filed_at: datetime | None = None
    sections: list[Section] = Field(default_factory=list)


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    company_id: str
    text: str
    start_char: int
    end_char: int
    section_id: str | None = None
    page: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Fact(BaseModel):
    fact_id: str
    company_id: str
    concept: str  # e.g. "us-gaap:Revenues"
    value: float
    unit: str  # e.g. "USD", "shares", "INR"
    period_end: date
    period_start: date | None = None
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    form: str | None = None
    accession: str | None = None
    source_url: str | None = None


class Citation(BaseModel):
    doc_id: str | None = None
    chunk_id: str | None = None
    fact_id: str | None = None
    quote: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    url: str | None = None
    page: int | None = None  # 0-indexed PDF page, for bring-your-own-docs benchmarks
    verified: bool | None = None  # set by the verifier, never by the model


class Event(BaseModel):
    event_id: str
    company_id: str
    event_type: str  # taxonomy label
    label_source: str  # e.g. "8k_item", "nse_category", "llm"
    doc_id: str
    quote: str
    occurred_on: date | None = None
    quote_match_score: float | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    quality_score: int | None = Field(default=None, ge=1, le=5)


class Claim(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)
    supported: bool | None = None


class TraceStep(BaseModel):
    stage: str  # e.g. "route", "plan", "tool", "compose", "verify"
    name: str
    input: Any = None
    output: Any = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


class Answer(BaseModel):
    text: str
    claims: list[Claim] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)  # Plotly specs
    abstained: bool = False
    trace: list[TraceStep] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)  # the run's ledger, for the UI

    @property
    def tokens(self) -> int:
        return sum(s.tokens_in + s.tokens_out for s in self.trace)

    @property
    def latency_ms(self) -> int:
        return sum(s.latency_ms for s in self.trace)

    @property
    def cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.trace)


class RunConfig(BaseModel):
    arm: str  # "b0", "o1".."o5", "loupe"
    model: str  # alias from configs/models.yaml
    tools_enabled: bool = True
    retrieval: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int = 2048

    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]


class EvalRecord(BaseModel):
    run_id: str
    dataset: str
    item_id: str
    config_hash: str
    metrics: dict[str, float]
    judge: str | None = None
    created_at: datetime
