"""Shared context for the Loupe-Gold builders: facts store, universe, SEC manifest, phrasing."""

import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from loupe.datasets.universe import METRICS_CONFIG, REPO_ROOT, UniverseCompany, load_universe
from loupe.eval.schema import GoldEvidence
from loupe.tools.facts import FactResult, FactsStore, load_metrics

SEED = 20261013  # the project seed (company split); every builder derives its RNG from it
YEARS = (2023, 2024, 2025)
QUARTERS = ("Q1", "Q2", "Q3", "Q4")
WINDOW = (date(2023, 1, 1), date(2025, 12, 31))  # SEC corpus window (8-K filing dates)
DATA_CUTOFF = date(2026, 10, 13)  # snapshot date of the SEC corpus and XBRL facts
GOLD_DIR = REPO_ROOT / "data" / "gold"

# Human labels for the XBRL concept that actually answered, so questions name what was tagged.
CONCEPT_LABELS = {
    "Revenues": "total revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "total revenue",
    "RevenueFromContractWithCustomerIncludingAssessedTax": "total revenue",
    "RevenuesNetOfInterestExpense": "total net revenue (net of interest expense)",
    "SalesRevenueNet": "net sales",
    "CostOfRevenue": "cost of revenue",
    "CostOfGoodsAndServicesSold": "cost of goods and services sold",
    "CostOfGoodsSold": "cost of goods sold",
    "GrossProfit": "gross profit",
    "OperatingIncomeLoss": "operating income",
    "NetIncomeLoss": "net income attributable to shareholders",
    "NetIncomeLossAvailableToCommonStockholdersBasic": (
        "net income available to common shareholders"
    ),
    "ProfitLoss": "net income (including noncontrolling interests)",
    "EarningsPerShareDiluted": "diluted earnings per share",
    "EarningsPerShareBasic": "basic earnings per share",
    "ResearchAndDevelopmentExpense": "research and development expense",
    "NetCashProvidedByUsedInOperatingActivities": "net cash provided by operating activities",
    "PaymentsToAcquirePropertyPlantAndEquipment": (
        "capital expenditures (purchases of property, plant and equipment)"
    ),
    "PaymentsToAcquireProductiveAssets": "capital expenditures (payments for productive assets)",
    "Assets": "total assets",
    "AssetsCurrent": "total current assets",
    "Liabilities": "total liabilities",
    "LiabilitiesCurrent": "total current liabilities",
    "StockholdersEquity": "total shareholders' equity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": (
        "total equity (including noncontrolling interests)"
    ),
    "CashAndCashEquivalentsAtCarryingValue": "cash and cash equivalents",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": (
        "cash, cash equivalents and restricted cash"
    ),
    "LongTermDebtNoncurrent": "long-term debt (excluding the current portion)",
    "LongTermDebt": "total long-term debt (including the current portion)",
    "LongTermDebtAndCapitalLeaseObligations": "long-term debt and finance lease obligations",
    "InventoryNet": "inventory",
}
METRIC_LABELS = {
    "revenue": "revenue",
    "cost_of_revenue": "cost of revenue",
    "gross_profit": "gross profit",
    "operating_income": "operating income",
    "net_income": "net income",
    "eps_diluted": "diluted earnings per share",
    "rd_expense": "research and development expense",
    "operating_cash_flow": "operating cash flow",
    "capex": "capital expenditures",
    "total_assets": "total assets",
    "total_liabilities": "total liabilities",
    "equity": "shareholders' equity",
    "cash": "cash and cash equivalents",
    "long_term_debt": "long-term debt",
    "inventory": "inventory",
    "current_assets": "current assets",
    "current_liabilities": "current liabilities",
}


def label_for(fact: FactResult) -> str:
    return CONCEPT_LABELS.get(fact.concept.split(":")[-1], METRIC_LABELS.get(fact.metric, ""))


def fmt_date(d: date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def fmt_usd(value: float, unit: str = "millions") -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)
    if unit == "billions":
        return f"{sign}${v / 1e9:,.2f} billion"
    if unit == "per_share":
        return f"{sign}${v:,.2f} per share"
    digits = 0 if v >= 1e8 else 1
    return f"{sign}${v / 1e6:,.{digits}f} million"


