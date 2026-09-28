"""
FARE-Style Statement Extraction Agent.

Answers factual corporate financial questions using grounded SEC Company Facts.
Follows the FARE pipeline:
Query Understanding -> Fact Retrieval -> Evidence Selection -> Answer Generation -> Source Evidence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from src.data.company_registry import CompanyMetadata, CompanyRegistry, get_registry
from src.retrieval.financial_query import (
    FinancialFactResult,
    FinancialQueryEngine,
    get_default_query_engine,
)
from src.retrieval.metric_mapper import MetricMapper, get_default_mapper

logger = logging.getLogger(__name__)

# Common ticker / abbreviation overrides
COMPANY_ABBREVIATIONS: Dict[str, str] = {
    "amd": "ADVANCED MICRO DEVICES INC",
    "aar": "AAR CORP.",
    "spire": "Spire Inc.",
    "akorn": "AKORN INC",
    "cheniere": "Cheniere Energy, Inc.",
    "hess": "HESS CORPORATION",
    "u-haul": "U-Haul Holding Company",
    "uhaul": "U-Haul Holding Company",
    "aflac": "Aflac Incorporated",
}


@dataclass
class StatementExtractionResult:
    """
    Structured outcome of the statement extraction process.
    Guarantees that every numerical answer is grounded in SEC EDGAR facts.
    """
    query: str
    answer: str
    value: Optional[Union[int, float]]
    unit: Optional[str]
    company: str
    metric: str
    fiscal_year: Optional[int]
    fiscal_period: str
    evidence: Optional[Dict[str, Any]]
    status: str
    extracted_entities: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to a clean dictionary."""
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"StatementExtractionResult(company='{self.company}', metric='{self.metric}', "
            f"fy={self.fiscal_year}, status='{self.status}', answer='{self.answer}')"
        )


