"""
Financial Metric Mapping & SEC Concept Resolution Module.

Maintains a controlled dictionary of financial metrics and provides dynamic,
company-specific resolution of logical metrics to available SEC XBRL concepts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Union

from src.data.company_registry import CompanyMetadata, get_registry
from src.data.sec_loader import CompanyFacts, SECDataLoader, get_default_loader

logger = logging.getLogger(__name__)

UNRESOLVED_STATUS = "Metric unavailable / unresolved"

# Controlled Metric Definitions & Ordered Concept Fallback Hierarchy
CONTROLLED_METRICS: Dict[str, Dict[str, Any]] = {
    "Revenue": {
        "description": "Total revenue or net sales recognized during the period",
        "statement": "Income Statement",
        "type": "duration",
        "concepts": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "GrossRevenue",
            "TotalRevenuesAndOtherIncome",
            "Revenue",
        ],
        "aliases": ["revenue", "revenues", "sales", "net sales", "topline", "total revenue"],
    },
    "Net Income": {
        "description": "Net income or loss attributable to the parent entity",
        "statement": "Income Statement",
        "type": "duration",
        "concepts": [
            "NetIncomeLoss",
            "ProfitLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ],
        "aliases": ["net income", "net_income", "net profit", "net earnings", "profit", "bottom line"],
    },
    "Total Assets": {
        "description": "Sum of the carrying amounts of all assets",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "Assets",
        ],
        "aliases": ["total assets", "assets", "total_assets"],
    },
    "Total Liabilities": {
        "description": "Sum of the carrying amounts of all liabilities",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "Liabilities",
        ],
        "aliases": ["total liabilities", "liabilities", "total_liabilities"],
    },
    "Stockholders Equity": {
        "description": "Total equity attributable to shareholders/stockholders",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "CommonStockholdersEquity",
            "Equity",
        ],
        "aliases": ["stockholders equity", "stockholders_equity", "shareholders equity", "equity", "book value"],
    },
    "Cash": {
        "description": "Cash and cash equivalents held at the balance sheet date",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "Cash",
            "CashAndCashEquivalents",
        ],
        "aliases": ["cash", "cash and equivalents", "cash and cash equivalents", "cash balance"],
    },
    "Current Assets": {
        "description": "Assets expected to be realized in cash, sold, or consumed within one year",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "AssetsCurrent",
        ],
        "aliases": ["current assets", "current_assets"],
    },
    "Current Liabilities": {
        "description": "Liabilities due to be settled within one year",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "LiabilitiesCurrent",
        ],
        "aliases": ["current liabilities", "current_liabilities"],
    },
    "Operating Income": {
        "description": "Income before interest, taxes, and non-operating items (EBIT)",
        "statement": "Income Statement",
        "type": "duration",
        "concepts": [
            "OperatingIncomeLoss",
        ],
        "aliases": ["operating income", "operating_income", "operating profit", "ebit"],
    },
    "Gross Profit": {
        "description": "Revenue minus cost of goods/services sold",
        "statement": "Income Statement",
        "type": "duration",
        "concepts": [
            "GrossProfit",
        ],
        "aliases": ["gross profit", "gross_profit", "gross margin dollar"],
    },
    "Operating Cash Flow": {
        "description": "Net cash provided by or used in operating activities",
        "statement": "Cash Flows",
        "type": "duration",
        "concepts": [
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ],
        "aliases": ["operating cash flow", "operating_cash_flow", "cfo", "cash flow from operations"],
    },
    "Long Term Debt": {
        "description": "Long-term debt obligations due beyond one year",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "LongTermDebtNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
            "LongTermDebt",
        ],
        "aliases": ["long term debt", "long_term_debt", "noncurrent debt", "debt"],
    },
    "Short Term Debt": {
        "description": "Current portion of debt and short-term borrowings",
        "statement": "Balance Sheet",
        "type": "instant",
        "concepts": [
            "DebtCurrent",
            "ShortTermBorrowings",
            "LongTermDebtCurrent",
        ],
        "aliases": ["short term debt", "short_term_debt", "current debt"],
    },
}


@dataclass
class MetricResolutionResult:
    """
    Result of a metric resolution attempt for a specific company.
    """
    status: str
    canonical_metric: str
    concept: Optional[str]
    taxonomy: str = "us-gaap"
    statement: Optional[str] = None
    period_type: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        return self.status != UNRESOLVED_STATUS and self.concept is not None

    def __str__(self) -> str:
        if self.is_resolved:
            return self.concept or UNRESOLVED_STATUS
        return UNRESOLVED_STATUS

    def __repr__(self) -> str:
        return (
            f"MetricResolutionResult(metric='{self.canonical_metric}', "
            f"concept='{self.concept}', status='{self.status}')"
        )


class MetricMapper:
    """
    Ontology manager that dynamically resolves standard financial metrics
    to company-specific SEC XBRL concepts without hardcoding.
    """

    def __init__(
        self,
        loader: Optional[SECDataLoader] = None,
        ontology: Optional[Dict[str, Dict[str, Any]]] = None
    ):
        self.loader = loader or get_default_loader()
        self.ontology = ontology or CONTROLLED_METRICS
        self._alias_index: Dict[str, str] = {}
        self._build_alias_index()

    def _build_alias_index(self) -> None:
        """Builds lookup index from normalized aliases to canonical metric names."""
        self._alias_index.clear()
        for canonical, spec in self.ontology.items():
            self._alias_index[canonical.lower()] = canonical
            for alias in spec.get("aliases", []):
                self._alias_index[alias.lower().strip()] = canonical

    def get_canonical_name(self, metric_query: str) -> Optional[str]:
        """
        Normalizes any metric alias or query string to its canonical metric name.
        Example: 'topline' -> 'Revenue', 'ebit' -> 'Operating Income'
        """
        cleaned = re.sub(r"[\s_-]+", " ", str(metric_query).strip()).lower()
        return self._alias_index.get(cleaned)

    def list_supported_metrics(self) -> List[str]:
        """Returns list of canonical metric names supported by the ontology."""
        return list(self.ontology.keys())

    def get_candidate_concepts(self, metric_query: str) -> List[str]:
        """
        Returns the prioritized list of XBRL concepts for a metric query.
        """
        canonical = self.get_canonical_name(metric_query)
        if canonical and canonical in self.ontology:
            return list(self.ontology[canonical]["concepts"])
        # If not recognized as a registered metric, return the query itself as a direct concept
        return [str(metric_query).strip()]

    def resolve_metric(
        self,
        company: Union[str, int, CompanyFacts, CompanyMetadata],
        metric: str,
        taxonomy: str = "us-gaap"
    ) -> MetricResolutionResult:
        """
        Determines the appropriate available SEC concept for a company.

        :param company: Target company (name, CIK, CompanyFacts, or CompanyMetadata).
        :param metric: Logical metric name or alias (e.g. 'revenue', 'Net Income', 'assets').
        :param taxonomy: Target taxonomy (default: 'us-gaap').
        :return: MetricResolutionResult (status='RESOLVED' with concept, or UNRESOLVED_STATUS).
        """
        canonical = self.get_canonical_name(metric) or str(metric).strip()

        # Load facts for the target company
        try:
            if isinstance(company, CompanyFacts):
                cf = company
            elif isinstance(company, CompanyMetadata):
                cf = self.loader.load_company_by_cik(company.cik)
            else:
                cf = self.loader.load_company_by_cik(company)
        except Exception:
            # Try loading by name if CIK lookup failed
            try:
                cf = self.loader.load_company_by_name(str(company))
            except Exception as e:
                logger.warning(f"Could not load company facts for '{company}': {e}")
                return MetricResolutionResult(
                    status=UNRESOLVED_STATUS,
                    canonical_metric=canonical,
                    concept=None,
                    taxonomy=taxonomy
                )

        # Inspect available concepts in the company's fact tree
        available_tax = cf.facts.get(taxonomy, {})
        if not isinstance(available_tax, dict) or not available_tax:
            return MetricResolutionResult(
                status=UNRESOLVED_STATUS,
                canonical_metric=canonical,
                concept=None,
                taxonomy=taxonomy
            )

        candidate_concepts = self.get_candidate_concepts(metric)

        # Find the first available concept according to the ontology precedence
        for candidate in candidate_concepts:
            if candidate in available_tax:
                metric_spec = self.ontology.get(canonical, {})
                return MetricResolutionResult(
                    status="RESOLVED",
                    canonical_metric=canonical,
                    concept=candidate,
                    taxonomy=taxonomy,
                    statement=metric_spec.get("statement"),
                    period_type=metric_spec.get("type")
                )

        return MetricResolutionResult(
            status=UNRESOLVED_STATUS,
            canonical_metric=canonical,
            concept=None,
            taxonomy=taxonomy
        )


# Singleton instance & module convenience functions
_DEFAULT_MAPPER: Optional[MetricMapper] = None


def get_default_mapper() -> MetricMapper:
    global _DEFAULT_MAPPER
    if _DEFAULT_MAPPER is None:
        _DEFAULT_MAPPER = MetricMapper()
    return _DEFAULT_MAPPER


def resolve_metric(
    company: Union[str, int, CompanyFacts, CompanyMetadata],
    metric: str,
    taxonomy: str = "us-gaap"
) -> Union[str, MetricResolutionResult]:
    """
    Convenience function to resolve a metric for a company.
    Returns MetricResolutionResult. Its string representation returns
    either the resolved concept or 'Metric unavailable / unresolved'.
    """
    return get_default_mapper().resolve_metric(company=company, metric=metric, taxonomy=taxonomy)


def list_supported_metrics() -> List[str]:
    """Returns all supported canonical financial metrics."""
    return get_default_mapper().list_supported_metrics()
