"""
FARE-Style Comparison Agent.

Performs multi-company financial comparisons using grounded SEC facts and
deterministic calculations. Generates transparent, side-by-side metric tables
without arbitrary qualitative ranking unless explicitly requested for a specific metric.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from src.data.company_registry import CompanyMetadata, CompanyRegistry, get_registry
from src.retrieval.financial_query import (
    FinancialFactResult,
    FinancialQueryEngine,
    get_default_query_engine,
)
from src.tools.financial_calculator import (
    CalculationResult,
    FinancialCalculator,
    get_default_calculator,
)

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
    "acme": "ACME UNITED CORP",
}


@dataclass
class ComparisonResult:
    """
    Structured outcome of a multi-company financial comparison.
    Contains aligned metrics, source facts, and deterministic calculations.
    """
    query: str
    fiscal_year: int
    companies: List[str]
    company_metadata: List[Dict[str, Any]]
    metrics_table: List[Dict[str, Any]]
    company_facts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    company_calculations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    comparative_analysis: List[str] = field(default_factory=list)
    summary: str = ""
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to dictionary."""
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"ComparisonResult(companies={self.companies}, year={self.fiscal_year}, "
            f"metrics_count={len(self.metrics_table)}, status='{self.status}')"
        )


class ComparisonAgent:
    """
    FARE-inspired Comparison Agent for multi-entity corporate financial evaluation.
    Retrieves facts for Company A and Company B in parallel, executes deterministic
    calculations, aligns the comparative metrics table, and formulates objective reasoning.
    """

    def __init__(
        self,
        query_engine: Optional[FinancialQueryEngine] = None,
        calculator: Optional[FinancialCalculator] = None,
        registry: Optional[CompanyRegistry] = None
    ):
        self.query_engine = query_engine or get_default_query_engine()
        self.calculator = calculator or get_default_calculator()
        self.registry = registry or get_registry()

    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parses multi-company query to extract companies and target fiscal year.
        """
        cleaned_query = query.strip()

        # 1. Extract Fiscal Year
        year = None
        yr_match = re.search(r"(?:FY\s*|fiscal\s*year\s*)?(\b(?:19|20)\d{2}\b)|(?:FY)(\d{4})", cleaned_query, re.IGNORECASE)
        if yr_match:
            year_str = yr_match.group(1) or yr_match.group(2)
            year = int(year_str)
        else:
            year = 2023  # Default fallback year

        # 2. Extract multiple companies
        matched_companies: List[CompanyMetadata] = []

        # Check ticker / abbreviation overrides
        words = re.findall(r"\b\w+\b", cleaned_query.lower())
        for w in words:
            if w in COMPANY_ABBREVIATIONS:
                try:
                    comp = self.registry.get_company(COMPANY_ABBREVIATIONS[w])
                    if comp not in matched_companies:
                        matched_companies.append(comp)
                except Exception:
                    pass

        # Check against registered entities
        for comp in self.registry.list_companies(include_empty=False):
            name_clean = comp.entity_name.lower().replace(",", "").replace(".", "").replace(" inc", "").replace(" corp", "")
            tokens = [t for t in name_clean.split() if len(t) > 3]
            if name_clean in cleaned_query.lower():
                if comp not in matched_companies:
                    matched_companies.append(comp)
                continue

            for tok in tokens:
                if re.search(rf"\b{re.escape(tok)}\b", cleaned_query, re.IGNORECASE):
                    if comp not in matched_companies:
                        matched_companies.append(comp)
                    break

        return {
            "companies": matched_companies,
            "fiscal_year": year,
            "raw_query": query
        }

    def compare_companies(
        self,
        companies: List[Union[str, CompanyMetadata]],
        fiscal_year: int,
        query: str = ""
    ) -> ComparisonResult:
        """
        Executes multi-company comparison workflow:
        Company A -> Retrieve facts -> Deterministic calculations
        Company B -> Retrieve facts -> Deterministic calculations
                  -> Comparative metrics table
                  -> Objective comparison reasoning
        """
        # Resolve company metadata
        resolved_metas: List[CompanyMetadata] = []
        for c in companies:
            if isinstance(c, CompanyMetadata):
                resolved_metas.append(c)
            else:
                try:
                    resolved_metas.append(self.registry.get_company(c))
                except Exception as e:
                    logger.warning(f"Could not resolve company '{c}': {e}")

        if len(resolved_metas) < 2:
            return ComparisonResult(
                query=query,
                fiscal_year=fiscal_year,
                companies=[c.entity_name for c in resolved_metas],
                company_metadata=[c.to_dict() for c in resolved_metas],
                metrics_table=[],
                status="INSUFFICIENT_COMPANIES",
                summary="Comparison requires at least two valid companies."
            )

        company_names = [m.entity_name for m in resolved_metas]
        facts_by_company: Dict[str, List[Dict[str, Any]]] = {}
        calcs_by_company: Dict[str, Dict[str, Any]] = {}

        # ---------------------------------------------------------------------
        # 1. Retrieve Facts & Compute Ratios for Each Company
        # ---------------------------------------------------------------------
        for meta in resolved_metas:
            c_name = meta.entity_name
            # Retrieve primary statements facts
            rev = self.query_engine.query_financial_fact(meta, "Revenue", fiscal_year)
            ni = self.query_engine.query_financial_fact(meta, "Net Income", fiscal_year)
            assets = self.query_engine.query_financial_fact(meta, "Total Assets", fiscal_year)
            equity = self.query_engine.query_financial_fact(meta, "Stockholders Equity", fiscal_year)
            cash = self.query_engine.query_financial_fact(meta, "Cash", fiscal_year)

            facts_by_company[c_name] = [
                f.to_dict() for f in (rev, ni, assets, equity, cash) if f is not None
            ]

            # Compute deterministic ratios
            company_ratios = self.calculator.compute_all_ratios(meta.entity_name, fiscal_year)
            calcs_by_company[c_name] = {
                metric: res.to_dict() for metric, res in company_ratios.items()
            }

        # ---------------------------------------------------------------------
        # 2. Build Side-by-Side Comparative Metrics Table
        # ---------------------------------------------------------------------
        standard_comparison_lines = [
            ("Revenue", "USD", True),
            ("Net Income", "USD", True),
            ("Total Assets", "USD", True),
            ("Cash", "USD", True),
            ("Revenue Growth", "%", False),
            ("Net Profit Margin", "%", False),
            ("ROA", "%", False),
            ("ROE", "%", False),
            ("Current Ratio", "ratio", False),
            ("Debt-to-Equity", "ratio", False),
            ("Debt Ratio", "ratio", False),
        ]

        metrics_table: List[Dict[str, Any]] = []

        for metric_name, unit, is_fact in standard_comparison_lines:
            row: Dict[str, Any] = {
                "metric": metric_name,
                "unit": unit,
                "values": {}
            }
            for meta in resolved_metas:
                c_name = meta.entity_name
                val = None
                if is_fact:
                    # Look up from retrieved facts
                    f_list = facts_by_company.get(c_name, [])
                    match = next((f for f in f_list if f["concept"] and metric_name.lower() in f.get("concept", "").lower() or (metric_name == "Revenue" and "revenue" in f.get("concept", "").lower())), None)
                    if match:
                        val = match["value"]
                else:
                    # Look up from calculations
                    c_dict = calcs_by_company.get(c_name, {})
                    if metric_name in c_dict and c_dict[metric_name].get("status") == "SUCCESS":
                        val = c_dict[metric_name].get("value")

                row["values"][c_name] = val

            metrics_table.append(row)

        # ---------------------------------------------------------------------
        # 3. Formulate Transparent Comparative Reasoning
        # ---------------------------------------------------------------------
        analysis_lines: List[str] = []
        c1, c2 = company_names[0], company_names[1]

        # Scale Comparison
        rev_row = next((r for r in metrics_table if r["metric"] == "Revenue"), None)
        if rev_row and rev_row["values"].get(c1) is not None and rev_row["values"].get(c2) is not None:
            v1, v2 = rev_row["values"][c1], rev_row["values"][c2]
            analysis_lines.append(
                f"Scale: {c1} reported revenue of ${v1:,.0f} USD compared to ${v2:,.0f} USD for {c2} in FY{fiscal_year}."
            )

        # Profitability Comparison
        margin_row = next((r for r in metrics_table if r["metric"] == "Net Profit Margin"), None)
        if margin_row and margin_row["values"].get(c1) is not None and margin_row["values"].get(c2) is not None:
            m1, m2 = margin_row["values"][c1], margin_row["values"][c2]
            analysis_lines.append(
                f"Profitability: {c1}'s net profit margin was {m1:.2f}% versus {m2:.2f}% for {c2}."
            )

        # Return / Efficiency Comparison
        roa_row = next((r for r in metrics_table if r["metric"] == "ROA"), None)
        if roa_row and roa_row["values"].get(c1) is not None and roa_row["values"].get(c2) is not None:
            r1, r2 = roa_row["values"][c1], roa_row["values"][c2]
            analysis_lines.append(
                f"Capital Efficiency: ROA was {r1:.2f}% for {c1} and {r2:.2f}% for {c2}."
            )

        # Liquidity Comparison
        cr_row = next((r for r in metrics_table if r["metric"] == "Current Ratio"), None)
        if cr_row and cr_row["values"].get(c1) is not None and cr_row["values"].get(c2) is not None:
            cr1, cr2 = cr_row["values"][c1], cr_row["values"][c2]
            analysis_lines.append(
                f"Liquidity: {c1} maintained a current ratio of {cr1:.2f}x compared to {cr2:.2f}x for {c2}."
            )

        summary = (
            f"Financial Comparison: {' vs '.join(company_names)} (FY{fiscal_year})\n"
            + "\n".join(f"- {line}" for line in analysis_lines)
        )

        return ComparisonResult(
            query=query,
            fiscal_year=fiscal_year,
            companies=company_names,
            company_metadata=[m.to_dict() for m in resolved_metas],
            metrics_table=metrics_table,
            company_facts=facts_by_company,
            company_calculations=calcs_by_company,
            comparative_analysis=analysis_lines,
            summary=summary,
            status="SUCCESS"
        )

    def answer_query(self, query: str) -> ComparisonResult:
        """Parses natural-language user query and executes comparative evaluation."""
        parsed = self.parse_query(query)
        companies = parsed.get("companies", [])
        fiscal_year = parsed.get("fiscal_year", 2023)

        if len(companies) < 2:
            return ComparisonResult(
                query=query,
                fiscal_year=fiscal_year,
                companies=[c.entity_name for c in companies],
                company_metadata=[c.to_dict() for c in companies],
                metrics_table=[],
                status="INSUFFICIENT_COMPANIES",
                summary="Please provide at least two company names or CIKs to compare (e.g. 'Compare Abbott and AMD in 2023')."
            )

        return self.compare_companies(
            companies=companies,
            fiscal_year=fiscal_year,
            query=query
        )


# Singleton instance and convenience function
_DEFAULT_COMPARISON_AGENT: Optional[ComparisonAgent] = None


def get_default_comparison_agent() -> ComparisonAgent:
    global _DEFAULT_COMPARISON_AGENT
    if _DEFAULT_COMPARISON_AGENT is None:
        _DEFAULT_COMPARISON_AGENT = ComparisonAgent()
    return _DEFAULT_COMPARISON_AGENT


def compare_companies(
    query_or_companies: Union[str, List[Union[str, CompanyMetadata]]],
    fiscal_year: Optional[int] = None
) -> ComparisonResult:
    """Convenience function to run the Comparison Agent."""
    agent = get_default_comparison_agent()
    if isinstance(query_or_companies, list):
        year = fiscal_year or 2023
        return agent.compare_companies(companies=query_or_companies, fiscal_year=year)
    return agent.answer_query(str(query_or_companies))
