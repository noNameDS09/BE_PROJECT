"""Shared pieces for every orchestration arm.

All arms get the same model, retriever and token cap per question. Tools differ on
purpose (decision D21): published baselines get only the generic tools any agent
framework ships (filing search, a calculator, the company list), while Loupe gets the
financial harness we built (XBRL facts, comparisons, charts, forecasts, distress score,
8-K events). The `loupe-generic-tools` ablation runs Loupe's orchestration with the
generic tools, separating the harness's effect from the orchestration's.
"""

import json
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
- Take numbers from tool results (metrics, calculations, forecasts), never from memory. Show units.
- If the evidence does not answer the question, say exactly what is missing instead of guessing.
- If the question contains a false premise, say so and correct it from the evidence.
- Analysis only: never recommend buying, selling or holding a security."""

ABSTAIN = re.compile(
    r"\b(not (?:reported|available|found|disclosed|stated|mentioned)|"
    r"no (?:evidence|information|data|record|indication|mention)|"
    r"(?:does|do|did) not (?:contain|mention|indicate|show|include|report|support)|"
    r"(?:has|have|had) not (?:filed|reported|disclosed|announced)|"
    r"(?:cannot|can't|could not|unable to) (?:find|determine|answer|confirm|verify)|"
    r"insufficient (?:evidence|information)|false premise|premise is (?:false|incorrect))\b",
    re.I,
)

# "tools off" ablation: the model may read filings but must do every number itself
TEXT_ONLY_TOOLS = ["search_filings", "list_companies", "list_events"]

# what a standard agent framework provides; everything else in the ToolBox is our harness
GENERIC_TOOLS = ["search_filings", "calculate", "list_companies"]
TOOLSETS: dict[str, list[str] | None] = {"harness": None, "generic": GENERIC_TOOLS, "none": []}


def parse_json(text: str | None) -> Any:
    """First JSON object or array in a model reply (tolerates code fences and chatter)."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    starts = [i for i in (candidate.find("{"), candidate.find("[")) if i != -1]
    if not starts:
        return None
    start = min(starts)
    closer = "}" if candidate[start] == "{" else "]"
    end = candidate.rfind(closer)
    if end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


@dataclass
class RunContext:
    gateway: Gateway
    model: str
    tools: ToolBox
    # reasoning models spend output tokens thinking before they answer: keep caps generous
    max_tokens: int = 4000
    max_steps: int = 8
    tools_enabled: bool = True
    query_rewrite: bool = False
    allowed_tools: list[str] | None = None  # None = the full harness
    ledger: Ledger = field(default_factory=Ledger)
    trace: list[TraceStep] = field(default_factory=list)

    def use_toolset(self, toolset: str) -> None:
        self.allowed_tools = TOOLSETS[toolset]

    def allows(self, name: str) -> bool:
        if not self.tools_enabled and name not in TEXT_ONLY_TOOLS:
            return False
        return self.allowed_tools is None or name in self.allowed_tools

    def specs(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        allowed = (
            names
            if self.tools_enabled
            else [n for n in (names or TEXT_ONLY_TOOLS) if n in TEXT_ONLY_TOOLS]
        )
        if self.allowed_tools is not None:
            wanted = allowed if allowed is not None else self.allowed_tools
            # a specialist whose harness tools are all unavailable falls back to the generic set
            allowed = [n for n in wanted if n in self.allowed_tools] or list(self.allowed_tools)
        return self.tools.specs(allowed)

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

    def llm_json(self, stage: str, system: str, user: str, max_tokens: int = 2000) -> Any:
        c = self.llm(
            stage,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            json_mode=True,
            max_tokens=max_tokens,
        )
        return parse_json(c.text)

    def rewrite(self, query: str) -> list[str]:
        out = self.llm_json(
            "rewrite",
            'You rewrite search queries for SEC filings. Return JSON {"queries": [3 strings]}: '
            "alternative phrasings using the terms filings use (e.g. 'net revenue', 'Item 1A').",
            query,
            max_tokens=1500,
        )
        queries = out.get("queries", []) if isinstance(out, dict) else []
        return [q for q in queries if isinstance(q, str) and q.strip()][:3]

    def tool(self, name: str, args: dict[str, Any]) -> str:
        if not self.allows(name):
            out = f"ERROR: tool {name} is not available in this configuration."
        else:
            if name == "search_filings" and self.query_rewrite and "query" in args:
                args = {**args, "extra_queries": self.rewrite(args["query"])}
            out = self.tools.call(name, args, self.ledger)
        self.trace.append(TraceStep(stage="tool", name=name, input=args, output=out[:2000]))
        return out

    def finish(self, text: str, removed: list[str] | None = None) -> Answer:
        claims = verify(text, self.ledger)
        # declining = the answer says the information is missing AND verifies no fact itself
        abstained = bool(ABSTAIN.search(text)) and not any(c.supported for c in claims)
        return Answer(
            text=text,
            claims=claims,
            abstained=abstained,
            charts=list(self.ledger.charts),
            trace=self.trace,
            evidence=[e.model_dump() for e in self.ledger.items.values()],
            removed_claims=removed or [],
        )


class Orchestrator(Protocol):
    name: str
    label: str
    description: str
    toolset: str  # "harness" | "generic" | "none"

    def run(self, question: str, ctx: RunContext) -> Answer: ...
