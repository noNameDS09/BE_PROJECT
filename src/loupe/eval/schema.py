"""One format for every evaluation question, public or our own.

Loaders turn each public dataset into EvalItems; Loupe-Gold builders produce the same
shape. The runner, metrics, judge, API and Bench UI only ever see EvalItems.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal[
    "numeric",  # one number is the answer (checked by code with a tolerance)
    "text",  # free-text answer (checked by an LLM judge against the gold answer)
    "refusal",  # correct behaviour is to refuse or correct a false premise
    "event",  # 8-K event extraction: type + fields + quote
    "plan",  # expected intents / tool sequence (router and planner scoring)
    "retrieval",  # gold evidence passages only (retrieval metrics)
]


class EvalDoc(BaseModel):
    """A document that ships with the question (bring-your-own-docs mode)."""

    doc_id: str
    title: str = ""
    text: str | None = None
    path: str | None = None  # e.g. a FinanceBench PDF, relative to the data dir


class GoldEvidence(BaseModel):
    doc_id: str | None = None
    page: int | None = None  # 0-indexed page for PDFs
    text: str | None = None
    accession: str | None = None
    item: str | None = None


class EvalItem(BaseModel):
    item_id: str  # "<dataset>:<native id>", unique across all sets
    dataset: str
    question: str
    kind: Kind
    answer: str | None = None  # gold answer as text
    answer_value: float | None = None  # gold number, in base units (USD, %, ratio...)
    answer_unit: str | None = None
    tolerance: float = 0.01  # relative tolerance for numeric answers
    mode: Literal["corpus", "docs", "context"] = "corpus"  # context = text given inline
    context: str | None = None  # inline context (FinQA/TAT-QA/FailSafeQA style)
    documents: list[EvalDoc] = Field(default_factory=list)
    evidence: list[GoldEvidence] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    fiscal_year: int | None = None
    turns: list[str] = Field(default_factory=list)  # earlier questions in a conversation
    expected_tools: list[str] = Field(default_factory=list)
    expected_intents: list[str] = Field(default_factory=list)
    split: Literal["dev", "test"] | None = None
    category: str | None = None  # dataset's own question type, for per-category results
    meta: dict[str, Any] = Field(default_factory=dict)


class ResultRow(BaseModel):
    """One (item, arm, model) run, as stored in the results table."""

    run_id: str
    item_id: str
    dataset: str
    arm: str
    model: str
    config_hash: str
    answer: str
    correct: float | None = None  # 1/0 for numeric and refusal, judge score 0..1 for text
    supported_rate: float | None = None  # verified claims / checkable claims
    hallucinated: bool | None = None  # any unsupported checkable claim
    abstained: bool = False
    retrieval_recall: float | None = None
    tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    created_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)
