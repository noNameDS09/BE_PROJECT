"""O2: ReAct (Yao et al., ICLR 2023) with native tool calling.

The model alternates between calling tools and reading their results until it writes
a final answer, or the step budget runs out and it is asked to answer with what it has.
"""

import json

from loupe.core.schemas import Answer
from loupe.orchestrators.base import CITED_RULES, RunContext


class ReAct:
    name = "react"
    SYSTEM = (
        "You are a financial analyst with tools over SEC filings and exact XBRL numbers for "
        "these companies. Think about what you need, call tools, read the results, and repeat "
        "until you can answer.\n" + CITED_RULES
    )

    def run(self, question: str, ctx: RunContext) -> Answer:
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user", "content": question},
        ]
        specs = ctx.tools.specs()
        for _ in range(ctx.max_steps):
            c = ctx.llm("step", messages, tools=specs)
            if not c.tool_calls:
                return ctx.finish(c.text or "")
            messages.append(
                {
                    "role": "assistant",
                    "content": c.text,
                    "tool_calls": [
                        {
                            "id": tc.id or f"call_{i}",
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for i, tc in enumerate(c.tool_calls)
                    ],
                }
            )
            for i, tc in enumerate(c.tool_calls):
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id or f"call_{i}",
                        "content": ctx.tool(tc.name, tc.arguments),
                    }
                )
        messages.append(
            {
                "role": "user",
                "content": "Step budget used up. Answer now from the evidence you have.",
            }
        )
        return ctx.finish(ctx.llm("answer", messages).text or "")
