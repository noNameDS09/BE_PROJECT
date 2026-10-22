"""Loupe-Orch v1: the orchestration this project proposes (docs/hypotheses.md, section 2).

1. Router    multi-label intents + companies + fiscal years (unlike FARE's single intent)
2. Planner   ReWOO-style typed plan, only for multi-step questions; simple ones use a short
             tool loop restricted to the intents' tools
3. Executors deterministic tools; retrieval filtered by the routed companies and years
4. Composer  writes the answer as claims, each citing evidence ids
5. Verifier  (a) code: numbers and quotes must match cited evidence
             (b) critic: flags claims the evidence does not support
             one revision; claims still failing the code check are removed
6. Abstain   if nothing verifiable remains, say what is missing instead of guessing

Each component can be switched off for the ablation study (RQ3).
"""

from dataclasses import dataclass

from loupe.agent.verify import cited_ids, found_in, verify
from loupe.core.schemas import Answer
from loupe.orchestrators.base import CITED_RULES, RunContext
from loupe.orchestrators.plan_execute import PLANNER, execute_plan, tool_catalogue
from loupe.orchestrators.react import tool_loop
from loupe.orchestrators.router import INTENTS, SPECIALISTS

ROUTE = (
    "Analyse a question about SEC filings of US companies. Return JSON:\n"
    '{"intents": [one or more of ' + ", ".join(f'"{i}"' for i in INTENTS) + "],\n"
    ' "companies": [tickers or company names mentioned], "fiscal_years": [integers],'
    ' "multi_step": true|false}\n'
    "multi_step is true when answering needs several dependent lookups or calculations."
)

COMPOSE = (
    "Write the final answer from the evidence below. Each sentence that states a fact must cite "
    "the evidence ids it relies on, e.g. [E3]. Be concise and specific; give numbers with units "
    "exactly as in the evidence (rounding is fine).\n" + CITED_RULES
)

CRITIC = (
    "For each numbered claim, decide whether its cited evidence supports it. Return JSON "
    '{"unsupported": [claim numbers], "missing": "what the answer still lacks, or empty"}.'
)

PLANNED_INTENTS = {"calc", "compare", "trend", "forecast", "chart"}


