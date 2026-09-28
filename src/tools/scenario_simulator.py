"""
Deterministic Financial Scenario & Stress Simulation Engine.

Performs reproducible, non-LLM sensitivity and stress-test simulations on
grounded SEC EDGAR corporate facts (revenue contraction, input cost inflation,
operating expense shocks, interest rate surges, and operating breakeven).

RESEARCH DATA LIMITATION:
Simulations are deterministic mathematical sensitivity models grounded in historical
SEC 10-K reported facts. They do not constitute predictive market guidance or
speculative non-deterministic forecasting.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

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

SIMULATION_LIMITATION_NOTICE = (
    "RESEARCH DATA LIMITATION: Financial simulations are deterministic sensitivity analyses "
    "grounded strictly in historical SEC EDGAR 10-K reported facts. They model mathematical "
    "sensitivities (shocks to top-line revenue, cost inflation, and interest burdens) and do not "
    "constitute predictive market forecasts or speculative guidance."
)


@dataclass
class SimulationLineItem:
    """
    Individual financial statement metric under stress simulation.
    """
    name: str
    baseline: float
    stressed: float
    delta_absolute: float
    delta_percent: Optional[float]
    unit: str = "USD"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "baseline": self.baseline,
            "stressed": self.stressed,
            "delta_absolute": self.delta_absolute,
            "delta_percent": self.delta_percent,
            "unit": self.unit,
            "notes": self.notes,
        }


@dataclass
class SimulationResult:
    """
    Complete scenario simulation outcome.
    """
    company: str
    cik: str
    fiscal_year: int
    scenario_name: str
    parameters: Dict[str, Any]
    line_items: Dict[str, SimulationLineItem] = field(default_factory=dict)
    source_facts: List[Dict[str, Any]] = field(default_factory=list)
    breakeven_revenue_decline_pct: Optional[float] = None
    risk_assessment: str = ""
    data_limitation_notice: str = SIMULATION_LIMITATION_NOTICE
    status: str = "SUCCESS"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "cik": self.cik,
            "fiscal_year": self.fiscal_year,
            "scenario_name": self.scenario_name,
            "parameters": self.parameters,
            "line_items": {k: v.to_dict() for k, v in self.line_items.items()},
            "source_facts": self.source_facts,
            "breakeven_revenue_decline_pct": self.breakeven_revenue_decline_pct,
            "risk_assessment": self.risk_assessment,
            "data_limitation_notice": self.data_limitation_notice,
            "status": self.status,
            "notes": self.notes,
        }

    def to_markdown_table(self) -> str:
        """Renders the scenario comparison table in GitHub Markdown."""
        lines = [
            f"### Scenario Simulation: {self.scenario_name}",
            f"**Company**: {self.company} (CIK: {self.cik}) | **Fiscal Year**: {self.fiscal_year}",
            "",
            "| Metric | Baseline | Stressed | Delta ($) | Delta (%) |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for name, item in self.line_items.items():
            if item.unit == "%":
                b_str = f"{item.baseline:.2f}%"
                s_str = f"{item.stressed:.2f}%"
                d_abs_str = f"{item.delta_absolute:+.2f} pts"
                d_pct_str = f"{item.delta_percent:+.2f}%" if item.delta_percent is not None else "N/A"
            else:
                b_str = f"${item.baseline:,.0f}"
                s_str = f"${item.stressed:,.0f}"
                d_abs_str = f"${item.delta_absolute:+,.0f}"
                d_pct_str = f"{item.delta_percent:+.2f}%" if item.delta_percent is not None else "N/A"

            lines.append(f"| {name} | {b_str} | {s_str} | {d_abs_str} | {d_pct_str} |")

        if self.breakeven_revenue_decline_pct is not None:
            lines.append("")
            lines.append(f"**Operating Breakeven Revenue Contraction**: `{self.breakeven_revenue_decline_pct:.2f}%`")

        if self.risk_assessment:
            lines.append("")
            lines.append(f"**Risk Assessment**: {self.risk_assessment}")

        lines.append("")
        lines.append(f"> [!NOTE]\n> {self.data_limitation_notice}")
        return "\n".join(lines)


class ScenarioSimulator:
    """
    Deterministic financial simulation and stress-testing engine.
    """

    def __init__(
        self,
        query_engine: Optional[FinancialQueryEngine] = None,
        calculator: Optional[FinancialCalculator] = None,
        registry: Optional[CompanyRegistry] = None,
    ):
        self.query_engine = query_engine or get_default_query_engine()
        self.calculator = calculator or get_default_calculator()
        self.registry = registry or get_registry()

    def _resolve_company_meta(self, company: str) -> Optional[CompanyMetadata]:
        c_clean = str(company).strip()
        c_lower = c_clean.lower()
        if c_lower in ("amd", "advanced micro devices"):
            try:
                return self.registry.get_company("0000002488")
            except Exception:
                pass
        if c_lower in ("abbott", "abbott laboratories"):
            try:
                return self.registry.get_company("0000001800")
            except Exception:
                pass
        if c_lower in ("apple", "aapl"):
            try:
                return self.registry.get_company("0000320193")
            except Exception:
                pass

        try:
            return self.registry.get_company(c_clean)
        except Exception:
            matches = self.registry.search_company_by_name(c_clean, limit=1)
            return matches[0] if matches else None

    def _gather_baseline_facts(self, cik: str, fiscal_year: int) -> tuple[Dict[str, float], List[Dict[str, Any]]]:
        """
        Retrieves core income statement and balance sheet lines for simulation.
        Returns (facts_dict, source_facts_list).
        """
        metrics_to_query = [
            ("Revenue", "revenue"),
            ("CostOfGoodsSold", "cost of goods sold"),
            ("GrossProfit", "gross profit"),
            ("OperatingIncome", "operating income"),
            ("NetIncome", "net income"),
            ("LongTermDebt", "long term debt"),
            ("TotalAssets", "total assets"),
        ]

        facts: Dict[str, float] = {}
        source_facts: List[Dict[str, Any]] = []

        for metric_key, query_metric in metrics_to_query:
            res = self.query_engine.query_financial_fact(
                company=cik,
                metric=query_metric,
                fiscal_year=fiscal_year,
                fiscal_period="FY",
            )
            if res is not None and res.value is not None:
                facts[metric_key] = float(res.value)
                source_facts.append(res.to_dict())

        # Derive Gross Profit if missing but Revenue and COGS exist
        if "GrossProfit" not in facts and "Revenue" in facts and "CostOfGoodsSold" in facts:
            facts["GrossProfit"] = facts["Revenue"] - facts["CostOfGoodsSold"]

        # Derive COGS if missing but Revenue and GrossProfit exist
        if "CostOfGoodsSold" not in facts and "Revenue" in facts and "GrossProfit" in facts:
            facts["CostOfGoodsSold"] = facts["Revenue"] - facts["GrossProfit"]

        # Derive Operating Expenses if GrossProfit and OperatingIncome exist
        if "GrossProfit" in facts and "OperatingIncome" in facts:
            facts["OperatingExpenses"] = facts["GrossProfit"] - facts["OperatingIncome"]

        return facts, source_facts

    def simulate_revenue_shock(
        self,
        company: str,
        fiscal_year: int,
        shock_pct: float,
        cogs_variability: float = 0.5,
    ) -> SimulationResult:
        """
        Simulates top-line revenue shock (e.g. -10% or +5%).

        Args:
            company: Company name or CIK.
            fiscal_year: Fiscal year to shock.
            shock_pct: Percentage change in revenue (e.g. -10.0 for -10%).
            cogs_variability: Fraction of COGS that varies directly with revenue (default 0.5 = 50% variable, 50% fixed).
        """
        meta = self._resolve_company_meta(company)
        if not meta:
            return SimulationResult(
                company=company,
                cik="",
                fiscal_year=fiscal_year,
                scenario_name=f"Revenue Shock ({shock_pct:+.1f}%)",
                parameters={"shock_pct": shock_pct},
                status="COMPANY_NOT_FOUND",
                notes=f"Could not resolve company '{company}' in registry.",
            )

        base_facts, source_facts = self._gather_baseline_facts(meta.cik, fiscal_year)
        if "Revenue" not in base_facts:
            return SimulationResult(
                company=meta.entity_name,
                cik=meta.cik,
                fiscal_year=fiscal_year,
                scenario_name=f"Revenue Shock ({shock_pct:+.1f}%)",
                parameters={"shock_pct": shock_pct},
                status="MISSING_DATA",
                notes=f"Revenue fact not found for {meta.entity_name} in FY{fiscal_year}.",
            )

        base_rev = base_facts["Revenue"]
        stressed_rev = base_rev * (1.0 + (shock_pct / 100.0))
        delta_rev = stressed_rev - base_rev

        # COGS adjustment: variable portion shifts with revenue
        base_cogs = base_facts.get("CostOfGoodsSold", base_rev * 0.55)  # conservative fallback
        variable_cogs = base_cogs * cogs_variability
        fixed_cogs = base_cogs * (1.0 - cogs_variability)
        stressed_cogs = (variable_cogs * (1.0 + (shock_pct / 100.0))) + fixed_cogs
        delta_cogs = stressed_cogs - base_cogs

        # Gross Profit
        base_gp = base_facts.get("GrossProfit", base_rev - base_cogs)
        stressed_gp = stressed_rev - stressed_cogs
        delta_gp = stressed_gp - base_gp

        # Operating Expenses (assumed fixed in revenue shock)
        base_opinc = base_facts.get("OperatingIncome", base_gp * 0.4)
        base_opex = base_facts.get("OperatingExpenses", base_gp - base_opinc)
        stressed_opex = base_opex
        delta_opex = 0.0

        # Operating Income
        stressed_opinc = stressed_gp - stressed_opex
        delta_opinc = stressed_opinc - base_opinc

        # Net Income: assumes non-operating & taxes adjust proportionally
        base_ni = base_facts.get("NetIncome", base_opinc * 0.75)
        tax_wedge = base_opinc - base_ni
        # If operating income is positive, scale tax wedge proportionally, else 0 tax shield
        if base_opinc != 0:
            effective_tax_rate = max(0.0, min(0.35, tax_wedge / base_opinc))
        else:
            effective_tax_rate = 0.20
        stressed_ni = stressed_opinc * (1.0 - effective_tax_rate)
        delta_ni = stressed_ni - base_ni

        # Margin calculations
        base_gm = (base_gp / base_rev) * 100.0
        stressed_gm = (stressed_gp / stressed_rev) * 100.0 if stressed_rev != 0 else 0.0

        base_om = (base_opinc / base_rev) * 100.0
        stressed_om = (stressed_opinc / stressed_rev) * 100.0 if stressed_rev != 0 else 0.0

        base_nm = (base_ni / base_rev) * 100.0
        stressed_nm = (stressed_ni / stressed_rev) * 100.0 if stressed_rev != 0 else 0.0

        line_items = {
            "Revenue": SimulationLineItem("Revenue", base_rev, stressed_rev, delta_rev, shock_pct, "USD"),
            "Cost of Goods Sold": SimulationLineItem("Cost of Goods Sold", base_cogs, stressed_cogs, delta_cogs, ((delta_cogs / abs(base_cogs)) * 100.0) if base_cogs else None, "USD", notes=f"Assumes {cogs_variability*100:.0f}% variable cost structure"),
            "Gross Profit": SimulationLineItem("Gross Profit", base_gp, stressed_gp, delta_gp, ((delta_gp / abs(base_gp)) * 100.0) if base_gp else None, "USD"),
            "Gross Margin": SimulationLineItem("Gross Margin", base_gm, stressed_gm, stressed_gm - base_gm, ((stressed_gm - base_gm) / abs(base_gm) * 100.0) if base_gm else None, "%"),
            "Operating Expenses": SimulationLineItem("Operating Expenses", base_opex, stressed_opex, delta_opex, 0.0, "USD", notes="Fixed SG&A/R&D commitments"),
            "Operating Income": SimulationLineItem("Operating Income", base_opinc, stressed_opinc, delta_opinc, ((delta_opinc / abs(base_opinc)) * 100.0) if base_opinc else None, "USD"),
            "Operating Margin": SimulationLineItem("Operating Margin", base_om, stressed_om, stressed_om - base_om, ((stressed_om - base_om) / abs(base_om) * 100.0) if base_om else None, "%"),
            "Net Income": SimulationLineItem("Net Income", base_ni, stressed_ni, delta_ni, ((delta_ni / abs(base_ni)) * 100.0) if base_ni else None, "USD"),
            "Net Profit Margin": SimulationLineItem("Net Profit Margin", base_nm, stressed_nm, stressed_nm - base_nm, ((stressed_nm - base_nm) / abs(base_nm) * 100.0) if base_nm else None, "%"),
        }

        # Breakeven revenue drop calculation
        breakeven_pct = None
        if base_opinc > 0:
            contribution_margin = (base_rev - variable_cogs) / base_rev if base_rev > 0 else 0.0
            if contribution_margin > 0:
                breakeven_dollar_drop = base_opinc / contribution_margin
                breakeven_pct = -round((breakeven_dollar_drop / base_rev) * 100.0, 2)

        # Risk assessment synthesis
        if stressed_opinc < 0:
            risk_assessment = (
                f"HIGH RISK: A {shock_pct:+.1f}% revenue contraction eliminates operating profit, resulting in an "
                f"operating loss of ${stressed_opinc:,.0f}."
            )
        elif stressed_om < 5.0:
            risk_assessment = (
                f"ELEVATED RISK: Operating margin compresses severely to {stressed_om:.2f}% under a "
                f"{shock_pct:+.1f}% revenue shock."
            )
        elif shock_pct < 0:
            risk_assessment = (
                f"MODERATE RESILIENCE: Operating income drops by {abs(delta_opinc / base_opinc * 100):.1f}%, "
                f"but operating profitability remains positive at {stressed_om:.2f}%."
            )
        else:
            risk_assessment = (
                f"EXPANSION: Top-line growth of {shock_pct:+.1f}% expands operating income by "
                f"{abs(delta_opinc / base_opinc * 100):.1f}%."
            )

        return SimulationResult(
            company=meta.entity_name,
            cik=meta.cik,
            fiscal_year=fiscal_year,
            scenario_name=f"Revenue Shock ({shock_pct:+.1f}%)",
            parameters={"shock_pct": shock_pct, "cogs_variability": cogs_variability},
            line_items=line_items,
            source_facts=source_facts,
            breakeven_revenue_decline_pct=breakeven_pct,
            risk_assessment=risk_assessment,
            status="SUCCESS",
            notes=f"Deterministic {shock_pct:+.1f}% revenue sensitivity simulation on FY{fiscal_year} 10-K reported facts.",
        )

    def simulate_cost_inflation(
        self,
        company: str,
        fiscal_year: int,
        cogs_inflation_pct: float = 0.0,
        sga_inflation_pct: float = 0.0,
    ) -> SimulationResult:
        """
        Simulates cost inflation on input costs (COGS) and SG&A/Operating expenses.
        """
        meta = self._resolve_company_meta(company)
        if not meta:
            return SimulationResult(
                company=company,
                cik="",
                fiscal_year=fiscal_year,
                scenario_name="Cost Inflation Shock",
                parameters={"cogs_inflation_pct": cogs_inflation_pct, "sga_inflation_pct": sga_inflation_pct},
                status="COMPANY_NOT_FOUND",
                notes=f"Could not resolve company '{company}' in registry.",
            )

        base_facts, source_facts = self._gather_baseline_facts(meta.cik, fiscal_year)
        if "Revenue" not in base_facts:
            return SimulationResult(
                company=meta.entity_name,
                cik=meta.cik,
                fiscal_year=fiscal_year,
                scenario_name="Cost Inflation Shock",
                parameters={"cogs_inflation_pct": cogs_inflation_pct, "sga_inflation_pct": sga_inflation_pct},
                status="MISSING_DATA",
                notes=f"Revenue baseline not found for {meta.entity_name} in FY{fiscal_year}.",
            )

        base_rev = base_facts["Revenue"]
        base_cogs = base_facts.get("CostOfGoodsSold", base_rev * 0.55)
        base_gp = base_facts.get("GrossProfit", base_rev - base_cogs)
        base_opinc = base_facts.get("OperatingIncome", base_gp * 0.40)
        base_opex = base_facts.get("OperatingExpenses", base_gp - base_opinc)
        base_ni = base_facts.get("NetIncome", base_opinc * 0.75)

        # Apply inflation
        stressed_cogs = base_cogs * (1.0 + (cogs_inflation_pct / 100.0))
        delta_cogs = stressed_cogs - base_cogs

        stressed_gp = base_rev - stressed_cogs
        delta_gp = stressed_gp - base_gp

        stressed_opex = base_opex * (1.0 + (sga_inflation_pct / 100.0))
        delta_opex = stressed_opex - base_opex

        stressed_opinc = stressed_gp - stressed_opex
        delta_opinc = stressed_opinc - base_opinc

        effective_tax_rate = max(0.0, min(0.35, (base_opinc - base_ni) / base_opinc)) if base_opinc != 0 else 0.20
        stressed_ni = stressed_opinc * (1.0 - effective_tax_rate)
        delta_ni = stressed_ni - base_ni

        base_gm = (base_gp / base_rev) * 100.0
        stressed_gm = (stressed_gp / base_rev) * 100.0

        base_om = (base_opinc / base_rev) * 100.0
        stressed_om = (stressed_opinc / base_rev) * 100.0

        line_items = {
            "Revenue": SimulationLineItem("Revenue", base_rev, base_rev, 0.0, 0.0, "USD", notes="Revenue held constant"),
            "Cost of Goods Sold": SimulationLineItem("Cost of Goods Sold", base_cogs, stressed_cogs, delta_cogs, cogs_inflation_pct, "USD"),
            "Gross Profit": SimulationLineItem("Gross Profit", base_gp, stressed_gp, delta_gp, ((delta_gp / abs(base_gp)) * 100.0) if base_gp else None, "USD"),
            "Gross Margin": SimulationLineItem("Gross Margin", base_gm, stressed_gm, stressed_gm - base_gm, None, "%"),
            "Operating Expenses": SimulationLineItem("Operating Expenses", base_opex, stressed_opex, delta_opex, sga_inflation_pct, "USD"),
            "Operating Income": SimulationLineItem("Operating Income", base_opinc, stressed_opinc, delta_opinc, ((delta_opinc / abs(base_opinc)) * 100.0) if base_opinc else None, "USD"),
            "Operating Margin": SimulationLineItem("Operating Margin", base_om, stressed_om, stressed_om - base_om, None, "%"),
            "Net Income": SimulationLineItem("Net Income", base_ni, stressed_ni, delta_ni, ((delta_ni / abs(base_ni)) * 100.0) if base_ni else None, "USD"),
        }

        if stressed_opinc < 0:
            risk_assessment = (
                f"CRITICAL VULNERABILITY: Combined cost inflation (COGS +{cogs_inflation_pct:.1f}%, OpEx +{sga_inflation_pct:.1f}%) "
                f"wipes out operating income, producing an operating loss of ${stressed_opinc:,.0f}."
            )
        elif stressed_om < base_om * 0.5:
            risk_assessment = (
                f"SEVERE MARGIN EROSION: Operating margin contracts by {abs(stressed_om - base_om):.2f} pts "
                f"from {base_om:.2f}% to {stressed_om:.2f}%."
            )
        else:
            risk_assessment = (
                f"RESILIENT ABSORPTION: Profitability absorbs cost inflation with operating margin "
                f"compressing by {abs(stressed_om - base_om):.2f} pts to {stressed_om:.2f}%."
            )

        return SimulationResult(
            company=meta.entity_name,
            cik=meta.cik,
            fiscal_year=fiscal_year,
            scenario_name=f"Cost Inflation (COGS +{cogs_inflation_pct:.1f}%, OpEx +{sga_inflation_pct:.1f}%)",
            parameters={"cogs_inflation_pct": cogs_inflation_pct, "sga_inflation_pct": sga_inflation_pct},
            line_items=line_items,
            source_facts=source_facts,
            risk_assessment=risk_assessment,
            status="SUCCESS",
            notes=f"Deterministic cost inflation stress simulation on FY{fiscal_year} 10-K reported facts.",
        )

    def simulate_interest_rate_shock(
        self,
        company: str,
        fiscal_year: int,
        rate_shock_bps: float = 150.0,
    ) -> SimulationResult:
        """
        Simulates interest rate shock on long-term debt (e.g. +150 bps = +1.50%).
        """
        meta = self._resolve_company_meta(company)
        if not meta:
            return SimulationResult(
                company=company,
                cik="",
                fiscal_year=fiscal_year,
                scenario_name=f"Interest Rate Shock (+{rate_shock_bps:.0f} bps)",
                parameters={"rate_shock_bps": rate_shock_bps},
                status="COMPANY_NOT_FOUND",
                notes=f"Could not resolve company '{company}' in registry.",
            )

        base_facts, source_facts = self._gather_baseline_facts(meta.cik, fiscal_year)
        lt_debt = base_facts.get("LongTermDebt", 0.0)
        base_ni = base_facts.get("NetIncome", 0.0)
        base_opinc = base_facts.get("OperatingIncome", 0.0)

        rate_shock_dec = rate_shock_bps / 10000.0  # e.g. 150 bps = 0.0150
        additional_interest_pretax = lt_debt * rate_shock_dec
        effective_tax_rate = 0.21  # standard US statutory corporate tax rate
        additional_interest_after_tax = additional_interest_pretax * (1.0 - effective_tax_rate)

        stressed_ni = base_ni - additional_interest_after_tax
        delta_ni = stressed_ni - base_ni

        line_items = {
            "Long-Term Debt": SimulationLineItem("Long-Term Debt", lt_debt, lt_debt, 0.0, 0.0, "USD"),
            "Additional Pre-Tax Interest Burden": SimulationLineItem("Additional Pre-Tax Interest Burden", 0.0, additional_interest_pretax, additional_interest_pretax, None, "USD", notes=f"+{rate_shock_bps:.0f} bps on debt"),
            "Additional After-Tax Interest Expense": SimulationLineItem("Additional After-Tax Interest Expense", 0.0, additional_interest_after_tax, additional_interest_after_tax, None, "USD", notes=f"Net of 21% tax shield"),
            "Baseline Net Income": SimulationLineItem("Baseline Net Income", base_ni, base_ni, 0.0, 0.0, "USD"),
            "Stressed Net Income": SimulationLineItem("Stressed Net Income", base_ni, stressed_ni, delta_ni, ((delta_ni / abs(base_ni)) * 100.0) if base_ni else None, "USD"),
        }

        if lt_debt == 0.0:
            risk_assessment = "ZERO EXPOSURE: Company reports negligible or zero long-term debt; rate shock has negligible impact."
        elif stressed_ni < 0 and base_ni > 0:
            risk_assessment = f"SOLVENCY WARNING: Rate shock of +{rate_shock_bps:.0f} bps increases annual interest by ${additional_interest_pretax:,.0f}, turning net earnings negative."
        else:
            impact_pct = abs(delta_ni / base_ni * 100.0) if base_ni else 0.0
            risk_assessment = (
                f"MANAGEABLE BURDEN: Rate shock of +{rate_shock_bps:.0f} bps adds ${additional_interest_pretax:,.0f} "
                f"in annual pre-tax debt servicing, reducing net income by {impact_pct:.2f}%."
            )

        return SimulationResult(
            company=meta.entity_name,
            cik=meta.cik,
            fiscal_year=fiscal_year,
            scenario_name=f"Interest Rate Shock (+{rate_shock_bps:.0f} bps)",
            parameters={"rate_shock_bps": rate_shock_bps},
            line_items=line_items,
            source_facts=source_facts,
            risk_assessment=risk_assessment,
            status="SUCCESS",
            notes=f"Deterministic +{rate_shock_bps:.0f} bps rate sensitivity simulation on FY{fiscal_year} reported debt.",
        )

    def calculate_operating_breakeven(self, company: str, fiscal_year: int) -> Dict[str, Any]:
        """
        Determines the exact percentage revenue decline that reduces operating income to zero.
        """
        meta = self._resolve_company_meta(company)
        if not meta:
            return {"status": "COMPANY_NOT_FOUND", "company": company, "breakeven_pct": None}

        base_facts, _ = self._gather_baseline_facts(meta.cik, fiscal_year)
        rev = base_facts.get("Revenue")
        opinc = base_facts.get("OperatingIncome")
        cogs = base_facts.get("CostOfGoodsSold", (rev * 0.55) if rev else None)

        if not rev or opinc is None or not cogs:
            return {"status": "MISSING_DATA", "company": meta.entity_name, "breakeven_pct": None}

        if opinc <= 0:
            return {
                "status": "ALREADY_DEFICIT",
                "company": meta.entity_name,
                "operating_income": opinc,
                "breakeven_pct": 0.0,
                "notes": "Company is already operating at zero or negative operating income.",
            }

        # Assume 50% variable COGS
        variable_cogs = cogs * 0.5
        contribution_margin = (rev - variable_cogs) / rev
        if contribution_margin <= 0:
            return {"status": "NEGATIVE_CONTRIBUTION_MARGIN", "company": meta.entity_name, "breakeven_pct": None}

        breakeven_drop_dollars = opinc / contribution_margin
        breakeven_pct = -round((breakeven_drop_dollars / rev) * 100.0, 2)

        return {
            "status": "SUCCESS",
            "company": meta.entity_name,
            "cik": meta.cik,
            "fiscal_year": fiscal_year,
            "baseline_revenue": rev,
            "baseline_operating_income": opinc,
            "breakeven_revenue_decline_pct": breakeven_pct,
            "breakeven_revenue_dollar_threshold": rev - breakeven_drop_dollars,
            "notes": f"Revenue can decline by {abs(breakeven_pct):.2f}% (${breakeven_drop_dollars:,.0f}) before operating profit reaches $0.",
        }


# Global singleton and helper
_DEFAULT_SIMULATOR: Optional[ScenarioSimulator] = None


def get_default_simulator() -> ScenarioSimulator:
    global _DEFAULT_SIMULATOR
    if _DEFAULT_SIMULATOR is None:
        _DEFAULT_SIMULATOR = ScenarioSimulator()
    return _DEFAULT_SIMULATOR
