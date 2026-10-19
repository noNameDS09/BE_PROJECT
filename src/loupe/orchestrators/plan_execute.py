"""O3: Plan-and-Execute in the ReWOO style (Wang et al. 2023; Xu et al. 2023).

1. Planner: writes every tool call up front as JSON steps. Later steps may refer to an
   earlier step's number as "#1", "#2" (e.g. calculate "pct_change(#1, #2)").
2. Worker: runs the steps in order with no model in the loop, substituting numbers.
3. Solver: answers from the step results, citing evidence ids.
The planner never sees tool outputs, which is what makes ReWOO cheap and also its
main weakness on questions whose next step depends on what was found.
"""

import json
import re
from typing import Any

from loupe.core.schemas import Answer
from loupe.orchestrators.base import CITED_RULES, RunContext

REF = re.compile(r"#(\d+)")
FIRST_ID = re.compile(r"\[(E\d+)\]")


def tool_catalogue(ctx: RunContext, names: list[str] | None = None) -> str:
    lines = []
    for spec in ctx.specs(names):
        f = spec["function"]
        params = ", ".join(
            f"{k}{'' if k in f['parameters'].get('required', []) else '?'}"
            for k in f["parameters"]["properties"]
        )
        lines.append(f"- {f['name']}({params}): {f['description']}")
    metrics = ", ".join(ctx.tools.metric_names)
    companies = ", ".join(c.id for c in ctx.tools.companies)
    return "\n".join(lines) + f"\nMetrics: {metrics}\nCompanies: {companies}"


PLANNER = """You plan tool calls to answer a question about SEC filings. You will NOT see the
results, so plan every step now. Return JSON:
{{"plan": [{{"step": 1, "tool": "<name>", "args": {{...}}, "why": "<short>"}}, ...]}}
A later step can use an earlier step's number by writing "#<step>" inside a string argument,
e.g. {{"tool": "calculate", "args": {{"expression": "pct_change(#1, #2)"}}}}.
Use at most {max_steps} steps. Tools:
{tools}"""

SOLVER = "You answer the question from the results of a plan that was executed.\n" + CITED_RULES


def substitute(value: Any, numbers: dict[int, float]) -> Any:
    if isinstance(value, str):
        return REF.sub(
            lambda m: repr(numbers[int(m.group(1))]) if int(m.group(1)) in numbers else m.group(0),
            value,
        )
    if isinstance(value, dict):
        return {k: substitute(v, numbers) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, numbers) for v in value]
    return value


def execute_plan(ctx: RunContext, plan: list[dict[str, Any]]) -> list[str]:
    numbers: dict[int, float] = {}
    results = []
    for n, step in enumerate(plan, 1):
        sid = int(step.get("step", n)) if str(step.get("step", n)).isdigit() else n
        tool = str(step.get("tool", ""))
        args = substitute(step.get("args") or {}, numbers)
        out = ctx.tool(tool, args if isinstance(args, dict) else {})
        match = FIRST_ID.search(out)
        if match and (ev := ctx.ledger.get(match.group(1))) and ev.value is not None:
            numbers[sid] = ev.value
        results.append(f"Step {sid} {tool}({json.dumps(args)}):\n{out}")
    return results


class PlanExecute:
    name = "plan_execute"
    label = "O3 · Plan-and-Execute (ReWOO)"
    description = (
        "Plan every tool call up front, run them without the model, then solve from the results."
    )

    def run(self, question: str, ctx: RunContext) -> Answer:
        out = ctx.llm_json(
            "plan",
            PLANNER.format(max_steps=ctx.max_steps, tools=tool_catalogue(ctx)),
            question,
            4000,
        )
        plan = out.get("plan", []) if isinstance(out, dict) else []
        plan = [s for s in plan if isinstance(s, dict)][: ctx.max_steps]
        results = execute_plan(ctx, plan) if plan else ["(the planner returned no usable plan)"]
        c = ctx.llm(
            "answer",
            [
                {"role": "system", "content": SOLVER},
                {
                    "role": "user",
                    "content": "Results:\n\n" + "\n\n".join(results) + f"\n\nQuestion: {question}",
                },
            ],
        )
        return ctx.finish(c.text or "")
