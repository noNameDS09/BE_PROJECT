"""Scoring one answer against one EvalItem. Code first; the LLM judge only where code can't decide.

- numeric:   correct if any number in the answer equals the gold value within the item's
             relative tolerance (also accepting the same value written in thousands,
             millions, billions, or a percentage written as a fraction).
- refusal:   correct if the answer declines or corrects the premise (abstain detector,
             then the judge for anything the detector can't tell).
- text:      judge score 0 / 0.5 / 1 against the gold answer.
- retrieval: recall of the gold evidence among the passages the run retrieved.
- plan:      tool-set recall/precision against expected_tools.
Hallucination and support come from the code verifier's claims, for every kind.
"""

from loupe.agent.verify import parse_numbers
from loupe.core.schemas import Answer
from loupe.eval.schema import EvalItem

SCALES = (1, 1e3, 1e6, 1e9, 1e-2, 1e2)


def numeric_correct(answer: str, item: EvalItem) -> bool:
    if item.answer_value is None:
        return False
    gold = item.answer_value
    tol = max(abs(gold) * item.tolerance, 1e-9)
    for n in parse_numbers(answer):
        for s in SCALES:
            if (
                abs(n.value * s - gold) <= tol
                or abs(n.value - gold * s) <= abs(gold * s) * item.tolerance
            ):
                return True
    return False


def support_stats(answer: Answer) -> tuple[float | None, bool | None]:
    """(share of checkable claims supported, whether any checkable claim is unsupported)."""
    checked = [c for c in answer.claims if c.supported is not None]
    if not checked:
        return None, None
    ok = sum(bool(c.supported) for c in checked)
    return ok / len(checked), ok < len(checked)


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def retrieval_recall(answer: Answer, item: EvalItem) -> float | None:
    """Share of gold evidence items found among the chunks the run retrieved."""
    if not item.evidence:
        return None
    chunks = [e for e in answer.evidence if e.get("kind") == "chunk"]
    found = 0
    for gold in item.evidence:
        for ev in chunks:
            cit = ev.get("citation") or {}
            meta_page = cit.get("page")
            same_doc = gold.doc_id is None or cit.get("doc_id") == gold.doc_id
            if gold.page is not None and same_doc and meta_page == gold.page:
                found += 1
                break
            if gold.text and same_doc:
                g = _norm(gold.text)[:300]
                if g and (
                    g[:120] in _norm(ev.get("text", "")) or _norm(ev.get("text", ""))[:120] in g
                ):
                    found += 1
                    break
            if gold.accession and gold.accession in (cit.get("doc_id") or ""):
                found += 1
                break
    return found / len(item.evidence)


def plan_scores(answer: Answer, item: EvalItem) -> dict[str, float]:
    if not item.expected_tools:
        return {}
    used = {s.name for s in answer.trace if s.stage == "tool"}
    want = set(item.expected_tools)
    recall = len(used & want) / len(want)
    precision = len(used & want) / len(used) if used else 0.0
    return {"tool_recall": recall, "tool_precision": precision}
