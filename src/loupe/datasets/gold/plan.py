"""Gold-Plan: questions labelled with the intents and tool sequence a good router/planner uses.

Intents: lookup, calc, compare, event, trend, forecast, chart, open_analysis.
`expected_tools` uses the full toolset (including the planned compare_companies, make_chart,
forecast_metric and list_events); meta.expected_tools_minimal is the same plan with today's
tools only (search_filings, get_financial_metric, calculate, list_companies). Templates are
filled with real companies and years; any metric a template needs is checked to resolve in
FactsStore, so no plan item is secretly a trick question.
"""

from dataclasses import dataclass

from loupe.datasets.gold.common import YEARS, GoldContext
from loupe.eval.schema import EvalItem

NAME = "gold_plan"
INTENTS = ("lookup", "calc", "compare", "event", "trend", "forecast", "chart", "open_analysis")
TOOLS = ("search_filings", "get_financial_metric", "calculate", "list_companies")
FUTURE_TOOLS = ("compare_companies", "make_chart", "forecast_metric", "list_events")

GFM, CALC, SEARCH, LIST = "get_financial_metric", "calculate", "search_filings", "list_companies"


@dataclass(frozen=True)
class Template:
    id: str
    text: str
    intents: tuple[str, ...]
    tools: tuple[str, ...]
    minimal: tuple[str, ...]
    needs: tuple[str, ...] = ()  # FY metrics that must resolve for every company named
    n_companies: int = 1
    span: bool = False  # needs FY2023-25 (trend), else one year
    sector: bool = False
    count: int = 6


METRIC_WORDS = {"revenue": "revenue", "net_income": "net income", "total_assets": "total assets"}

TEMPLATES = (
    # single intent
    Template("lookup_metric", "What was {co}'s {m} in fiscal {y}?", ("lookup",), (GFM,), (GFM,),
             needs=("{m}",), count=10),
    Template("lookup_auditor", "Who audits {co}'s financial statements, according to its fiscal "
             "{y} 10-K?", ("lookup",), (SEARCH,), (SEARCH,)),
    Template("lookup_dividend", "What does {co} say about its dividend policy in its fiscal {y} "
             "10-K?", ("lookup",), (SEARCH,), (SEARCH,), count=4),
    Template("list_sector", "Which companies in your coverage are in the {sector} sector?",
             ("lookup",), (LIST,), (LIST,), n_companies=0, sector=True, count=5),
    Template("calc_operating_margin", "What was {co}'s operating margin in fiscal {y}?",
             ("calc",), (GFM, CALC), (GFM, CALC), needs=("operating_income", "revenue")),
    Template("calc_current_ratio", "Compute {co}'s current ratio at the end of fiscal {y}.",
             ("calc",), (GFM, CALC), (GFM, CALC), needs=("current_assets", "current_liabilities")),
    Template("calc_fcf", "What was {co}'s free cash flow in fiscal {y}?", ("calc",), (GFM, CALC),
             (GFM, CALC), needs=("operating_cash_flow", "capex")),
    Template("compare_two", "Which had higher {m} in fiscal {y}: {co} or {co2}?", ("compare",),
             ("compare_companies",), (GFM,), needs=("{m}",), n_companies=2, count=8),
    Template("compare_three", "Compare {co}, {co2} and {co3} by total assets at the end of fiscal "
             "{y}.", ("compare",), ("compare_companies",), (GFM,), needs=("total_assets",),
             n_companies=3, count=5),
    Template("event_year", "What material events did {co} disclose in its 8-K filings during {y}?",
             ("event",), ("list_events",), (SEARCH,), count=8),
    Template("event_risk", "Has {co} reported any auditor changes, restatements or impairments "
             "since 2023?", ("event",), ("list_events",), (SEARCH,), count=6),
    Template("trend_metric", "How has {co}'s {m} trended from fiscal 2023 to fiscal 2025?",
             ("trend",), (GFM,), (GFM,), needs=("{m}",), span=True, count=8),
    Template("trend_quarterly", "Is {co}'s quarterly revenue growing or shrinking over fiscal {y}?",
             ("trend",), (GFM,), (GFM,), needs=("revenue",), count=5),
    Template("forecast_revenue", "Forecast {co}'s revenue for fiscal 2026 from its recent "
             "results.", ("forecast",), (GFM, "forecast_metric"), (GFM, CALC),
             needs=("revenue",), span=True),
    Template("forecast_quarter", "What is a reasonable projection of {co}'s net income for the "
             "next quarter?", ("forecast",), (GFM, "forecast_metric"), (GFM, CALC),
             needs=("net_income",), span=True, count=5),
    Template("chart_quarterly", "Plot {co}'s quarterly revenue for fiscal {y}.", ("chart",),
             (GFM, "make_chart"), (GFM,), needs=("revenue",)),
    Template("chart_annual", "Draw a bar chart of {co}'s net income for fiscal 2023 to 2025.",
             ("chart",), (GFM, "make_chart"), (GFM,), needs=("net_income",), span=True, count=5),
    Template("open_risks", "What are the main risks facing {co}'s business according to its "
             "latest 10-K?", ("open_analysis",), (SEARCH,), (SEARCH,), count=8),
    Template("open_competition", "How does {co}'s management describe its competitive position?",
             ("open_analysis",), (SEARCH,), (SEARCH,), count=6),
    # several intents
    Template("lookup_calc_growth", "What was {co}'s revenue in fiscal {y}, and how much did it "
             "grow from the prior year?", ("lookup", "calc"), (GFM, CALC), (GFM, CALC),
             needs=("revenue",), count=8),
    Template("compare_chart", "Chart {co}'s and {co2}'s revenue side by side for fiscal "
             "2023-2025.", ("compare", "chart"), ("compare_companies", "make_chart"), (GFM,),
             needs=("revenue",), n_companies=2, span=True, count=7),
    Template("event_analysis", "Did {co} disclose any material impairments or debt acceleration "
             "events in {y}, and what do they imply for its credit risk?",
             ("event", "open_analysis"), ("list_events", SEARCH), (SEARCH,), count=7),
    Template("trend_forecast", "How has {co}'s operating cash flow trended since fiscal 2023, and "
             "what would you project for fiscal 2026?", ("trend", "forecast"),
             (GFM, "forecast_metric"), (GFM, CALC), needs=("operating_cash_flow",), span=True,
             count=7),
    Template("calc_trend_chart", "Plot {co}'s net profit margin for fiscal 2023-2025 and describe "
             "the trend.", ("calc", "trend", "chart"), (GFM, CALC, "make_chart"), (GFM, CALC),
             needs=("net_income", "revenue"), span=True, count=7),
    Template("compare_calc", "Compare the operating margins of {co} and {co2} in fiscal {y}.",
             ("compare", "calc"), ("compare_companies", CALC), (GFM, CALC),
             needs=("operating_income", "revenue"), n_companies=2, count=7),
    Template("lookup_event", "What was {co}'s net income in fiscal {y}, and did it report any "
             "material 8-K events that year?", ("lookup", "event"), (GFM, "list_events"),
             (GFM, SEARCH), needs=("net_income",), count=7),
    Template("lookup_drivers", "What was {co}'s revenue in fiscal {y}, and what does management "
             "say drove the change?", ("lookup", "open_analysis"), (GFM, SEARCH), (GFM, SEARCH),
             needs=("revenue",), count=7),
    Template("sector_compare", "Among the {sector} companies you cover, which had the highest net "
             "income in fiscal {y}?", ("compare",), (LIST, "compare_companies"), (LIST, GFM),
             n_companies=0, sector=True, count=5),
    Template("event_compare", "Which of {co} and {co2} filed more 8-Ks about executive or director "
             "changes in {y}?", ("compare", "event"), ("list_events",), (SEARCH,), n_companies=2,
             count=6),
    Template("trend_compare_chart", "Show how {co}'s and {co2}'s total assets evolved from fiscal "
             "2023 to 2025 on one chart.", ("compare", "trend", "chart"),
             ("compare_companies", "make_chart"), (GFM,), needs=("total_assets",),
             n_companies=2, span=True, count=6),
    Template("margin_drivers", "What was {co}'s gross margin in fiscal {y}, and what factors does "
             "management cite for it?", ("lookup", "calc", "open_analysis"), (GFM, CALC, SEARCH),
             (GFM, CALC, SEARCH), needs=("gross_profit", "revenue"), count=6),
)  # fmt: skip


