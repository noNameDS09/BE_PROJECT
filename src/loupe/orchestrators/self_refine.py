"""O5: ReAct plus a Self-Refine critic (Madaan et al., NeurIPS 2023).

The same model drafts an answer with tools, critiques its own draft against the
evidence it gathered, and revises once (it may call tools again while revising).
"""

from loupe.core.schemas import Answer
from loupe.orchestrators.base import RunContext
from loupe.orchestrators.react import ReAct, tool_loop

CRITIC = """You review a draft answer about SEC filings against the evidence it cites.
List concrete problems: claims not supported by the cited evidence, wrong numbers or units,
missing citations, parts of the question left unanswered, investment advice.
Return JSON {"ok": true|false, "issues": ["..."]}."""


class SelfRefine:
    name = "self_refine"
    label = "O5 · ReAct + Self-Refine"
    toolset = "generic"
    description = "Draft with generic tools, critique the draft against its evidence, revise once."

    def run(self, question: str, ctx: RunContext) -> Answer:
        ctx.use_toolset(self.toolset)
        messages = [
            {"role": "system", "content": ReAct.SYSTEM},
            {"role": "user", "content": question},
        ]
        draft = tool_loop(ctx, messages)
        evidence = "\n".join(f"[{e.id}] {e.text[:600]}" for e in ctx.ledger.items.values())
        review = ctx.llm_json(
            "critique",
            CRITIC,
            f"Question: {question}\n\nDraft:\n{draft}\n\nEvidence:\n{evidence}",
            2000,
        )
        if not isinstance(review, dict) or review.get("ok", True) or not review.get("issues"):
            return ctx.finish(draft)
        issues = "\n".join(f"- {i}" for i in review["issues"] if isinstance(i, str))
        messages += [
            {"role": "assistant", "content": draft},
            {
                "role": "user",
                "content": f"A reviewer found these problems:\n{issues}\n"
                "Revise the answer. Use tools if you need more evidence.",
            },
        ]  # fmt: skip
        return ctx.finish(tool_loop(ctx, messages, max_steps=4))