@dataclass
class LoupeOrch:
    name: str = "loupe"
    label: str = "Loupe-Orch v1 (ours)"
    description: str = (
        "Multi-intent router → planner when needed → tools → composer → "
        "verifier + critic → abstain."
    )
    use_router: bool = True
    use_planner: bool = True
    use_code_verifier: bool = True
    use_critic: bool = True
    use_abstain: bool = True
    toolset: str = "harness"  # "generic" = Loupe's orchestration without our financial tools

    def _route(self, question: str, ctx: RunContext) -> dict:
        if not self.use_router:
            return {"intents": INTENTS, "companies": [], "fiscal_years": [], "multi_step": True}
        out = ctx.llm_json("route", ROUTE, question, 2000)
        out = out if isinstance(out, dict) else {}
        intents = [i for i in out.get("intents", []) if i in INTENTS] or ["open_analysis"]
        known = {c.id: c for c in ctx.tools.companies}
        names = {c.name.lower(): c.id for c in ctx.tools.companies}
        companies, unknown = [], []
        for raw in out.get("companies", []) or []:
            key = str(raw).upper().strip()
            match = (
                key
                if key in known
                else next((t for n, t in names.items() if str(raw).lower() in n), None)
            )
            (companies if match else unknown).append(match or str(raw))
        years = [int(y) for y in out.get("fiscal_years", []) or [] if str(y).isdigit()]
        return {"intents": intents, "companies": companies, "unknown": unknown,
                "fiscal_years": years, "multi_step": bool(out.get("multi_step"))}  # fmt: skip

    def _tools_for(self, intents: list[str]) -> list[str]:
        names: list[str] = []
        for i in intents:
            names += [t for t in SPECIALISTS[i][1] if t not in names]
        return names

    def _gather(self, question: str, route: dict, ctx: RunContext) -> None:
        tools = self._tools_for(route["intents"])
        hint = ""
        if route["companies"]:
            hint += f"\nCompanies (tickers): {', '.join(route['companies'])}."
        if route["fiscal_years"]:
            hint += f"\nFiscal years: {', '.join(map(str, route['fiscal_years']))}."
        planned = self.use_planner and (route["multi_step"] or len(route["intents"]) > 1
                                        or PLANNED_INTENTS & set(route["intents"]))  # fmt: skip
        if planned:
            out = ctx.llm_json(
                "plan", PLANNER.format(max_steps=ctx.max_steps, tools=tool_catalogue(ctx, tools)),
                question + hint, 4000,
            )  # fmt: skip
            plan = out.get("plan", []) if isinstance(out, dict) else []
            plan = [s for s in plan if isinstance(s, dict) and s.get("tool") in tools][
                : ctx.max_steps
            ]
            if plan:
                execute_plan(ctx, plan)
                return
        system = (
            "Gather the evidence needed to answer. Call tools; when you have enough, reply DONE.\n"
            "Filter searches by the companies and periods in the question."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question + hint},
        ]
        tool_loop(ctx, messages, tools, max_steps=5)

    def _compose(self, question: str, ctx: RunContext, feedback: str = "") -> str:
        evidence = "\n".join(f"[{e.id}] {e.text[:900]}" for e in ctx.ledger.items.values())
        user = f"Evidence:\n{evidence or '(none)'}\n\nQuestion: {question}"
        if feedback:
            user += (
                f"\n\nA checker found problems in your previous answer:\n{feedback}\n"
                "Fix or remove them."
            )
        c = ctx.llm(
            "compose", [{"role": "system", "content": COMPOSE}, {"role": "user", "content": user}]
        )
        return c.text or ""

    def _abstain_text(self, question: str, route: dict) -> str:
        who = (
            ", ".join(route.get("companies") or route.get("unknown") or [])
            or "the companies asked about"
        )
        return (
            f"I could not find evidence in the SEC filings or XBRL data to answer this for {who}. "
            "The answer is not reported in the documents available, so I will not estimate it."
        )

    def run(self, question: str, ctx: RunContext) -> Answer:
        ctx.use_toolset(self.toolset)
        route = self._route(question, ctx)
        if self.use_abstain and route.get("unknown") and not route["companies"]:
            return ctx.finish(
                f"{', '.join(route['unknown'])} is not among the companies covered by this corpus, "
                "so there is no filing evidence to answer from."
            )
        self._gather(question, route, ctx)
        answer = self._compose(question, ctx)

        claims = verify(answer, ctx.ledger)
        bad = [c.text for c in claims if c.supported is False] if self.use_code_verifier else []
        hints = {b: _cite_hint(b, ctx) for b in bad}
        if self.use_critic:
            numbered = "\n".join(f"{i}. {c.text}" for i, c in enumerate(claims, 1))
            cited = "\n".join(f"[{e.id}] {e.text[:500]}" for e in ctx.ledger.items.values())
            review = ctx.llm_json(
                "critique", CRITIC, f"Claims:\n{numbered}\n\nEvidence:\n{cited}", 2000
            )
            if isinstance(review, dict):
                for n in review.get("unsupported", []) or []:
                    if (
                        isinstance(n, int)
                        and 1 <= n <= len(claims)
                        and claims[n - 1].text not in bad
                    ):
                        bad.append(claims[n - 1].text)
                if review.get("missing"):
                    bad.append(f"Missing: {review['missing']}")
        removed: list[str] = []
        if bad:
            feedback = "\n".join(f"- {b}{hints.get(b, '')}" for b in bad)
            answer = self._compose(question, ctx, feedback)
            if self.use_code_verifier:
                revised = verify(answer, ctx.ledger)
                removed = [c.text for c in revised if c.supported is False]
                answer = " ".join(c.text for c in revised if c.supported is not False)
        if self.use_abstain and not answer.strip():
            answer = self._abstain_text(question, route)
        return ctx.finish(answer, removed=removed)


def _cite_hint(sentence: str, ctx: RunContext) -> str:
    """Point a failed claim at the evidence that does hold its numbers, if any."""
    ids = [i for i in found_in(sentence, ctx.ledger) if i not in cited_ids(sentence)]
    if not ids:
        return ""
    return f" (these numbers are in {', '.join(f'[{i}]' for i in ids[:3])}; cite that instead)"


ABLATIONS = {
    "loupe-no-router": LoupeOrch(
        name="loupe-no-router", label="Loupe minus router", use_router=False
    ),
    "loupe-no-planner": LoupeOrch(
        name="loupe-no-planner", label="Loupe minus planner", use_planner=False
    ),
    "loupe-no-verifier": LoupeOrch(
        name="loupe-no-verifier", label="Loupe minus code verifier", use_code_verifier=False
    ),
    "loupe-no-critic": LoupeOrch(
        name="loupe-no-critic", label="Loupe minus critic", use_critic=False
    ),
    "loupe-no-abstain": LoupeOrch(
        name="loupe-no-abstain", label="Loupe minus abstain", use_abstain=False
    ),
    "loupe-generic-tools": LoupeOrch(
        name="loupe-generic-tools",
        label="Loupe minus harness (generic tools)",
        description="Loupe's orchestration with only the baselines' generic tools.",
        toolset="generic",
    ),
}
