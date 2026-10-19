"""Shared pieces for every orchestration arm.

All arms get the same model, tools and token cap per question, so differences in the
results come from the orchestration alone (docs/hypotheses.md, section 1).
"""

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from loupe.agent.evidence import Ledger
from loupe.agent.tools import ToolBox
from loupe.agent.verify import verify
from loupe.core.schemas import Answer, TraceStep
from loupe.llm.gateway import Completion, Gateway

CITED_RULES = """Rules:
- Use only the evidence you were given or retrieved with tools. Do not use outside knowledge.
- After every sentence that states a fact, cite its evidence ids in brackets, e.g. [E2] or [E1][E4].
- Take numbers from get_financial_metric or calculate results, never from memory. Show units.
- If the evidence does not answer the question, say exactly what is missing instead of guessing.
- Analysis only: never recommend buying, selling or holding a security."""

ABSTAIN = re.compile(
    r"\b(not (?:reported|available|found|disclosed)|no (?:evidence|information|data)|"
    r"(?:cannot|can't|unable to) (?:find|determine|answer)|"
    r"insufficient (?:evidence|information))\b",
    re.I,
)


@dataclass
class RunContext:
    gateway: Gateway
    model: str
    tools: ToolBox
    max_tokens: int = 1500
    max_steps: int = 8
    ledger: Ledger = field(default_factory=Ledger)
    trace: list[TraceStep] = field(default_factory=list)

    def llm(self, stage: str, messages: list[dict[str, Any]], **kw: Any) -> Completion:
        c = self.gateway.complete(
            self.model, messages, max_tokens=kw.pop("max_tokens", self.max_tokens), **kw
        )
        self.trace.append(
            TraceStep(
                stage=stage,
                name=self.model,
                input=messages[-1].get("content") if messages else None,
                output=c.text if c.text is not None else [t.model_dump() for t in c.tool_calls],
                model=c.model,
                tokens_in=c.tokens_in,
                tokens_out=c.tokens_out,
                latency_ms=c.latency_ms,
                cost_usd=c.cost_usd,
            )
        )
        return c

    def tool(self, name: str, args: dict[str, Any]) -> str:
        out = self.tools.call(name, args, self.ledger)
        self.trace.append(TraceStep(stage="tool", name=name, input=args, output=out[:2000]))
        return out

    def finish(self, text: str) -> Answer:
        return Answer(
            text=text,
            claims=verify(text, self.ledger),
            abstained=bool(ABSTAIN.search(text)),
            trace=self.trace,
            evidence=[e.model_dump() for e in self.ledger.items.values()],
        )


class Orchestrator(Protocol):
    name: str

    def run(self, question: str, ctx: RunContext) -> Answer: ...
