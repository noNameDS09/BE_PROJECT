"""Company universe selection: eligibility, size and 8-K risk events.

Rule (docs/decisions.md D3): ~15 FinanceBench companies plus ~10 companies chosen
for notable FY2023-25 8-K risk events. Every candidate must have enough periodic
reports in the window to support the experiments.
"""

import random
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import date
from typing import Any, Literal
from urllib.parse import urlencode

from pydantic import BaseModel

from loupe.sources.us.edgar import FilingRef, select_window
from loupe.sources.us.sec_client import SecClient

# 8-K items that signal risk. 5.02 (officer changes) is extracted later but is
# too common to drive selection.
RISK_ITEMS = {
    "1.03": "bankruptcy or receivership",
    "1.05": "material cybersecurity incident",
    "2.04": "triggering event accelerating an obligation",
    "2.06": "material impairment",
    "4.01": "change in certifying accountant",
    "4.02": "non-reliance on prior financial statements",
}

REVENUE_CONCEPTS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenuesNetOfInterestExpense",
    "SalesRevenueNet",
)

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"


class Selection(BaseModel):
    ticker: str
    group: Literal["financebench", "event"]
    sector: str
    reason: str


def stratified_split(sectors: dict[str, str], n_dev: int, seed: int) -> dict[str, str]:
    """Assign `n_dev` keys to dev, spread across sectors in proportion to their size.

    Quotas use the largest-remainder method; companies within a sector are drawn at random.
    """
    rng = random.Random(seed)
    by_sector: dict[str, list[str]] = defaultdict(list)
    for key in sorted(sectors):
        by_sector[sectors[key]].append(key)
    names = sorted(by_sector)
    rng.shuffle(names)  # random tie-break between equal remainders
    exact = {s: n_dev * len(by_sector[s]) / len(sectors) for s in names}
    quota = {s: int(exact[s]) for s in names}
    for s in sorted(names, key=lambda s: exact[s] - quota[s], reverse=True):
        if sum(quota.values()) >= n_dev:
            break
        quota[s] += 1
    split = {}
    for s in sorted(by_sector):
        members = by_sector[s][:]
        rng.shuffle(members)
        for i, key in enumerate(members):
            split[key] = "dev" if i < quota[s] else "test"
    return split


class Eligibility(BaseModel):
    n_10k: int
    n_10q: int
    n_8k: int
    risk_items: dict[str, int]

    def eligible(self, min_10k: int = 3, min_10q: int = 6) -> bool:
        return self.n_10k >= min_10k and self.n_10q >= min_10q


def eligibility(filings: list[FilingRef], start: date, end: date) -> Eligibility:
    window = select_window(filings, start, end, ("10-K", "10-Q", "8-K"))
    forms = Counter(f.form for f in window)
    risk = Counter(i for f in window if f.form == "8-K" for i in f.items if i in RISK_ITEMS)
    return Eligibility(
        n_10k=forms["10-K"], n_10q=forms["10-Q"], n_8k=forms["8-K"], risk_items=dict(risk)
    )


def latest_annual_revenue(facts: dict[str, Any]) -> tuple[float, str] | None:
    """Latest full-year revenue reported in a 10-K, as (USD, period end)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    best: tuple[str, float] | None = None
    for concept in REVENUE_CONCEPTS:
        for row in gaap.get(concept, {}).get("units", {}).get("USD", []):
            if row.get("form") != "10-K" or "start" not in row:
                continue
            days = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
            if not 350 <= days <= 380:
                continue
            candidate = (row["end"], float(row["val"]))
            if best is None or candidate > best:
                best = candidate
    return (best[1], best[0]) if best else None


def efts_search(
    client: SecClient, phrase: str, start: date, end: date, forms: str = "8-K"
) -> Iterator[dict[str, Any]]:
    """Page through EDGAR full-text search hits for `phrase`."""
    offset = 0
    while True:
        query = urlencode(
            {
                "q": f'"{phrase}"',
                "forms": forms,
                "dateRange": "custom",
                "startdt": start.isoformat(),
                "enddt": end.isoformat(),
                "from": offset,
            }
        )
        page = client.get_json(f"{EFTS_URL}?{query}")
        hits = page["hits"]["hits"]
        yield from (h["_source"] for h in hits)
        offset += len(hits)
        if not hits or offset >= min(page["hits"]["total"]["value"], 10_000):
            return
