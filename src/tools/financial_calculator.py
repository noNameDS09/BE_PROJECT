"""
Deterministic Financial Calculator.

Performs reproducible, non-LLM numerical financial calculations with full
audit trails, provenance tracking, and edge-case handling (zero denominators,
unit mismatches, negative values, and missing periods).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from src.retrieval.financial_query import (
    FinancialFactResult,
    FinancialQueryEngine,
    get_default_query_engine,
)

logger = logging.getLogger(__name__)


@dataclass
class CalculationResult:
    """
    Deterministic calculation result container with complete lineage.
    """
    metric: str
    value: Optional[float]
    formula: str
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    source_facts: List[Dict[str, Any]] = field(default_factory=list)
    unit: str = "%"
    status: str = "SUCCESS"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to the exact project specification dictionary."""
        return {
            "metric": self.metric,
            "value": self.value,
            "formula": self.formula,
            "inputs": self.inputs,
            "source_facts": self.source_facts,
            "unit": self.unit,
            "status": self.status,
            "notes": self.notes,
        }

    def __repr__(self) -> str:
        val_str = f"{self.value:.2f} {self.unit}" if self.value is not None else "None"
        return f"CalculationResult(metric='{self.metric}', value={val_str}, status='{self.status}')"


def _extract_val_and_fact(
    item: Union[int, float, FinancialFactResult, None],
    name: str,
    expected_unit: Optional[str] = None
) -> tuple[Optional[float], Optional[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Extracts numerical value, unit, input descriptor, and source fact dict.
    """
    if item is None:
        return None, None, {"name": name, "value": None, "unit": None}, None

    if isinstance(item, FinancialFactResult):
        val = float(item.value) if item.value is not None else None
        unit = item.unit
        input_desc = {"name": name, "value": val, "unit": unit, "fiscal_year": item.fiscal_year, "form": item.form}
        fact_dict = item.to_dict()
        return val, unit, input_desc, fact_dict

    val = float(item)
    unit = expected_unit or "USD"
    input_desc = {"name": name, "value": val, "unit": unit}
    return val, unit, input_desc, None


class FinancialCalculator:
    """
    Deterministic financial arithmetic engine.
    Calculates growth, margins, return ratios, and solvency ratios directly.
    """

    def __init__(self, query_engine: Optional[FinancialQueryEngine] = None):
        self.query_engine = query_engine or get_default_query_engine()

    # -------------------------------------------------------------------------
    # Core Mathematical Arithmetic
    # -------------------------------------------------------------------------

    def calculate_revenue_growth(
        self,
        current_revenue: Union[float, int, FinancialFactResult, None],
        previous_revenue: Union[float, int, FinancialFactResult, None]
    ) -> CalculationResult:
        """
        Calculates percentage revenue growth:
        ((Current Revenue - Previous Revenue) / Previous Revenue) * 100
        """
        formula = "((Current Revenue - Previous Revenue) / abs(Previous Revenue)) * 100"
        c_val, c_unit, c_in, c_fact = _extract_val_and_fact(current_revenue, "Current Revenue")
        p_val, p_unit, p_in, p_fact = _extract_val_and_fact(previous_revenue, "Previous Revenue")

        inputs = [c_in, p_in]
        sources = [f for f in (c_fact, p_fact) if f]

        if c_val is None or p_val is None:
            return CalculationResult(
                metric="Revenue Growth",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="MISSING_INPUTS",
                notes="One or both revenue values were missing."
            )

        if c_unit and p_unit and c_unit.upper() != p_unit.upper():
            return CalculationResult(
                metric="Revenue Growth",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {c_unit} vs {p_unit}."
            )

        if p_val == 0:
            return CalculationResult(
                metric="Revenue Growth",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="ZERO_DENOMINATOR",
                notes="Previous revenue was zero; growth rate undefined."
            )

        growth = ((c_val - p_val) / abs(p_val)) * 100.0
        return CalculationResult(
            metric="Revenue Growth",
            value=round(growth, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="%",
            status="SUCCESS",
            notes=f"Revenue changed from {p_val:,.0f} to {c_val:,.0f} ({growth:+.2f}%)."
        )

    def calculate_profit_margin(
        self,
        income_value: Union[float, int, FinancialFactResult, None],
        revenue_value: Union[float, int, FinancialFactResult, None],
        margin_type: str = "Net Profit Margin"
    ) -> CalculationResult:
        """
        Calculates profit margin percentage:
        (Income / Revenue) * 100
        """
        formula = f"({margin_type.replace(' Margin', '')} / Revenue) * 100"
        inc_val, inc_unit, inc_in, inc_fact = _extract_val_and_fact(income_value, "Income")
        rev_val, rev_unit, rev_in, rev_fact = _extract_val_and_fact(revenue_value, "Revenue")

        inputs = [inc_in, rev_in]
        sources = [f for f in (inc_fact, rev_fact) if f]

        if inc_val is None or rev_val is None:
            return CalculationResult(
                metric=margin_type,
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="MISSING_INPUTS",
                notes="Income or revenue value was missing."
            )

        if inc_unit and rev_unit and inc_unit.upper() != rev_unit.upper():
            return CalculationResult(
                metric=margin_type,
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {inc_unit} vs {rev_unit}."
            )

        if rev_val == 0:
            return CalculationResult(
                metric=margin_type,
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="ZERO_DENOMINATOR",
                notes="Revenue was zero; margin undefined."
            )

        margin = (inc_val / rev_val) * 100.0
        return CalculationResult(
            metric=margin_type,
            value=round(margin, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="%",
            status="SUCCESS",
            notes=f"{margin_type}: {margin:.2f}% on revenue of {rev_val:,.0f}."
        )

    def calculate_roa(
        self,
        net_income: Union[float, int, FinancialFactResult, None],
        total_assets: Union[float, int, FinancialFactResult, None]
    ) -> CalculationResult:
        """
        Calculates Return on Assets (ROA) percentage:
        (Net Income / Total Assets) * 100
        """
        formula = "(Net Income / Total Assets) * 100"
        ni_val, ni_unit, ni_in, ni_fact = _extract_val_and_fact(net_income, "Net Income")
        ta_val, ta_unit, ta_in, ta_fact = _extract_val_and_fact(total_assets, "Total Assets")

        inputs = [ni_in, ta_in]
        sources = [f for f in (ni_fact, ta_fact) if f]

        if ni_val is None or ta_val is None:
            return CalculationResult(
                metric="ROA",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="MISSING_INPUTS",
                notes="Net Income or Total Assets missing."
            )

        if ni_unit and ta_unit and ni_unit.upper() != ta_unit.upper():
            return CalculationResult(
                metric="ROA",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {ni_unit} vs {ta_unit}."
            )

        if ta_val == 0:
            return CalculationResult(
                metric="ROA",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="ZERO_DENOMINATOR",
                notes="Total Assets was zero; ROA undefined."
            )

        roa = (ni_val / ta_val) * 100.0
        return CalculationResult(
            metric="ROA",
            value=round(roa, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="%",
            status="SUCCESS",
            notes=f"Return on Assets: {roa:.2f}%."
        )

    def calculate_roe(
        self,
        net_income: Union[float, int, FinancialFactResult, None],
        stockholders_equity: Union[float, int, FinancialFactResult, None]
    ) -> CalculationResult:
        """
        Calculates Return on Equity (ROE) percentage:
        (Net Income / Stockholders Equity) * 100
        """
        formula = "(Net Income / Stockholders Equity) * 100"
        ni_val, ni_unit, ni_in, ni_fact = _extract_val_and_fact(net_income, "Net Income")
        eq_val, eq_unit, eq_in, eq_fact = _extract_val_and_fact(stockholders_equity, "Stockholders Equity")

        inputs = [ni_in, eq_in]
        sources = [f for f in (ni_fact, eq_fact) if f]

        if ni_val is None or eq_val is None:
            return CalculationResult(
                metric="ROE",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="MISSING_INPUTS",
                notes="Net Income or Stockholders Equity missing."
            )

        if ni_unit and eq_unit and ni_unit.upper() != eq_unit.upper():
            return CalculationResult(
                metric="ROE",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {ni_unit} vs {eq_unit}."
            )

        if eq_val == 0:
            return CalculationResult(
                metric="ROE",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="%",
                status="ZERO_DENOMINATOR",
                notes="Stockholders Equity was zero; ROE undefined."
            )

        roe = (ni_val / eq_val) * 100.0
        return CalculationResult(
            metric="ROE",
            value=round(roe, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="%",
            status="SUCCESS",
            notes=f"Return on Equity: {roe:.2f}%."
        )

    def calculate_current_ratio(
        self,
        current_assets: Union[float, int, FinancialFactResult, None],
        current_liabilities: Union[float, int, FinancialFactResult, None]
    ) -> CalculationResult:
        """
        Calculates Current Ratio:
        Current Assets / Current Liabilities
        """
        formula = "Current Assets / Current Liabilities"
        ca_val, ca_unit, ca_in, ca_fact = _extract_val_and_fact(current_assets, "Current Assets")
        cl_val, cl_unit, cl_in, cl_fact = _extract_val_and_fact(current_liabilities, "Current Liabilities")

        inputs = [ca_in, cl_in]
        sources = [f for f in (ca_fact, cl_fact) if f]

        if ca_val is None or cl_val is None:
            return CalculationResult(
                metric="Current Ratio",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="MISSING_INPUTS",
                notes="Current Assets or Current Liabilities missing."
            )

        if ca_unit and cl_unit and ca_unit.upper() != cl_unit.upper():
            return CalculationResult(
                metric="Current Ratio",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {ca_unit} vs {cl_unit}."
            )

        if cl_val == 0:
            return CalculationResult(
                metric="Current Ratio",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="ZERO_DENOMINATOR",
                notes="Current Liabilities was zero; ratio undefined."
            )

        ratio = ca_val / cl_val
        return CalculationResult(
            metric="Current Ratio",
            value=round(ratio, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="ratio",
            status="SUCCESS",
            notes=f"Current Ratio: {ratio:.2f}x liquidity coverage."
        )

    def calculate_debt_to_equity(
        self,
        debt: Union[float, int, FinancialFactResult, None],
        equity: Union[float, int, FinancialFactResult, None]
    ) -> CalculationResult:
        """
        Calculates Debt-to-Equity Ratio:
        Total Debt / Stockholders Equity
        """
        formula = "Total Debt / Stockholders Equity"
        d_val, d_unit, d_in, d_fact = _extract_val_and_fact(debt, "Debt")
        e_val, e_unit, e_in, e_fact = _extract_val_and_fact(equity, "Stockholders Equity")

        inputs = [d_in, e_in]
        sources = [f for f in (d_fact, e_fact) if f]

        if d_val is None or e_val is None:
            return CalculationResult(
                metric="Debt-to-Equity",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="MISSING_INPUTS",
                notes="Debt or Stockholders Equity missing."
            )

        if d_unit and e_unit and d_unit.upper() != e_unit.upper():
            return CalculationResult(
                metric="Debt-to-Equity",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {d_unit} vs {e_unit}."
            )

        if e_val == 0:
            return CalculationResult(
                metric="Debt-to-Equity",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="ZERO_DENOMINATOR",
                notes="Stockholders Equity was zero; ratio undefined."
            )

        ratio = d_val / e_val
        return CalculationResult(
            metric="Debt-to-Equity",
            value=round(ratio, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="ratio",
            status="SUCCESS",
            notes=f"Debt-to-Equity: {ratio:.2f}x."
        )

    def calculate_debt_ratio(
        self,
        total_liabilities: Union[float, int, FinancialFactResult, None],
        total_assets: Union[float, int, FinancialFactResult, None]
    ) -> CalculationResult:
        """
        Calculates Debt Ratio (Liabilities to Assets):
        Total Liabilities / Total Assets
        """
        formula = "Total Liabilities / Total Assets"
        l_val, l_unit, l_in, l_fact = _extract_val_and_fact(total_liabilities, "Total Liabilities")
        a_val, a_unit, a_in, a_fact = _extract_val_and_fact(total_assets, "Total Assets")

        inputs = [l_in, a_in]
        sources = [f for f in (l_fact, a_fact) if f]

        if l_val is None or a_val is None:
            return CalculationResult(
                metric="Debt Ratio",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="MISSING_INPUTS",
                notes="Total Liabilities or Total Assets missing."
            )

        if l_unit and a_unit and l_unit.upper() != a_unit.upper():
            return CalculationResult(
                metric="Debt Ratio",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="UNIT_MISMATCH",
                notes=f"Unit mismatch: {l_unit} vs {a_unit}."
            )

        if a_val == 0:
            return CalculationResult(
                metric="Debt Ratio",
                value=None,
                formula=formula,
                inputs=inputs,
                source_facts=sources,
                unit="ratio",
                status="ZERO_DENOMINATOR",
                notes="Total Assets was zero; debt ratio undefined."
            )

        ratio = l_val / a_val
        return CalculationResult(
            metric="Debt Ratio",
            value=round(ratio, 4),
            formula=formula,
            inputs=inputs,
            source_facts=sources,
            unit="ratio",
            status="SUCCESS",
            notes=f"Debt Ratio: {ratio:.2f} ({ratio * 100:.1f}% assets financed by liabilities)."
        )

    # -------------------------------------------------------------------------
    # Automated Retrieval & Computation Helpers
    # -------------------------------------------------------------------------

    def compute_revenue_growth(self, company: str, fiscal_year: int) -> CalculationResult:
        """Retrieves SEC facts and computes year-over-year revenue growth."""
        curr = self.query_engine.query_financial_fact(company, "Revenue", fiscal_year)
        prev = self.query_engine.query_financial_fact(company, "Revenue", fiscal_year - 1)
        return self.calculate_revenue_growth(curr, prev)

    def compute_profit_margins(self, company: str, fiscal_year: int) -> Dict[str, CalculationResult]:
        """Retrieves SEC facts and computes Gross, Operating, and Net Profit Margins."""
        rev = self.query_engine.query_financial_fact(company, "Revenue", fiscal_year)
        gp = self.query_engine.query_financial_fact(company, "Gross Profit", fiscal_year)
        oi = self.query_engine.query_financial_fact(company, "Operating Income", fiscal_year)
        ni = self.query_engine.query_financial_fact(company, "Net Income", fiscal_year)

        return {
            "Gross Margin": self.calculate_profit_margin(gp, rev, margin_type="Gross Margin"),
            "Operating Margin": self.calculate_profit_margin(oi, rev, margin_type="Operating Margin"),
            "Net Profit Margin": self.calculate_profit_margin(ni, rev, margin_type="Net Profit Margin"),
        }

    def compute_all_ratios(self, company: str, fiscal_year: int) -> Dict[str, CalculationResult]:
        """Retrieves facts and computes comprehensive solvency, liquidity, and return ratios."""
        rev = self.query_engine.query_financial_fact(company, "Revenue", fiscal_year)
        prev_rev = self.query_engine.query_financial_fact(company, "Revenue", fiscal_year - 1)
        ni = self.query_engine.query_financial_fact(company, "Net Income", fiscal_year)
        assets = self.query_engine.query_financial_fact(company, "Total Assets", fiscal_year)
        equity = self.query_engine.query_financial_fact(company, "Stockholders Equity", fiscal_year)
        curr_assets = self.query_engine.query_financial_fact(company, "Current Assets", fiscal_year)
        curr_liab = self.query_engine.query_financial_fact(company, "Current Liabilities", fiscal_year)

        # Check total liabilities: if not reported, derive as Assets - Equity
        liab = self.query_engine.query_financial_fact(company, "Total Liabilities", fiscal_year)
        derived_liab_fact = None
        if liab is None and assets is not None and equity is not None:
            derived_val = float(assets.value) - float(equity.value)
            derived_liab_fact = FinancialFactResult(
                value=derived_val,
                unit=assets.unit,
                fiscal_year=fiscal_year,
                fiscal_period="FY",
                form=assets.form,
                filed_date=assets.filed_date,
                concept="Derived: Assets - StockholdersEquity",
                source_company=assets.source_company,
                source_cik=assets.source_cik,
                selection_notes="Derived accounting identity: Total Assets - Stockholders Equity."
            )
            liab = derived_liab_fact

        # Check debt: long-term debt or derived
        debt = self.query_engine.query_financial_fact(company, "Long Term Debt", fiscal_year) or liab

        return {
            "Revenue Growth": self.calculate_revenue_growth(rev, prev_rev),
            "Net Profit Margin": self.calculate_profit_margin(ni, rev, "Net Profit Margin"),
            "ROA": self.calculate_roa(ni, assets),
            "ROE": self.calculate_roe(ni, equity),
            "Current Ratio": self.calculate_current_ratio(curr_assets, curr_liab),
            "Debt-to-Equity": self.calculate_debt_to_equity(debt, equity),
            "Debt Ratio": self.calculate_debt_ratio(liab, assets),
        }


# Singleton instance and convenience functions
_DEFAULT_CALCULATOR: Optional[FinancialCalculator] = None


def get_default_calculator() -> FinancialCalculator:
    global _DEFAULT_CALCULATOR
    if _DEFAULT_CALCULATOR is None:
        _DEFAULT_CALCULATOR = FinancialCalculator()
    return _DEFAULT_CALCULATOR


def calculate_revenue_growth(current: Any, previous: Any) -> CalculationResult:
    return get_default_calculator().calculate_revenue_growth(current, previous)


def calculate_profit_margin(income: Any, revenue: Any, margin_type: str = "Net Profit Margin") -> CalculationResult:
    return get_default_calculator().calculate_profit_margin(income, revenue, margin_type=margin_type)


def calculate_roa(net_income: Any, total_assets: Any) -> CalculationResult:
    return get_default_calculator().calculate_roa(net_income, total_assets)


def calculate_roe(net_income: Any, stockholders_equity: Any) -> CalculationResult:
    return get_default_calculator().calculate_roe(net_income, stockholders_equity)


def calculate_current_ratio(current_assets: Any, current_liabilities: Any) -> CalculationResult:
    return get_default_calculator().calculate_current_ratio(current_assets, current_liabilities)


def calculate_debt_to_equity(debt: Any, equity: Any) -> CalculationResult:
    return get_default_calculator().calculate_debt_to_equity(debt, equity)


def calculate_debt_ratio(total_liabilities: Any, total_assets: Any) -> CalculationResult:
    return get_default_calculator().calculate_debt_ratio(total_liabilities, total_assets)
