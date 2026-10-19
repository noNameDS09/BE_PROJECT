"""Aggregate stored results into leaderboard rows and the B0 → Loupe stage waterfall."""

from collections import defaultdict
from typing import Any

from loupe.eval.stats import Estimate, cluster_bootstrap

STAGE_ORDER = [
    ("b0", "B0 · model alone"),
    ("rag", "O1 · + retrieval (single-shot RAG)"),
    ("react", "O2 · + tools in a loop (ReAct)"),
    ("plan_execute", "O3 · planning (ReWOO)"),
    ("router", "O4 · routing to one specialist (FARE)"),
    ("self_refine", "O5 · + self-critique"),
    ("loupe", "Loupe-Orch v1"),
    ("loupe-no-router", "Loupe minus router"),
    ("loupe-no-planner", "Loupe minus planner"),
    ("loupe-no-verifier", "Loupe minus code verifier"),
    ("loupe-no-critic", "Loupe minus critic"),
    ("loupe-no-abstain", "Loupe minus abstain"),
]


def _cluster(row: dict[str, Any]) -> str:
    meta = row.get("meta") or {}
    if isinstance(meta, str):
        import json

        meta = json.loads(meta)
    companies = meta.get("companies") or []
    return companies[0] if companies else row["item_id"]


def _metric(rows: list[dict], key: str, transform=float) -> Estimate:
    values = [None if r[key] is None else transform(r[key]) for r in rows]
    return cluster_bootstrap(values, [_cluster(r) for r in rows])


def leaderboard(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("error"):
            continue
        groups[(r["arm"], r["model"], r["dataset"])].append(r)
    out = []
    for (arm, model, dataset), rs in sorted(groups.items()):
        out.append(
            {
                "arm": arm,
                "model": model,
                "dataset": dataset,
                "n": len(rs),
                "metrics": {
                    "accuracy": _metric(rs, "correct").model_dump(),
                    "hallucination_rate": _metric(rs, "hallucinated").model_dump(),
                    "supported_rate": _metric(rs, "supported_rate").model_dump(),
                    "abstain_rate": _metric(rs, "abstained").model_dump(),
                    "retrieval_recall": _metric(rs, "retrieval_recall").model_dump(),
                },
                "tokens": sum(r["tokens"] for r in rs) / len(rs),
                "latency_ms": sum(r["latency_ms"] for r in rs) / len(rs),
                "cost_usd": sum(r["cost_usd"] for r in rs) / len(rs),
            }
        )
    return out


def stages(rows: list[dict]) -> list[dict]:
    board = {(r["arm"]): r for r in leaderboard(rows)}
    return [
        {
            "label": label,
            "arm": arm,
            "kind": "ablation" if arm.startswith("loupe-no-") else "step",
            "accuracy": board[arm]["metrics"]["accuracy"],
            "hallucination_rate": board[arm]["metrics"]["hallucination_rate"],
            "n": board[arm]["n"],
        }
        for arm, label in STAGE_ORDER
        if arm in board
    ]
