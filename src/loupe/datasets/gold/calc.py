"""Gold-Calc: multi-step answers computed in code from 2-3 XBRL facts.

Each item stores the calculation name, the formula, and every input with its provenance;
`gold verify` re-fetches the inputs and recomputes the answer with the same function.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from loupe.datasets.gold.common import (
    YEARS,
    GoldContext,
    evidence,
    fmt_usd,
    fy_phrase,
    label_for,
    provenance,
)
from loupe.eval.schema import EvalItem
from loupe.tools.facts import FactResult

NAME = "gold_calc"
PER_COMPANY = 6


@dataclass(frozen=True)
class Calc:
    name: str
    family: str
    inputs: Callable[[int], dict[str, tuple[str, int]]]  # year -> {key: (metric, fiscal_year)}
    compute: Callable[[dict[str, float]], float | None]
    formula: str
    unit: str  # "%", "ratio" or "USD"
    years: tuple[int, ...]
    templates: tuple[str, ...]


def _div(a: float, b: float) -> float | None:
    return a / b if b else None


def _growth(v: dict[str, float]) -> float | None:
    if v["prior"] <= 0 or v["current"] <= 0:
        return None  # growth across a loss (sign change) or from zero is not meaningful
    return (v["current"] - v["prior"]) / v["prior"] * 100


def _cagr(v: dict[str, float]) -> float | None:
    if v["start"] <= 0 or v["end"] <= 0:
        return None
    return (math.pow(v["end"] / v["start"], 1 / 2) - 1) * 100


def _margin(num: str) -> Callable[[dict[str, float]], float | None]:
    def f(v: dict[str, float]) -> float | None:
        r = _div(v[num], v["revenue"])
        return None if r is None else r * 100

    return f


def _gross_from_cost(v: dict[str, float]) -> float | None:
    r = _div(v["revenue"] - v["cost_of_revenue"], v["revenue"])
    return None if r is None else r * 100


def _d2e(v: dict[str, float]) -> float | None:
    return None if v["equity"] <= 0 else v["long_term_debt"] / v["equity"]


GROWTH_T = (
    "By what percentage did {co}'s {label} change from {p0} to {p1}? "
    "Answer in percent, rounded to one decimal place.",
    "What was {co}'s year-over-year growth in {label} in {p1} compared with {p0}? "
    "Give a percentage rounded to one decimal.",
    "Compute the YoY change in {co}'s {label} between {p0} and {p1}, as a percentage "
    "(one decimal place).",
)
MARGIN_T = (
    "What was {co}'s {name} in {p1}, computed as {num} divided by {den}? "
    "Answer in percent, rounded to one decimal place.",
    "Calculate {co}'s {name} for {p1} ({num} / {den}), as a percentage with one decimal.",
)
RATIO_T = (
    "What was {co}'s {name} at the end of {p1}, defined as {num} divided by {den}? "
    "Round to two decimal places.",
    "Compute {co}'s {name} ({num} / {den}) as of the end of {p1}, to two decimals.",
)
FCF_T = (
    "What was {co}'s free cash flow in {p1}, defined as {num} minus {den}? Answer in USD millions.",
    "Compute {co}'s {p1} free cash flow ({num} less {den}), in USD millions.",
)
CAGR_T = (
    "What was {co}'s two-year compound annual growth rate (CAGR) in {label} from {p0} to "
    "{p1}? Answer in percent, rounded to one decimal place.",
    "Calculate the 2-year CAGR of {co}'s {label} between {p0} and {p1}, as a percentage "
    "with one decimal.",
)


def _yoy(metric: str) -> Calc:
    return Calc(
        name=f"yoy_growth_{metric}",
        family="yoy_growth",
        inputs=lambda y: {"current": (metric, y), "prior": (metric, y - 1)},
        compute=_growth,
        formula="(current - prior) / prior * 100",
        unit="%",
        years=(2024, 2025),
        templates=GROWTH_T,
    )


def _margin_calc(name: str, metric: str) -> Calc:
    return Calc(
        name=name,
        family="margin",
        inputs=lambda y: {metric: (metric, y), "revenue": ("revenue", y)},
        compute=_margin(metric),
        formula=f"{metric} / revenue * 100",
        unit="%",
        years=YEARS,
        templates=MARGIN_T,
    )


CALCS: dict[str, Calc] = {
    c.name: c
    for c in [
        _yoy("revenue"),
        _yoy("net_income"),
        _yoy("operating_cash_flow"),
        _margin_calc("gross_margin", "gross_profit"),
        Calc(
            name="gross_margin_from_cost",
            family="margin",
            inputs=lambda y: {"revenue": ("revenue", y), "cost_of_revenue": ("cost_of_revenue", y)},
            compute=_gross_from_cost,
            formula="(revenue - cost_of_revenue) / revenue * 100",
            unit="%",
            years=YEARS,
            templates=MARGIN_T,
        ),
        _margin_calc("operating_margin", "operating_income"),
        _margin_calc("net_margin", "net_income"),
        Calc(
            name="current_ratio",
            family="ratio",
            inputs=lambda y: {
                "current_assets": ("current_assets", y),
                "current_liabilities": ("current_liabilities", y),
            },
            compute=lambda v: _div(v["current_assets"], v["current_liabilities"]),
            formula="current_assets / current_liabilities",
            unit="ratio",
            years=YEARS,
            templates=RATIO_T,
        ),
        Calc(
            name="debt_to_equity",
            family="ratio",
            inputs=lambda y: {"long_term_debt": ("long_term_debt", y), "equity": ("equity", y)},
            compute=_d2e,
            formula="long_term_debt / equity (only when equity > 0)",
            unit="ratio",
            years=YEARS,
            templates=RATIO_T,
        ),
        Calc(
            name="free_cash_flow",
            family="fcf",
            inputs=lambda y: {
                "operating_cash_flow": ("operating_cash_flow", y),
                "capex": ("capex", y),
            },
            compute=lambda v: v["operating_cash_flow"] - v["capex"],
            formula="operating_cash_flow - capex",
            unit="USD",
            years=YEARS,
            templates=FCF_T,
        ),
        Calc(
            name="cagr_2y_revenue",
            family="cagr",
            inputs=lambda y: {"start": ("revenue", y - 2), "end": ("revenue", y)},
            compute=_cagr,
            formula="((end / start) ** (1 / 2) - 1) * 100",
            unit="%",
            years=(2025,),
            templates=CAGR_T,
        ),
    ]
}
DISPLAY = {
    "gross_margin": "gross margin",
    "gross_margin_from_cost": "gross margin",
    "operating_margin": "operating margin",
    "net_margin": "net profit margin",
    "current_ratio": "current ratio",
    "debt_to_equity": "debt-to-equity ratio",
}


def fetch(ctx: GoldContext, company: str, calc: Calc, year: int) -> dict[str, FactResult] | None:
    facts = {}
    for key, (metric, fy) in calc.inputs(year).items():
        fact = ctx.store.get(company, metric, fy, "FY")
        if fact is None:
            return None
        facts[key] = fact
    return facts


def compute(calc: Calc, facts: dict[str, FactResult]) -> float | None:
    return calc.compute({k: f.value for k, f in facts.items()})


def tolerance(unit: str, value: float) -> float:
    """1% relative, widened to the requested rounding (0.05 pp for %, 0.005 for ratios)."""
    half = {"%": 0.05, "ratio": 0.005}.get(unit, 0.0)
    return max(0.01, half / abs(value)) if value else 0.01


def _text(ctx, company, calc: Calc, year: int, facts: dict[str, FactResult], rng) -> str:
    co = rng.choice([ctx.name(company), ctx.name(company), company])
    p1 = fy_phrase(ctx, company, year, rng)
    keys = list(facts)
    if calc.family in ("yoy_growth", "cagr"):
        f0 = facts["prior" if calc.family == "yoy_growth" else "start"]
        p0 = fy_phrase(ctx, company, f0.fiscal_year, rng)
        return rng.choice(calc.templates).format(co=co, label=label_for(f0), p0=p0, p1=p1)
    num, den = label_for(facts[keys[0]]), label_for(facts[keys[1]])
    if calc.name == "gross_margin_from_cost":
        num = f"({label_for(facts['revenue'])} minus {label_for(facts['cost_of_revenue'])})"
        den = label_for(facts["revenue"])
    if calc.name in ("gross_margin", "operating_margin", "net_margin"):
        num, den = label_for(facts[keys[0]]), label_for(facts["revenue"])
    return rng.choice(calc.templates).format(
        co=co, name=DISPLAY.get(calc.name, calc.name), num=num, den=den, p1=p1
    )


def _answer_text(calc: Calc, value: float) -> str:
    if calc.unit == "%":
        return f"{value:.1f}% (exact {value:.4f}%)"
    if calc.unit == "ratio":
        return f"{value:.2f} (exact {value:.4f})"
    return f"{fmt_usd(value)} (USD {value:,.0f})"


def build(ctx: GoldContext) -> list[EvalItem]:
    items = []
    for company in sorted(ctx.universe):
        rng = ctx.rng(NAME, company)
        candidates = []
        for calc in CALCS.values():
            for year in calc.years:
                facts = fetch(ctx, company, calc, year)
                if facts and compute(calc, facts) is not None:
                    candidates.append((calc, year, facts))
        # a company reporting gross profit gets the direct margin, not the cost-based one
        direct = {(c.name, y) for c, y, _ in candidates}
        candidates = [
            (c, y, f)
            for c, y, f in candidates
            if not (c.name == "gross_margin_from_cost" and ("gross_margin", y) in direct)
        ]
        rng.shuffle(candidates)
        chosen, families, names = [], {}, set()
        for c, y, f in candidates:  # spread over calculation types first
            if len(chosen) < PER_COMPANY and c.name not in names and families.get(c.family, 0) < 2:
                chosen.append((c, y, f))
                names.add(c.name)
                families[c.family] = families.get(c.family, 0) + 1
        for c, y, f in candidates:  # top up if the company lacks some inputs
            if len(chosen) < PER_COMPANY and (c, y, f) not in chosen:
                chosen.append((c, y, f))
        for calc, year, facts in chosen:
            value = compute(calc, facts)
            assert value is not None
            items.append(
                EvalItem(
                    item_id=f"{NAME}:{company}:{calc.name}:FY{year}",
                    dataset=NAME,
                    question=_text(ctx, company, calc, year, facts, rng),
                    kind="numeric",
                    answer=_answer_text(calc, value),
                    answer_value=value,
                    answer_unit=calc.unit,
                    tolerance=tolerance(calc.unit, value),
                    mode="corpus",
                    evidence=[evidence(ctx, f) for f in facts.values()],
                    companies=[company],
                    fiscal_year=year,
                    split=ctx.split(company),  # type: ignore[arg-type]
                    category=calc.family,
                    meta={
                        "calc": calc.name,
                        "formula": calc.formula,
                        "inputs": {k: provenance(f) for k, f in facts.items()},
                    },
                )
            )
    return items
