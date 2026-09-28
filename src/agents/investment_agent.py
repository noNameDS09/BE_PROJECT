"""
FARE-Style Investment / Financial Analysis Agent.

Performs multi-period financial reasoning using retrieved SEC facts and deterministic
calculations. Strictly partitions every output into:
- FACT (audited SEC XBRL data with accession numbers)
- CALCULATION (deterministic arithmetic outputs with mathematical formulas)
- INTERPRETATION (objective financial reasoning derived exclusively from calculations)
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
}


@dataclass
class InvestmentAnalysisResult:
    """
    Structured outcome of an investment analysis.
    Explicitly distinguishes FACT, CALCULATION, and INTERPRETATION.
    """
    query: str
    company: str
    cik: str
    start_year: int
    end_year: int
    facts: List[Dict[str, Any]] = field(default_factory=list)
    calculations: List[Dict[str, Any]] = field(default_factory=list)
    interpretations: List[str] = field(default_factory=list)
    summary: str = ""
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to a clean dictionary."""
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"InvestmentAnalysisResult(company='{self.company}', period={self.start_year}-{self.end_year}, "
            f"facts={len(self.facts)}, calculations={len(self.calculations)}, status='{self.status}')"
        )


class InvestmentAgent:
    """
    FARE-inspired Investment & Financial Analysis Agent.
    Orchestrates fact retrieval, calls deterministic calculation tools,
    and conducts trend analysis without allowing LLM arithmetic.
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
        Extracts company and timeframe (start_year, end_year) from user request.
        """
        cleaned_query = query.strip()

        # 1. Check for year range: e.g. "from 2022 to 2024", "2022 - 2024", "between 2021 and 2023"
        range_match = re.search(
            r"(?:from|between)?\s*(\b(?:19|20)\d{2}\b)\s*(?:to|-|through|and)\s*(\b(?:19|20)\d{2}\b)",
            cleaned_query,
            re.IGNORECASE
        )
        if range_match:
            y1 = int(range_match.group(1))
            y2 = int(range_match.group(2))
            start_year = min(y1, y2)
            end_year = max(y1, y2)
        else:
            # Single year reference: e.g. "in 2024" -> 2-year window (2023 to 2024)
            single_match = re.search(r"(?:in|for|FY)?\s*(\b(?:19|20)\d{2}\b)", cleaned_query, re.IGNORECASE)
            if single_match:
                end_year = int(single_match.group(1))
                start_year = end_year - 1
            else:
                # Default recent 3-year window
                start_year = 2022
                end_year = 2024

        # 2. Extract company
        identified_company: Optional[CompanyMetadata] = None
        query_words = re.findall(r"\b\w+(?:'\w+)?\b", cleaned_query.lower())
        for word in query_words:
            clean_word = word.replace("'s", "").strip()
            if clean_word in COMPANY_ABBREVIATIONS:
                try:
                    identified_company = self.registry.get_company(COMPANY_ABBREVIATIONS[clean_word])
                    break
                except Exception:
                    pass

        if not identified_company:
            for comp in self.registry.list_companies(include_empty=False):
                name_clean = comp.entity_name.lower().replace(",", "").replace(".", "").replace(" inc", "").replace(" corp", "")
                name_tokens = [t for t in name_clean.split() if len(t) > 3]
                if name_clean in cleaned_query.lower():
                    identified_company = comp
                    break
                for tok in name_tokens:
                    if re.search(rf"\b{re.escape(tok)}\b", cleaned_query, re.IGNORECASE):
                        identified_company = comp
                        break
                if identified_company:
                    break

        return {
            "company": identified_company,
            "start_year": start_year,
            "end_year": end_year,
            "raw_query": query
        }

    def analyze_company_performance(
        self,
        company: Union[str, CompanyMetadata],
        start_year: int,
        end_year: int,
        query: str = ""
    ) -> InvestmentAnalysisResult:
        """
        Performs end-to-end multi-period investment analysis:
        1. Retrieves factual time-series data (FACT).
        2. Executes deterministic mathematical tools (CALCULATION).
        3. Formulates structured financial reasoning (INTERPRETATION).
        """
        # Resolve company
        if isinstance(company, CompanyMetadata):
            meta = company
        else:
            try:
                meta = self.registry.get_company(company)
            except Exception as e:
                return InvestmentAnalysisResult(
                    query=query,
                    company=str(company),
                    cik="Unknown",
                    start_year=start_year,
                    end_year=end_year,
                    status="COMPANY_NOT_FOUND",
                    summary=f"Could not identify company: {e}"
                )

        facts_list: List[Dict[str, Any]] = []
        calculations_list: List[Dict[str, Any]] = []
        interpretations_list: List[str] = []

        # ---------------------------------------------------------------------
        # 1. Fact Retrieval (FACT)
        # ---------------------------------------------------------------------
        rev_facts = self.query_engine.query_facts_timeseries(meta, "Revenue", start_year, end_year)
        ni_facts = self.query_engine.query_facts_timeseries(meta, "Net Income", start_year, end_year)
        asset_facts = self.query_engine.query_facts_timeseries(meta, "Total Assets", start_year, end_year)
        equity_facts = self.query_engine.query_facts_timeseries(meta, "Stockholders Equity", start_year, end_year)

        for fact in (rev_facts + ni_facts + asset_facts + equity_facts):
            f_dict = fact.to_dict()
            f_dict["type"] = "FACT"
            facts_list.append(f_dict)

        if not rev_facts:
            return InvestmentAnalysisResult(
                query=query,
                company=meta.entity_name,
                cik=meta.cik,
                start_year=start_year,
                end_year=end_year,
                status="INSUFFICIENT_DATA",
                summary=f"No audited revenue data found for {meta.entity_name} between {start_year} and {end_year}."
            )

        # ---------------------------------------------------------------------
        # 2. Deterministic Calculations (CALCULATION)
        # ---------------------------------------------------------------------
        growth_results: List[CalculationResult] = []
        for i in range(1, len(rev_facts)):
            curr_f = rev_facts[i]
            prev_f = rev_facts[i - 1]
            if curr_f.fiscal_year == prev_f.fiscal_year + 1:
                g_res = self.calculator.calculate_revenue_growth(curr_f, prev_f)
                growth_results.append(g_res)
                c_dict = g_res.to_dict()
                c_dict["type"] = "CALCULATION"
                c_dict["fiscal_year"] = curr_f.fiscal_year
                calculations_list.append(c_dict)

        # Compute latest period ratios
        latest_year = rev_facts[-1].fiscal_year
        ratios = self.calculator.compute_all_ratios(meta.entity_name, latest_year)
        for name, calc in ratios.items():
            if calc.status == "SUCCESS":
                c_dict = calc.to_dict()
                c_dict["type"] = "CALCULATION"
                c_dict["fiscal_year"] = latest_year
                calculations_list.append(c_dict)

        # ---------------------------------------------------------------------
        # 3. Trend Analysis & Reasoning (INTERPRETATION)
        # ---------------------------------------------------------------------
        # Interpretation 1: Revenue Trajectory
        if growth_results:
            growth_strs = [f"{g.value:+.2f}% in {g.inputs[0].get('fiscal_year')}" for g in growth_results if g.value is not None]
            latest_g = growth_results[-1].value
            if latest_g is not None:
                if latest_g > 10.0:
                    trend_adj = "strong expansion"
                elif latest_g > 0:
                    trend_adj = "modest growth"
                else:
                    trend_adj = "contraction"
                interp_rev = (
                    f"[INTERPRETATION] Revenue Trajectory: {meta.entity_name} recorded {trend_adj} "
                    f"with YoY growth rates of {', '.join(growth_strs)}."
                )
                interpretations_list.append(interp_rev)

        # Interpretation 2: Profitability & Margins
        net_margin_calc = ratios.get("Net Profit Margin")
        if net_margin_calc and net_margin_calc.value is not None:
            m_val = net_margin_calc.value
            margin_desc = "exceptional" if m_val > 20 else ("healthy" if m_val > 10 else "thin")
            interp_margin = (
                f"[INTERPRETATION] Profitability: Net profit margin stood at {m_val:.2f}% in {latest_year}, "
                f"reflecting {margin_desc} bottom-line conversion."
            )
            interpretations_list.append(interp_margin)

        # Interpretation 3: Capital Efficiency (ROA & ROE)
        roa_calc = ratios.get("ROA")
        roe_calc = ratios.get("ROE")
        if roa_calc and roa_calc.value is not None and roe_calc and roe_calc.value is not None:
            interp_returns = (
                f"[INTERPRETATION] Capital Efficiency: The firm generated an ROE of {roe_calc.value:.2f}% "
                f"and an ROA of {roa_calc.value:.2f}% in {latest_year}."
            )
            interpretations_list.append(interp_returns)

        # Interpretation 4: Balance Sheet Health & Liquidity
        cr_calc = ratios.get("Current Ratio")
        dr_calc = ratios.get("Debt Ratio")
        if cr_calc and cr_calc.value is not None:
            liq_desc = "strong short-term liquidity" if cr_calc.value >= 1.5 else "tight working capital"
            dr_str = f" accompanied by a debt-to-assets ratio of {dr_calc.value:.2f}" if dr_calc and dr_calc.value is not None else ""
            interp_balance = (
                f"[INTERPRETATION] Solvency & Liquidity: A current ratio of {cr_calc.value:.2f}x indicates {liq_desc}{dr_str}."
            )
            interpretations_list.append(interp_balance)

        # Format Summary
        summary = (
            f"Financial Analysis of {meta.entity_name} ({start_year}–{end_year}):\n"
            + "\n".join(interpretations_list)
        )

        return InvestmentAnalysisResult(
            query=query,
            company=meta.entity_name,
            cik=meta.cik,
            start_year=start_year,
            end_year=end_year,
            facts=facts_list,
            calculations=calculations_list,
            interpretations=interpretations_list,
            summary=summary,
            status="SUCCESS"
        )

    def answer_query(self, query: str) -> InvestmentAnalysisResult:
        """Parses user query and runs financial analysis."""
        parsed = self.parse_query(query)
        company = parsed.get("company")
        if not company:
            return InvestmentAnalysisResult(
                query=query,
                company="Unknown",
                cik="Unknown",
                start_year=parsed["start_year"],
                end_year=parsed["end_year"],
                status="COMPANY_NOT_FOUND",
                summary="Could not identify the target company from the query. Please specify an SEC registrant name or CIK."
            )

        return self.analyze_company_performance(
            company=company,
            start_year=parsed["start_year"],
            end_year=parsed["end_year"],
            query=query
        )


# Singleton instance and convenience function
_DEFAULT_INVESTMENT_AGENT: Optional[InvestmentAgent] = None


def get_default_investment_agent() -> InvestmentAgent:
    global _DEFAULT_INVESTMENT_AGENT
    if _DEFAULT_INVESTMENT_AGENT is None:
        _DEFAULT_INVESTMENT_AGENT = InvestmentAgent()
    return _DEFAULT_INVESTMENT_AGENT


def analyze_financial_performance(
    query_or_company: str,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None
) -> InvestmentAnalysisResult:
    """Convenience function to run the Investment Agent."""
    agent = get_default_investment_agent()
    if start_year is not None and end_year is not None:
        return agent.analyze_company_performance(
            company=query_or_company,
            start_year=start_year,
            end_year=end_year,
            query=f"Analyze {query_or_company} from {start_year} to {end_year}"
        )
    return agent.answer_query(query_or_company)