def calendar_year_end(d: date) -> bool:
    """52/53-week years ending within a week of December 31 count as calendar years."""
    return (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 7)


@dataclass
class GoldContext:
    data_dir: Path
    store: FactsStore
    universe: dict[str, UniverseCompany]
    manifest: list[dict[str, Any]]
    doc_ids: set[str]
    _items_by_company: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def open(cls, data_dir: Path) -> "GoldContext":
        universe = load_universe()
        store = FactsStore(
            data_dir / "processed" / "loupe.duckdb",  # opened read-only by FactsStore
            load_metrics(METRICS_CONFIG),
            {c.id: c.cik for c in universe.values()},
        )
        manifest_path = data_dir / "raw" / "sec" / "manifest.jsonl"
        manifest = [json.loads(x) for x in manifest_path.read_text().split("\n") if x.strip()]
        docs_path = data_dir / "processed" / "sec" / "documents.jsonl"
        doc_ids = {json.loads(x)["doc_id"] for x in docs_path.read_text().split("\n") if x.strip()}
        return cls(data_dir, store, universe, manifest, doc_ids)

    def rng(self, *parts: object) -> random.Random:
        return random.Random(":".join(str(p) for p in (SEED, *parts)))

    def eight_k_items(self, company_id: str) -> set[str]:
        """Every 8-K item code the company filed in the corpus window."""
        if not self._items_by_company:
            for r in self.manifest:
                if r["form"] == "8-K":
                    self._items_by_company.setdefault(r["company_id"], set()).update(r["items"])
        return self._items_by_company.get(company_id, set())

    def doc_id(self, company_id: str, form: str | None, accession: str) -> str | None:
        doc_id = f"{company_id}_{form}_{accession}"
        return doc_id if doc_id in self.doc_ids else None

    def split(self, company_id: str) -> str:
        return self.universe[company_id].split

    def name(self, company_id: str) -> str:
        return self.universe[company_id].display


def provenance(fact: FactResult) -> dict[str, Any]:
    return {
        "company": fact.company_id,
        "metric": fact.metric,
        "fiscal_year": fact.fiscal_year,
        "period": fact.fiscal_period,
        "value": fact.value,
        "unit": fact.unit,
        "concept": fact.concept,
        "period_start": fact.period_start.isoformat() if fact.period_start else None,
        "period_end": fact.period_end.isoformat(),
        "accession": fact.accession,
        "form": fact.form,
        "filed": fact.filed.isoformat() if fact.filed else None,
        "url": fact.url,
        "derived": fact.derived,
    }


def evidence(ctx: GoldContext, fact: FactResult) -> GoldEvidence:
    return GoldEvidence(
        doc_id=ctx.doc_id(fact.company_id, fact.form, fact.accession),
        accession=fact.accession,
        text=f"{fact.concept} = {fact.value:g} {fact.unit} "
        f"({fact.period_start or ''}..{fact.period_end}, {fact.form} filed {fact.filed})",
    )


def period_phrase(
    ctx: GoldContext, fact: FactResult, rng: random.Random, with_end: bool = True
) -> str:
    """'fiscal 2024', 'Q2 of fiscal 2024 (the quarter ended June 29, 2024)', ...

    with_end=False drops the end date, for questions that state the date themselves.
    """
    fy = fact.fiscal_year
    year = rng.choice([f"fiscal {fy}", f"FY{fy}", f"fiscal year {fy}"])
    if not with_end:
        return year if fact.fiscal_period == "FY" else f"{fact.fiscal_period} of {year}"
    if fact.fiscal_period == "FY":
        if calendar_year_end(fact.period_end):
            return year
        return f"{year} (the fiscal year ended {fmt_date(fact.period_end)})"
    return f"{fact.fiscal_period} of {year} (the quarter ended {fmt_date(fact.period_end)})"


def fy_phrase(ctx: GoldContext, company_id: str, fy: int, rng: random.Random) -> str:
    year = rng.choice([f"fiscal {fy}", f"FY{fy}", f"fiscal year {fy}"])
    end = ctx.store.calendar(company_id).fy_end_for(fy)
    if end is None or calendar_year_end(end):
        return year
    return f"{year} (the fiscal year ended {fmt_date(end)})"
