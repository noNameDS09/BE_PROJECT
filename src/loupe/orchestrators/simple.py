"""Baselines B0 (model alone) and O1 (single-shot RAG)."""

from loupe.core.schemas import Answer
from loupe.orchestrators.base import CITED_RULES, RunContext


class ClosedBook:
    """B0: the model answers from what it already knows. Shows how much it makes up."""

    name = "b0"
    SYSTEM = (
        "You are a financial analyst. Answer the question about the company accurately and "
        "specifically, with exact numbers where asked. Analysis only, no investment advice."
    )

    def run(self, question: str, ctx: RunContext) -> Answer:
        c = ctx.llm(
            "answer",
            [{"role": "system", "content": self.SYSTEM}, {"role": "user", "content": question}],
        )
        return ctx.finish(c.text or "")


class SingleShotRAG:
    """O1: retrieve the top-k passages for the question once, answer once."""

    name = "rag"
    SYSTEM = (
        "You are a financial analyst answering questions from SEC filing passages.\n" + CITED_RULES
    )

    def run(self, question: str, ctx: RunContext) -> Answer:
        passages = ctx.tool("search_filings", {"query": question})
        c = ctx.llm(
            "answer",
            [
                {"role": "system", "content": self.SYSTEM},
                {"role": "user", "content": f"Passages:\n\n{passages}\n\nQuestion: {question}"},
            ],
        )
        return ctx.finish(c.text or "")