class StatementExtractionAgent:
    """
    Specialized financial agent that extracts audited financial statement line items.
    Prevents hallucination by requiring exact SEC fact matching.
    """

    def __init__(
        self,
        query_engine: Optional[FinancialQueryEngine] = None,
        registry: Optional[CompanyRegistry] = None,
        mapper: Optional[MetricMapper] = None
    ):
        self.query_engine = query_engine or get_default_query_engine()
        self.registry = registry or get_registry()
        self.mapper = mapper or get_default_mapper()

    # -------------------------------------------------------------------------
    # Pipeline Step 1: Query Understanding & Entity Extraction
    # -------------------------------------------------------------------------

    def understand_query(self, query: str) -> Dict[str, Any]:
        """
        Parses a natural-language query to extract:
        - Target company
        - Target metric
        - Fiscal year
        - Fiscal period (annual or quarterly)
        """
        cleaned_query = query.strip()

        # 1. Extract Fiscal Year
        year = None
        yr_match = re.search(r"(?:FY\s*|fiscal\s*year\s*)?(\b(?:19|20)\d\d\b)|(?:FY)(\d{4})", cleaned_query, re.IGNORECASE)
        if yr_match:
            year_str = yr_match.group(1) or yr_match.group(2)
            year = int(year_str)

        # 2. Extract Fiscal Period (FY vs Q1, Q2, Q3, Q4)
        period = "FY"
        fp_match = re.search(r"\b(Q[1-4]|first\s*quarter|second\s*quarter|third\s*quarter|fourth\s*quarter)\b", cleaned_query, re.IGNORECASE)
        if fp_match:
            fp_raw = fp_match.group(1).upper()
            if "FIRST" in fp_raw or fp_raw == "Q1":
                period = "Q1"
            elif "SECOND" in fp_raw or fp_raw == "Q2":
                period = "Q2"
            elif "THIRD" in fp_raw or fp_raw == "Q3":
                period = "Q3"
            elif "FOURTH" in fp_raw or fp_raw == "Q4":
                period = "Q4"

        # 3. Extract Metric
        identified_metric = None
        # Check canonical metrics and aliases (longest matches first)
        candidate_terms = []
        for canonical, spec in self.mapper.ontology.items():
            candidate_terms.append((canonical, canonical))
            for alias in spec.get("aliases", []):
                candidate_terms.append((alias, canonical))

        candidate_terms.sort(key=lambda x: len(x[0]), reverse=True)
        for term, canonical in candidate_terms:
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, cleaned_query, re.IGNORECASE):
                identified_metric = canonical
                break

        # 4. Extract Company
        identified_company: Optional[CompanyMetadata] = None

        # Check ticker / abbreviation dictionary
        query_words = re.findall(r"\b\w+(?:'\w+)?\b", cleaned_query.lower())
        for word in query_words:
            clean_word = word.replace("'s", "").strip()
            if clean_word in COMPANY_ABBREVIATIONS:
                try:
                    identified_company = self.registry.get_company(COMPANY_ABBREVIATIONS[clean_word])
                    break
                except Exception:
                    pass

        # If not found via abbreviation, test company names in registry
        if not identified_company:
            # Check against indexed company names
            for comp in self.registry.list_companies(include_empty=False):
                # Check entity name or core words
                name_clean = comp.entity_name.lower().replace(",", "").replace(".", "").replace(" inc", "").replace(" corp", "")
                name_tokens = [t for t in name_clean.split() if len(t) > 3]
                if name_clean in cleaned_query.lower():
                    identified_company = comp
                    break
                # Substring check for prominent single-word company names (e.g. Abbott)
                for tok in name_tokens:
                    if re.search(rf"\b{re.escape(tok)}\b", cleaned_query, re.IGNORECASE):
                        identified_company = comp
                        break
                if identified_company:
                    break

        return {
            "company": identified_company,
            "metric": identified_metric,
            "fiscal_year": year,
            "fiscal_period": period,
            "raw_query": query
        }

    # -------------------------------------------------------------------------
    # Pipeline Execution
    # -------------------------------------------------------------------------

    def answer_query(self, query: str) -> StatementExtractionResult:
        """
        Executes the FARE Statement Extraction pipeline:
        1. Query Understanding
        2. Financial Fact Retrieval
        3. Evidence Selection
        4. Answer Generation
        5. Source Evidence
        """
        # Step 1: Query Understanding
        slots = self.understand_query(query)
        comp_meta: Optional[CompanyMetadata] = slots.get("company")
        metric: Optional[str] = slots.get("metric")
        fiscal_year: Optional[int] = slots.get("fiscal_year")
        fiscal_period: str = slots.get("fiscal_period", "FY")

        extracted_info = {
            "company_name": comp_meta.entity_name if comp_meta else None,
            "company_cik": comp_meta.cik if comp_meta else None,
            "metric": metric,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
        }

        # Validate extracted slots
        if not comp_meta:
            return StatementExtractionResult(
                query=query,
                answer="Could not identify the target company from your query. Please specify an SEC registrant name or CIK.",
                value=None,
                unit=None,
                company="Unknown",
                metric=metric or "Unknown",
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                evidence=None,
                status="ENTITY_NOT_FOUND",
                extracted_entities=extracted_info
            )

        if not metric:
            return StatementExtractionResult(
                query=query,
                answer=f"Could not identify the financial metric requested for '{comp_meta.entity_name}'. Please request a recognized line item (e.g. Revenue, Net Income, Total Assets, Cash).",
                value=None,
                unit=None,
                company=comp_meta.entity_name,
                metric="Unknown",
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                evidence=None,
                status="UNRESOLVED_METRIC",
                extracted_entities=extracted_info
            )

        if not fiscal_year:
            return StatementExtractionResult(
                query=query,
                answer=f"Could not identify the target fiscal year for '{comp_meta.entity_name}'. Please specify a year (e.g. 2023 or 2024).",
                value=None,
                unit=None,
                company=comp_meta.entity_name,
                metric=metric,
                fiscal_year=None,
                fiscal_period=fiscal_period,
                evidence=None,
                status="MISSING_FISCAL_YEAR",
                extracted_entities=extracted_info
            )

        # Step 2: Financial Fact Retrieval
        fact_result: Optional[FinancialFactResult] = self.query_engine.query_financial_fact(
            company=comp_meta,
            metric=metric,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period
        )

        # Step 3: Evidence Selection & Verification
        if not fact_result or fact_result.value is None:
            period_label = f"fiscal year {fiscal_year}" if fiscal_period == "FY" else f"{fiscal_period} {fiscal_year}"
            return StatementExtractionResult(
                query=query,
                answer=f"No audited SEC financial fact was found for {comp_meta.entity_name}'s {metric} in {period_label}.",
                value=None,
                unit=None,
                company=comp_meta.entity_name,
                metric=metric,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                evidence=None,
                status="FACT_NOT_FOUND",
                extracted_entities=extracted_info
            )

        # Step 4: Answer Generation
        evidence = fact_result.to_dict()
        formatted_val = self._format_currency_value(fact_result.value, fact_result.unit)
        period_str = f"FY{fiscal_year}" if fiscal_period == "FY" else f"{fiscal_period} FY{fiscal_year}"

        answer = (
            f"{comp_meta.entity_name} reported {metric} of {formatted_val} "
            f"for {period_str} (Form {fact_result.form}, filed {fact_result.filed_date})."
        )

        # Step 5: Source Evidence Return
        return StatementExtractionResult(
            query=query,
            answer=answer,
            value=fact_result.value,
            unit=fact_result.unit,
            company=comp_meta.entity_name,
            metric=metric,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            evidence=evidence,
            status="SUCCESS",
            extracted_entities=extracted_info
        )

    def _format_currency_value(self, value: Union[int, float], unit: str) -> str:
        """Formats numbers with commas and billion/million scale suffixes for readability."""
        if unit.upper() == "USD":
            abs_val = abs(value)
            sign = "-" if value < 0 else ""
            if abs_val >= 1_000_000_000:
                scale_str = f" (${sign}{abs_val / 1_000_000_000:.2f}B)"
            elif abs_val >= 1_000_000:
                scale_str = f" (${sign}{abs_val / 1_000_000:.2f}M)"
            else:
                scale_str = ""
            return f"${value:,.0f} USD{scale_str}"

        return f"{value:,.0f} {unit}"


# Singleton instance and convenience function
_DEFAULT_STATEMENT_AGENT: Optional[StatementExtractionAgent] = None


def get_default_statement_agent() -> StatementExtractionAgent:
    global _DEFAULT_STATEMENT_AGENT
    if _DEFAULT_STATEMENT_AGENT is None:
        _DEFAULT_STATEMENT_AGENT = StatementExtractionAgent()
    return _DEFAULT_STATEMENT_AGENT


def extract_financial_statement_fact(query: str) -> StatementExtractionResult:
    """Convenience function to run the Statement Extraction Agent."""
    return get_default_statement_agent().answer_query(query)
