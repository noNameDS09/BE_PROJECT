"""Find companies with notable risk events, for the second half of the universe.

docs/PLAN.md D3 chooses the 25 US companies as ~15 FinanceBench names plus ~10
found by scanning FY2023-25 8-Ks for risk items: 1.03 (bankruptcy),
2.04 (accelerated financial obligation / debt default), 4.01 (auditor change),
4.02 (restatement of financials), 5.02 (officer departures), 1.01 and 2.01.

Only the filing index is needed — no document downloads — so a scan is cheap
and can cover the whole listed universe.

Ranking is deliberately simple and stated up front so the selection is
reproducible: severity of the item, then how many distinct risk items the
company filed, then recency.
"""

import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from loupe.core.schemas import CompanyInfo
from loupe.sources.us import RISK_8K_ITEMS, list_filings

# Higher = more serious. This ordering is a judgement call and is recorded as
# such; changing it changes the universe, so it is stated in docs/decisions.md.
ITEM_SEVERITY = {
    "1.03": 5,  # bankruptcy or receivership
    "4.02": 5,  # non-reliance on previously issued financials
    "2.04": 4,  # acceleration / debt default
    "4.01": 3,  # change in registrant's certifying accountant
    "1.01": 2,  # material definitive agreement
    "5.02": 1,  # departure or election of directors/officers
    "2.01": 1,  # completion of acquisition
}
SCAN_WINDOW = ("2023-01-01", "2025-12-31")


class RateLimitError(RuntimeError):
    """SEC asks for no more than 10 requests per second."""


@dataclass
class RiskProfile:
    ticker: str
    total_8k: int = 0
    risk_8k: int = 0
    items: dict[str, int] = field(default_factory=dict)
    latest: str | None = None

    @property
    def score(self) -> tuple[int, int, str]:
        """Sort key: worst item first, then breadth, then recency."""
        worst = max((ITEM_SEVERITY.get(i, 0) for i in self.items), default=0)
        return (worst, len(self.items), self.latest or "")

    def as_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "total_8k": self.total_8k,
            "risk_8k": self.risk_8k,
            "items": dict(sorted(self.items.items())),
            "latest": self.latest,
            "score": list(self.score),
        }


def profile_company(company: CompanyInfo, window: tuple[str, str] = SCAN_WINDOW) -> RiskProfile:
    """Count 8-K filings and risk items for one company."""
    filings = list_filings(company, forms=("8-K",), start=window[0], end=window[1])
    profile = RiskProfile(ticker=company.ticker, total_8k=len(filings))
    for filing in filings:
        for item in set(filing.get("items") or []) & RISK_8K_ITEMS:
            profile.items[item] = profile.items.get(item, 0) + 1
            profile.risk_8k += 1
        if filing.get("filing_date"):
            latest = filing["filing_date"].isoformat()
            profile.latest = max(profile.latest or "", latest)
    return profile


def scan(
    companies: Iterable[CompanyInfo],
    window: tuple[str, str] = SCAN_WINDOW,
    min_risk: int = 1,
    pause: float = 0.15,
    on_progress=None,
) -> list[RiskProfile]:
    """Profile many companies, ranked most interesting first.

    SEC allows 10 requests/second; `pause` keeps us well under that.
    """
    out: list[RiskProfile] = []
    for company in companies:
        if on_progress:
            on_progress(company)
        try:
            profile = profile_company(company, window)
        except Exception as exc:  # pragma: no cover - network dependent
            if on_progress:
                on_progress(company, f"{type(exc).__name__}: {exc}")
            continue
        if profile.risk_8k >= min_risk:
            out.append(profile)
        time.sleep(pause)
    return sorted(out, key=lambda p: p.score, reverse=True)


def to_event_candidates(
    profiles: list[RiskProfile], existing: Iterable[str] = (), count: int = 10
) -> list[dict]:
    """Turn the top ranked profiles into config-ready entries."""
    taken = {t.upper() for t in existing}
    entries: list[dict] = []
    for profile in profiles:
        if profile.ticker in taken or len(entries) >= count:
            continue
        entries.append(
            {
                "ticker": profile.ticker,
                "items": profile.items,
                "risk_8k": profile.risk_8k,
                "note": "8-K risk-event scan",
            }
        )
    return entries


def iter_candidates(rows: list[dict]) -> Iterator[str]:  # pragma: no cover
    for row in rows:
        yield row["ticker"]