def _resolves(ctx: GoldContext, company: str, metrics: list[str], years: list[int]) -> bool:
    return all(ctx.store.get(company, m, y) is not None for m in metrics for y in years)


def build(ctx: GoldContext) -> list[EvalItem]:
    items = []
    sectors = sorted({c.sector for c in ctx.universe.values()})
    for t in TEMPLATES:
        rng = ctx.rng(NAME, t.id)
        companies = sorted(ctx.universe)
        rng.shuffle(companies)
        made, attempts = 0, 0
        seen: set[tuple] = set()
        while made < t.count and attempts < 400:
            attempts += 1
            metric = rng.choice(list(METRIC_WORDS))
            year = rng.choice(YEARS)
            years = list(YEARS) if t.span else [year]
            needs = [n.replace("{m}", metric) for n in t.needs]
            if t.sector:
                sector = sectors[(made + attempts) % len(sectors)]
                members = [c for c in ctx.universe.values() if c.sector == sector]
                if len(members) < 2:
                    continue
                key: tuple = (sector, year if "{y}" in t.text else None)
                chosen: list[str] = []
                splits = {c.split for c in members}
                split = splits.pop() if len(splits) == 1 else rng.choice(["dev", "test"])
            else:
                first = companies[(made + attempts) % len(companies)]
                pool = [c for c in companies if ctx.split(c) == ctx.split(first) and c != first]
                chosen = [first, *rng.sample(pool, t.n_companies - 1)] if t.n_companies else []
                key = (
                    tuple(sorted(chosen)),
                    year if "{y}" in t.text else None,
                    metric if "{m}" in t.text else None,
                )
                split = ctx.split(first)
                sector = ""
            if key in seen or not all(_resolves(ctx, c, needs, years) for c in chosen):
                continue
            seen.add(key)
            names = [ctx.name(c) for c in chosen] + ["", "", ""]
            question = t.text.format(
                co=names[0], co2=names[1], co3=names[2], m=METRIC_WORDS[metric], y=year,
                sector=sector,
            )  # fmt: skip
            made += 1
            items.append(
                EvalItem(
                    item_id=f"{NAME}:{t.id}:{made:02d}",
                    dataset=NAME,
                    question=question,
                    kind="plan",
                    mode="corpus",
                    companies=chosen,
                    fiscal_year=year if "{y}" in t.text else None,
                    expected_intents=list(t.intents),
                    expected_tools=list(t.tools),
                    split=split,  # type: ignore[arg-type]
                    category="multi_intent" if len(t.intents) > 1 else "single_intent",
                    meta={
                        "template": t.id,
                        "expected_tools_minimal": list(t.minimal),
                        "metrics": needs,
                        "years": years if needs else [],
                        "sector": sector or None,
                    },
                )
            )
    return items
