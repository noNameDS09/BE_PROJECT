"""
Financial Query Engine.

Provides structured, deterministic retrieval of SEC financial facts for specific
companies, metrics, and fiscal periods. Eliminates hallucinations by directly
querying normalized SEC EDGAR XBRL facts.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

from src.data.company_registry import CompanyMetadata, CompanyRegistry, get_registry
from src.data.financial_normalizer import NormalizedFact, normalize_facts
from src.data.sec_loader import CompanyFacts, SECDataLoader, get_default_loader

logger = logging.getLogger(__name__)


# Standard candidate concept aliases for common financial metrics
COMMON_METRIC_CANDIDATES: Dict[str, List[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "net income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "total assets": [
        "Assets",
    ],
    "assets": [
        "Assets",
    ],
    "total liabilities": [
        "Liabilities",
        "LiabilitiesCurrent",
    ],
    "liabilities": [
        "Liabilities",
    ],
    "stockholders equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "equity": [
        "StockholdersEquity",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "Cash",
    ],
    "operating income": [
        "OperatingIncomeLoss",
    ],
    "gross profit": [
        "GrossProfit",
    ],
    "research and development": [
        "ResearchAndDevelopmentExpense",
    ],
}


@dataclass
class FinancialFactResult:
    """
    Structured, fully verifiable result of a financial fact query.
    Contains complete SEC provenance metadata for explainability.
    """
    value: Union[int, float]
    unit: str
    fiscal_year: int
    fiscal_period: str
    form: str
    filed_date: str
    concept: str
    source_company: str
    source_cik: str
    accession_number: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    taxonomy: str = "us-gaap"
    selection_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to dictionary."""
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"FinancialFactResult(company='{self.source_company}', concept='{self.concept}', "
            f"value={self.value:,} {self.unit}, fy={self.fiscal_year}, fp='{self.fiscal_period}', "
            f"form='{self.form}', filed='{self.filed_date}')"
        )


