"""LLM judge for free-text and refusal items.

Used only where code can't decide. The judge model should come from a different family
than the model being judged (docs/hypotheses.md section 3); the runner warns when they
share a provider family. Every verdict keeps its rationale for the human audit.
"""

from pydantic import BaseModel

from loupe.eval.schema import EvalItem
from loupe.llm.gateway import Gateway
from loupe.orchestrators.base import parse_json

TEXT_RUBRIC = """You grade an answer to a question about company financial filings against a gold
answer.
Score 1 if the answer contains the gold answer's key facts (numbers may be rounded or in other
units) and nothing that contradicts it; 0.5 if partly correct or incomplete; 0 if wrong,
contradicting, or it fails to answer. Ignore citation markers like [E1] and style.
Return JSON {"score": 0|0.5|1, "rationale": "<one sentence>"}."""

REFUSAL_RUBRIC = """The question below is a trick: it asks about something that is not in the
filings, is in the future, or rests on a false premise. The expected behaviour is described.
Score 1 if the answer declines, says the information is not available, or corrects the premise;
0 if it answers as if the premise were true or invents information.
Return JSON {"score": 0|1, "rationale": "<one sentence>"}."""


class Verdict(BaseModel):
    score: float | None
    rationale: str = ""
    judge: str = ""


def judge(gateway: Gateway, judge_model: str, item: EvalItem, answer: str) -> Verdict:
    rubric = REFUSAL_RUBRIC if item.kind == "refusal" else TEXT_RUBRIC
    user = (
        f"Question: {item.question}\n\n"
        f"{'Expected behaviour' if item.kind == 'refusal' else 'Gold answer'}: {item.answer}\n\n"
        f"Answer to grade:\n{answer}"
    )
    c = gateway.complete(
        judge_model,
        [{"role": "system", "content": rubric}, {"role": "user", "content": user}],
        json_mode=True,
        max_tokens=1500,
    )
    out = parse_json(c.text)
    if not isinstance(out, dict):
        return Verdict(
            score=None,
            rationale=f"unparseable judge output: {str(c.text)[:120]}",
            judge=judge_model,
        )
    try:
        score = float(out.get("score"))
    except (TypeError, ValueError):
        score = None
    if score is not None:
        score = min((0.0, 0.5, 1.0), key=lambda s: abs(s - score))
    return Verdict(score=score, rationale=str(out.get("rationale", ""))[:500], judge=judge_model)
