"""Gold-Num: single-value questions answered exactly from XBRL (no LLM).

Per company: 12 slots (9 fiscal years + 3 quarters, spread evenly over FY2023-25), each filled
with a different metric where the company reports one. Values, concepts and filings come
from FactsStore; questions name the concept actually tagged and the period end date.
"""

import random

from loupe.datasets.gold.common import (
    QUARTERS,
    YEARS,
    GoldContext,
    evidence,
    fmt_date,
    fmt_usd,
    label_for,
    period_phrase,
    provenance,
)
from loupe.eval.schema import EvalItem
from loupe.tools.facts import FactResult

NAME = "gold_num"
METRICS = (
    "revenue",
    "net_income",
    "operating_income",
    "gross_profit",
    "eps_diluted",
    "operating_cash_flow",
    "capex",
    "total_assets",
    "total_liabilities",
    "equity",
    "cash",
    "long_term_debt",
)
NOT_ADDITIVE = {"eps_diluted", "eps_basic"}  # "FY - 9M YTD" is meaningless for per-share data
PER_COMPANY = {"FY": 3, "Q": 1}  # per fiscal year -> 9 FY + 3 quarterly slots per company

FLOW_TEMPLATES = (
    "What was {co}'s {label} for {period}? Answer in {unit}.",
    "How much did {co} report as {label} for {period}? Give the figure in {unit}.",
    "According to its SEC filings, what {label} did {co} record in {period}? Use {unit}.",
    "{co}: {label}, {period}. State the amount in {unit}.",
    "Look up {co}'s {label} for {period}, in {unit}.",
)
BALANCE_TEMPLATES = (
    "What was {co}'s {label} as of {date}? Answer in {unit}.",
    "How much {label} did {co} report on its balance sheet at {date} (in {unit})?",
    "Report {co}'s {label} at the end of {period} ({date}), in {unit}.",
    "{co}: {label} at {date}. Give the amount in {unit}.",
)
EPS_TEMPLATES = (
    "What was {co}'s {label} for {period}? Answer in USD per share.",
    "How much did {co} earn per diluted share in {period}?",
    "What diluted EPS did {co} report for {period} (in USD per share)?",
)


def question(ctx: GoldContext, fact: FactResult, rng: random.Random) -> tuple[str, str]:
    """(question, answer text) with a natural phrasing and an explicit unit."""
    co = rng.choice([ctx.name(fact.company_id), ctx.name(fact.company_id), fact.company_id])
    instant = fact.period_start is None  # balances: the question states the date itself
    period = period_phrase(ctx, fact, rng, with_end=not instant)
    label = label_for(fact)
    if fact.metric in NOT_ADDITIVE:
        return rng.choice(EPS_TEMPLATES).format(co=co, label=label, period=period), fmt_usd(
            fact.value, "per_share"
        )
    scale = "billions" if abs(fact.value) >= 10e9 and rng.random() < 0.4 else "millions"
    unit = f"USD {scale}"
    templates = BALANCE_TEMPLATES if instant else FLOW_TEMPLATES
    q = rng.choice(templates).format(
        co=co, label=label, period=period, unit=unit, date=fmt_date(fact.period_end)
    )
    return q, f"{fmt_usd(fact.value, scale)} (USD {fact.value:,.0f})"


def _pick(
    ctx: GoldContext, company: str, year: int, kind: str, order: list[str], done: set, rng
) -> FactResult | None:
    periods = ["FY"] if kind == "FY" else rng.sample(QUARTERS, len(QUARTERS))
    for metric in order:
        for period in periods:
            if (metric, year, period) in done:
                continue
            if period == "Q4" and ctx.store.metrics[metric].kind == "instant":
                continue  # a Q4 balance is the fiscal year-end balance
            if any(d[0] == metric and d[1] == year for d in done):
                continue  # one question per metric and year
            fact = ctx.store.get(company, metric, year, period)  # type: ignore[arg-type]
            if fact is None or (fact.derived and metric in NOT_ADDITIVE):
                continue
            return fact
    return None


def build(ctx: GoldContext) -> list[EvalItem]:
    items = []
    for company in sorted(ctx.universe):
        rng = ctx.rng(NAME, company)
        slots = [(y, k) for y in YEARS for k, n in PER_COMPANY.items() for _ in range(n)]
        rng.shuffle(slots)
        metrics = list(METRICS)
        rng.shuffle(metrics)
        used: list[str] = []
        done: set = set()
        for year, kind in slots:
            order = [m for m in metrics if m not in used] + used  # least-used metrics first
            fact = _pick(ctx, company, year, kind, order, done, rng)
            if fact is None:
                continue
            done.add((fact.metric, year, fact.fiscal_period))
            if fact.metric in used:
                used.remove(fact.metric)
            used.append(fact.metric)
            q, answer = question(ctx, fact, rng)
            items.append(
                EvalItem(
                    item_id=f"{NAME}:{company}:{fact.metric}:FY{year}:{fact.fiscal_period}",
                    dataset=NAME,
                    question=q,
                    kind="numeric",
                    answer=answer,
                    answer_value=fact.value,
                    answer_unit=fact.unit,
                    tolerance=0.01,
                    mode="corpus",
                    evidence=[evidence(ctx, fact)],
                    companies=[company],
                    fiscal_year=year,
                    split=ctx.split(company),  # type: ignore[arg-type]
                    category="quarter" if fact.fiscal_period != "FY" else "fiscal_year",
                    meta={
                        "metric": fact.metric,
                        "period": fact.fiscal_period,
                        "derived": fact.derived,
                        "fact": provenance(fact),
                    },
                )
            )
    return items
