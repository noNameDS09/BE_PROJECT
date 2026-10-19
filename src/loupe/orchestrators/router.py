"""O4: router to one specialist agent, as in FARE (Chakraborty et al., IEEE Access 2026).

An orchestrator prompt maps the question to exactly ONE intent (ambiguous questions go
to the dominant intent); that specialist then answers with its own role prompt and a
restricted toolset. Single-intent routing is FARE's design choice and the main thing
Loupe-Orch changes (multi-intent routing plus planning).
"""

from loupe.core.schemas import Answer
from loupe.orchestrators.base import CITED_RULES, RunContext
from loupe.orchestrators.react import tool_loop

INTENTS = ["lookup", "calc", "compare", "event", "trend", "forecast", "chart", "open_analysis"]

SPECIALISTS: dict[str, tuple[str, list[str]]] = {
    "lookup": ("Statement extraction analyst: find the exact reported fact.",
               ["get_financial_metric", "search_filings"]),
    "calc": ("Quantitative analyst: compute ratios and changes from reported numbers.",
             ["get_financial_metric", "calculate", "search_filings"]),
    "compare": ("Comparison analyst: compare companies on one topic or metric.",
                ["compare_companies", "get_financial_metric", "calculate", "search_filings"]),
    "event": ("Disclosure analyst: material events reported on Form 8-K.",
              ["list_events", "search_filings"]),
    "trend": ("Trend analyst: how a metric moved over time and why.",
              ["make_chart", "get_financial_metric", "calculate", "search_filings"]),
    "forecast": ("Projection analyst: statistical projections with stated uncertainty.",
                 ["forecast_metric", "get_financial_metric", "search_filings"]),
    "chart": ("Visualisation analyst: build the requested chart from reported numbers.",
              ["make_chart", "get_financial_metric"]),
    "open_analysis": ("Risk analyst: qualitative questions about risks, strategy and outlook.",
                      ["search_filings", "get_financial_metric", "distress_score", "list_events"]),
}  # fmt: skip

ROUTER = (
    "Classify the user's question about SEC filings into exactly ONE intent from: "
    + ", ".join(INTENTS)
    + '. If several apply, choose the dominant one. Return JSON {"intent": "..."}.'
)


class Router:
    name = "router"
    label = "O4 · Router → specialist (FARE)"
    description = (
        "Route the question to exactly one specialist agent with its own prompt and tools."
    )

    def run(self, question: str, ctx: RunContext) -> Answer:
        out = ctx.llm_json("route", ROUTER, question, 50)
        intent = out.get("intent") if isinstance(out, dict) else None
        if intent not in SPECIALISTS:
            intent = "open_analysis"
        role, tools = SPECIALISTS[intent]
        system = f"You are a {role}\n{CITED_RULES}"
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]
        return ctx.finish(tool_loop(ctx, messages, tools))