class FinancialQueryEngine:
    """
    Retrieval engine for SEC Company Facts.
    Answers structured queries by applying rigorous disambiguation logic:
    - Annual vs quarterly period isolation
    - 10-K vs 10-Q form priority
    - Restatement & amendment resolution (latest filed dates)
    - Full SEC lineage tracking
    """

    def __init__(
        self,
        loader: Optional[SECDataLoader] = None,
        registry: Optional[CompanyRegistry] = None,
        mapper: Optional[Any] = None
    ):
        from src.retrieval.metric_mapper import get_default_mapper
        self.loader = loader or get_default_loader()
        self.registry = registry or get_registry()
        self.mapper = mapper or get_default_mapper()

    def _resolve_company(self, company: Union[str, int, CompanyMetadata]) -> CompanyMetadata:
        """Resolves input to CompanyMetadata."""
        if isinstance(company, CompanyMetadata):
            return company
        return self.registry.get_company(company)

    def _resolve_concepts(self, metric: Union[str, Sequence[str]]) -> List[str]:
        """
        Resolves metric query into an ordered list of candidate SEC XBRL concepts.
        """
        if isinstance(metric, (list, tuple)):
            return list(metric)
        return self.mapper.get_candidate_concepts(str(metric))

    def query_financial_fact(
        self,
        company: Union[str, int, CompanyMetadata],
        metric: Union[str, Sequence[str]],
        fiscal_year: int,
        fiscal_period: str = "FY",
        unit: Optional[str] = "USD",
        taxonomy: str = "us-gaap"
    ) -> Optional[FinancialFactResult]:
        """
        Queries a single financial fact for a company.

        Selection Logic:
        1. Identifies candidate SEC XBRL concepts for the target metric.
        2. Filters facts matching the target fiscal year and period (annual vs quarterly).
        3. For duration metrics (income statement/cash flow), verifies duration matches
           the period type (e.g. ~365 days for FY, ~90 days for discrete quarters to avoid
           cumulative 6-month/9-month periods).
        4. In case of restatements or multiple filings, selects the latest filing date
           and highest-priority form (10-K for FY, 10-Q for quarters).

        :param company: Company name, CIK, or CompanyMetadata object.
        :param metric: Logical metric name (e.g. 'Revenue', 'Net Income', 'Total Assets')
                       or specific XBRL concept name (e.g. 'Revenues').
        :param fiscal_year: Target fiscal year (e.g. 2023, 2024).
        :param fiscal_period: Target period: 'FY' for annual, or 'Q1', 'Q2', 'Q3', 'Q4'.
        :param unit: Target unit (default: 'USD', or None for any).
        :param taxonomy: Target XBRL taxonomy (default: 'us-gaap').
        :return: FinancialFactResult if found, or None if metric is unavailable for the period.
        """
        meta = self._resolve_company(company)
        candidate_concepts = self._resolve_concepts(metric)

        # Load facts for company
        try:
            cf: CompanyFacts = self.loader.load_company_by_cik(meta.cik)
        except Exception as e:
            logger.warning(f"Could not load facts for {meta.entity_name} ({meta.cik}): {e}")
            return None

        # Normalize only relevant concepts to conserve processing time
        normalized = normalize_facts(cf, taxonomies=[taxonomy], concepts=candidate_concepts)
        if not normalized:
            return None

        fp_clean = fiscal_period.strip().upper()
        is_annual_target = fp_clean == "FY"

        # Evaluate candidate facts per concept priority
        for concept in candidate_concepts:
            matching_facts = [f for f in normalized if f.concept == concept and f.value is not None]
            if not matching_facts:
                continue

            candidates: List[tuple[NormalizedFact, int, str]] = []

            for fact in matching_facts:
                # 1. Unit filter
                if unit and fact.unit.upper() != unit.upper():
                    continue

                # 2. Fiscal Period & Period Duration filter
                if is_annual_target:
                    # Must be annual period: fp is FY or form is 10-K
                    if fact.fp and fact.fp.upper() != "FY":
                        continue
                    if not fact.fp and fact.form not in ("10-K", "10-K/A", "20-F"):
                        continue

                    # For duration items: verify length is roughly 1 year (300 to 400 days)
                    if fact.duration_days is not None:
                        if fact.duration_days < 300 or fact.duration_days > 400:
                            continue

                    # Fiscal year alignment:
                    # In SEC EDGAR 10-Ks, comparative prior years are often reported with the current filing's 'fy'.
                    # We must verify period end date year aligns with the requested fiscal year.
                    end_year = fact.end_date.year if fact.end_date else fact.fy
                    if end_year != fiscal_year and fact.fy != fiscal_year:
                        continue
                    # Strong check: period end year must be within 1 year of target fiscal year
                    if fact.end_date and abs(fact.end_date.year - fiscal_year) > 1:
                        continue
                    if fact.end_date and fact.end_date.year != fiscal_year:
                        # Allow only if fiscal year is off by end date month (e.g. Jan fiscal year ends)
                        if not (fact.fy == fiscal_year and fact.end_date.month in (1, 2)):
                            continue

                else:
                    # Quarterly target (Q1, Q2, Q3, Q4)
                    if not fact.fp or fact.fp.upper() != fp_clean:
                        continue

                    # For duration items: reject cumulative 6-month or 9-month YTD periods
                    if fact.duration_days is not None and fact.duration_days > 120:
                        continue

                    # Fiscal year alignment
                    end_year = fact.end_date.year if fact.end_date else fact.fy
                    if end_year != fiscal_year and fact.fy != fiscal_year:
                        continue

                # Form scoring (prefer 10-K for FY, 10-Q for quarters, amendments 10-K/A are handled by filed date)
                form_score = 0
                if is_annual_target and fact.form in ("10-K", "10-K/A", "20-F"):
                    form_score += 50
                elif not is_annual_target and fact.form in ("10-Q", "10-Q/A"):
                    form_score += 50

                filed_str = fact.filed or "1900-01-01"
                candidates.append((fact, form_score, filed_str))

            if not candidates:
                continue

            # Selection sort:
            # 1. Form score (descending)
            # 2. Filed date (descending: restatements / latest revisions win)
            # 3. Calendar frame presence
            # 4. Accession number
            candidates.sort(
                key=lambda x: (
                    x[1],
                    x[2],
                    1 if x[0].frame else 0,
                    x[0].accn or ""
                ),
                reverse=True
            )

            chosen_fact, _, filed_date = candidates[0]
            notes = (
                f"Selected concept '{chosen_fact.concept}' from form '{chosen_fact.form}' "
                f"filed on {filed_date} (candidates evaluated: {len(candidates)})."
            )

            return FinancialFactResult(
                value=chosen_fact.value,
                unit=chosen_fact.unit,
                fiscal_year=fiscal_year,
                fiscal_period=fp_clean,
                form=chosen_fact.form or "Unknown",
                filed_date=filed_date,
                concept=chosen_fact.concept,
                source_company=meta.entity_name,
                source_cik=meta.cik,
                accession_number=chosen_fact.accn,
                start_date=chosen_fact.start,
                end_date=chosen_fact.end,
                taxonomy=chosen_fact.taxonomy,
                selection_notes=notes
            )

        return None

    def query_facts_timeseries(
        self,
        company: Union[str, int, CompanyMetadata],
        metric: Union[str, Sequence[str]],
        start_year: int,
        end_year: int,
        fiscal_period: str = "FY",
        unit: Optional[str] = "USD"
    ) -> List[FinancialFactResult]:
        """
        Retrieves a time-series of financial facts across consecutive fiscal years.

        :param company: Target company.
        :param metric: Target metric or concept.
        :param start_year: Beginning fiscal year (inclusive).
        :param end_year: Ending fiscal year (inclusive).
        :param fiscal_period: 'FY' or quarter identifier.
        :param unit: Unit filter.
        :return: Chronologically sorted list of FinancialFactResult objects.
        """
        results: List[FinancialFactResult] = []
        for year in range(start_year, end_year + 1):
            res = self.query_financial_fact(
                company=company,
                metric=metric,
                fiscal_year=year,
                fiscal_period=fiscal_period,
                unit=unit
            )
            if res is not None:
                results.append(res)
        return results


# Module-level convenience functions
_DEFAULT_ENGINE: Optional[FinancialQueryEngine] = None


def get_default_query_engine() -> FinancialQueryEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = FinancialQueryEngine()
    return _DEFAULT_ENGINE


def query_financial_fact(
    company: Union[str, int, CompanyMetadata],
    metric: Union[str, Sequence[str]],
    fiscal_year: int,
    fiscal_period: str = "FY",
    unit: Optional[str] = "USD"
) -> Optional[FinancialFactResult]:
    """
    Convenience function to query a single structured financial fact.
    """
    return get_default_query_engine().query_financial_fact(
        company=company,
        metric=metric,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        unit=unit
    )


def query_facts_timeseries(
    company: Union[str, int, CompanyMetadata],
    metric: Union[str, Sequence[str]],
    start_year: int,
    end_year: int,
    fiscal_period: str = "FY",
    unit: Optional[str] = "USD"
) -> List[FinancialFactResult]:
    """
    Convenience function to query a multi-year financial fact timeseries.
    """
    return get_default_query_engine().query_facts_timeseries(
        company=company,
        metric=metric,
        start_year=start_year,
        end_year=end_year,
        fiscal_period=fiscal_period,
        unit=unit
    )
