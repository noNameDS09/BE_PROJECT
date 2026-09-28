"""
FARE-Style Risk Extraction Agent.

Evaluates financial risks using grounded SEC facts and prepares the structured
schema for textual SEC 10-K/10-Q Item 1A narrative risk factor ingestion.

CRITICAL RESEARCH DATA LIMITATION:
SEC Company Facts ('companyfacts.zip') contains structured XBRL numerical financial data.
It does NOT contain the full qualitative narrative text of 'Item 1A. Risk Factors' from
Form 10-K / 10-Q filings. This module strictly separates quantitative distress risk signals
(which ARE derivable from Company Facts) from narrative corporate risk factors (which REQUIRE
raw SEC filing text). No unavailable narrative text is fabricated.
"""

from __future__ import annotations

import logging
import re
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

LIMITATION_NOTICE = (
    "RESEARCH DATA LIMITATION: SEC Company Facts contains structured numerical XBRL data. "
    "Full qualitative 'Item 1A. Risk Factors' narrative text is not present in the numeric dataset. "
    "Quantitative financial distress signals (liquidity, leverage, profitability contraction) "
    "are evaluated deterministically from SEC filings. When raw 10-K text is supplied, the agent "
    "ingests narrative risk factors into the structured schema."
)


@dataclass
class RiskItem:
    """
    Standardized, verifiable corporate risk item conforming to FARE requirements.
    Contains the 6 core research attributes:
    Risk, Category, Evidence, Source, Reasoning, Confidence.
    """
    risk: str
    category: str
    evidence: str
    source: str
    reasoning: str
    confidence: float
    severity: str = "MODERATE"
    is_quantitative: bool = True
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts to dictionary with standard FARE field names."""
        return {
            "Risk": self.risk,
            "Category": self.category,
            "Evidence": self.evidence,
            "Source": self.source,
            "Reasoning": self.reasoning,
            "Confidence": self.confidence,
            "Severity": self.severity,
            "IsQuantitative": self.is_quantitative,
            "Metrics": self.metrics,
        }

    def __repr__(self) -> str:
        return f"RiskItem(risk='{self.risk}', category='{self.category}', severity='{self.severity}')"


@dataclass
class RiskAnalysisResult:
    """
    Complete risk assessment outcome for an SEC registrant.
    """
    query: str
    company: str
    cik: str
    fiscal_year: int
    data_limitation_notice: str
    risks: List[RiskItem] = field(default_factory=list)
    summary: str = ""
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "company": self.company,
            "cik": self.cik,
            "fiscal_year": self.fiscal_year,
            "data_limitation_notice": self.data_limitation_notice,
            "risks": [r.to_dict() for r in self.risks],
            "summary": self.summary,
            "status": self.status,
        }

    @property
    def quantitative_risk_signals(self) -> List[RiskItem]:
        """Convenience property returning quantitative risk items."""
        return [r for r in self.risks if r.is_quantitative]

    def __repr__(self) -> str:
        return (
            f"RiskAnalysisResult(company='{self.company}', risks_identified={len(self.risks)}, "
            f"status='{self.status}')"
        )


# Backward-compatible alias
RiskExtractionResult = RiskAnalysisResult


class RiskExtractionAgent:
    """
    FARE-inspired Risk Extraction Agent.
    Evaluates quantitative distress signals from SEC facts and provides
    the narrative ingestion interface for future SEC 10-K text integration.
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

    # -------------------------------------------------------------------------
    # Quantitative Risk Assessment (from SEC Company Facts)
    # -------------------------------------------------------------------------

    def assess_financial_risks(
        self,
        company: Union[str, CompanyMetadata],
        fiscal_year: int = 2023,
        query: str = ""
    ) -> RiskAnalysisResult:
        """
        Assesses empirical financial distress signals using SEC Company Facts:
        - Liquidity Risk (Current Ratio)
        - Solvency & Capital Structure Risk (Debt Ratio & Debt-to-Equity)
        - Profitability & Contraction Risk (Net Margin & Revenue Growth)
        """
        if isinstance(company, CompanyMetadata):
            meta = company
        else:
            try:
                meta = self.registry.get_company(company)
            except Exception as e:
                return RiskAnalysisResult(
                    query=query,
                    company=str(company),
                    cik="Unknown",
                    fiscal_year=fiscal_year,
                    data_limitation_notice=LIMITATION_NOTICE,
                    risks=[],
                    summary=f"Could not identify company '{company}': {e}",
                    status="COMPANY_NOT_FOUND"
                )

        # Retrieve financial facts & ratios
        ratios = self.calculator.compute_all_ratios(meta.entity_name, fiscal_year)
        risk_items: List[RiskItem] = []

        # 1. Liquidity Risk Evaluation (Current Ratio)
        cr_calc = ratios.get("Current Ratio")
        if cr_calc and cr_calc.value is not None:
            cr_val = cr_calc.value
            if cr_val < 1.0:
                severity = "HIGH"
                desc = "Current obligations exceed liquid short-term assets (working capital deficit)."
            elif cr_val < 1.5:
                severity = "MODERATE"
                desc = "Working capital buffer is tight, though current assets exceed current liabilities."
            else:
                severity = "LOW"
                desc = "Sound liquidity buffer with liquid assets comfortably covering short-term debt."

            source_desc = (
                f"SEC Form {cr_calc.source_facts[0].get('form', '10-K') if cr_calc.source_facts else '10-K'} "
                f"for FY{fiscal_year}"
            )
            risk_items.append(RiskItem(
                risk="Short-Term Liquidity & Working Capital Risk",
                category="Liquidity",
                evidence=f"Current Ratio = {cr_val:.2f}x (Current Assets vs Current Liabilities)",
                source=source_desc,
                reasoning=desc,
                confidence=1.0,
                severity=severity,
                is_quantitative=True,
                metrics={"current_ratio": cr_val, "formula": cr_calc.formula}
            ))

        # 2. Solvency & Debt Burden Risk (Debt Ratio & Debt-to-Equity)
        dr_calc = ratios.get("Debt Ratio")
        de_calc = ratios.get("Debt-to-Equity")
        if dr_calc and dr_calc.value is not None:
            dr_val = dr_calc.value
            de_val = de_calc.value if de_calc else None

            if dr_val > 0.70 or (de_val is not None and de_val > 2.5):
                severity = "HIGH"
                desc = f"High leverage: {dr_val * 100:.1f}% of assets financed by liabilities, elevating interest rate and refinancing vulnerability."
            elif dr_val > 0.50 or (de_val is not None and de_val > 1.0):
                severity = "MODERATE"
                desc = f"Moderate leverage: {dr_val * 100:.1f}% of assets financed by liabilities."
            else:
                severity = "LOW"
                desc = f"Conservative capital structure with {dr_val * 100:.1f}% liabilities-to-assets."

            source_desc = f"SEC Form 10-K for FY{fiscal_year}"
            risk_items.append(RiskItem(
                risk="Financial Leverage & Solvency Risk",
                category="Solvency / Capital Structure",
                evidence=f"Debt Ratio = {dr_val:.2f} ({dr_val * 100:.1f}% of assets financed by liabilities)",
                source=source_desc,
                reasoning=desc,
                confidence=1.0,
                severity=severity,
                is_quantitative=True,
                metrics={"debt_ratio": dr_val, "debt_to_equity": de_val}
            ))

        # 3. Operational Contraction & Margin Pressure Risk
        nm_calc = ratios.get("Net Profit Margin")
        rg_calc = ratios.get("Revenue Growth")
        if nm_calc and nm_calc.value is not None:
            nm_val = nm_calc.value
            rg_val = rg_calc.value if rg_calc else None

            if nm_val < 0 or (rg_val is not None and rg_val < -10.0):
                severity = "HIGH"
                desc = "Net loss or double-digit top-line contraction detected in the period."
            elif (rg_val is not None and rg_val < 0) or nm_val < 5.0:
                severity = "MODERATE"
                desc = "Top-line revenue contraction or thin net margins under 5%."
            else:
                severity = "LOW"
                desc = "Positive revenue growth and healthy operating profitability."

            growth_str = f"YoY Revenue Growth = {rg_val:+.2f}%" if rg_val is not None else "Revenue growth N/A"
            risk_items.append(RiskItem(
                risk="Operational & Margin Pressure Risk",
                category="Operational / Profitability",
                evidence=f"Net Profit Margin = {nm_val:.2f}%, {growth_str}",
                source=f"SEC Form 10-K for FY{fiscal_year}",
                reasoning=desc,
                confidence=1.0,
                severity=severity,
                is_quantitative=True,
                metrics={"net_profit_margin": nm_val, "revenue_growth": rg_val}
            ))

        # Formulate Risk Summary
        high_risks = [r for r in risk_items if r.severity == "HIGH"]
        mod_risks = [r for r in risk_items if r.severity == "MODERATE"]
        low_risks = [r for r in risk_items if r.severity == "LOW"]

        summary_lines = [
            f"Financial Risk Assessment for {meta.entity_name} (FY{fiscal_year}):",
            f"[DATA BOUNDARY] {LIMITATION_NOTICE}",
            f"- High Risk Signals: {len(high_risks)}",
            f"- Moderate Risk Signals: {len(mod_risks)}",
            f"- Low Risk Signals: {len(low_risks)}",
        ]
        for r in risk_items:
            summary_lines.append(f"• [{r.severity}] {r.risk}: {r.reasoning} (Evidence: {r.evidence})")

        return RiskAnalysisResult(
            query=query,
            company=meta.entity_name,
            cik=meta.cik,
            fiscal_year=fiscal_year,
            data_limitation_notice=LIMITATION_NOTICE,
            risks=risk_items,
            summary="\n".join(summary_lines),
            status="SUCCESS"
        )

    # -------------------------------------------------------------------------
    # Narrative Risk Ingestion (Prepared for SEC 10-K Text Integration)
    # -------------------------------------------------------------------------

    def ingest_narrative_risk_factors(
        self,
        company: str,
        filing_text: str,
        source: str = "SEC Form 10-K Item 1A",
        confidence: float = 0.90
    ) -> List[RiskItem]:
        """
        Parses textual risk factor sections (e.g. from 10-K Item 1A text)
        and converts each narrative paragraph into a structured RiskItem.
        """
        if not filing_text or not filing_text.strip():
            return []

        risk_items: List[RiskItem] = []
        # Split text by common risk header bullet points or headings
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n|•", filing_text) if len(p.strip()) > 40]

        for p in paragraphs:
            # First sentence as risk title
            sentences = re.split(r"(?<=[.!?])\s+", p)
            title = sentences[0][:120].strip()
            body = p

            # Categorize by keyword
            p_low = p.lower()
            if any(w in p_low for w in ["liquidity", "credit", "cash", "capital resources"]):
                cat = "Liquidity"
            elif any(w in p_low for w in ["debt", "interest rate", "indebtedness", "covenant"]):
                cat = "Solvency / Capital Structure"
            elif any(w in p_low for w in ["regulation", "compliance", "legal", "fda", "sec", "law"]):
                cat = "Regulatory & Legal"
            elif any(w in p_low for w in ["competition", "market", "customer", "demand"]):
                cat = "Market & Competitive"
            elif any(w in p_low for w in ["supply chain", "manufacturing", "cyber", "technology"]):
                cat = "Operational & Technology"
            else:
                cat = "General Business Risk"

            risk_items.append(RiskItem(
                risk=title,
                category=cat,
                evidence=body[:300] + ("..." if len(body) > 300 else ""),
                source=source,
                reasoning=f"Narrative disclosure extracted from {source}.",
                confidence=confidence,
                severity="MODERATE",
                is_quantitative=False,
                metrics={}
            ))

        return risk_items

    # -------------------------------------------------------------------------
    # Query Routing Interface
    # -------------------------------------------------------------------------

    def answer_query(self, query: str) -> RiskAnalysisResult:
        """Parses natural-language user query and runs risk assessment."""
        cleaned_query = query.strip()

        # 1. Extract year
        yr_m = re.search(r"\b(20\d\d|19\d\d)\b", cleaned_query)
        year = int(yr_m.group(1)) if yr_m else 2023

        # 2. Extract company
        meta: Optional[CompanyMetadata] = None
        for comp in self.registry.list_companies(include_empty=False):
            name_clean = comp.entity_name.lower().replace(",", "").replace(".", "").replace(" inc", "").replace(" corp", "")
            tokens = [t for t in name_clean.split() if len(t) > 3]
            if name_clean in cleaned_query.lower():
                meta = comp
                break
            for tok in tokens:
                if re.search(rf"\b{re.escape(tok)}\b", cleaned_query, re.IGNORECASE):
                    meta = comp
                    break
            if meta:
                break

        if not meta:
            return RiskAnalysisResult(
                query=query,
                company="Unknown",
                cik="Unknown",
                fiscal_year=year,
                data_limitation_notice=LIMITATION_NOTICE,
                risks=[],
                summary="Could not identify the target company from your risk inquiry. Please specify an SEC registrant name or CIK.",
                status="COMPANY_NOT_FOUND"
            )

        return self.assess_financial_risks(meta, fiscal_year=year, query=query)


# Singleton instance and convenience function
_DEFAULT_RISK_AGENT: Optional[RiskExtractionAgent] = None


def get_default_risk_agent() -> RiskExtractionAgent:
    global _DEFAULT_RISK_AGENT
    if _DEFAULT_RISK_AGENT is None:
        _DEFAULT_RISK_AGENT = RiskExtractionAgent()
    return _DEFAULT_RISK_AGENT


def assess_company_risks(company: str, fiscal_year: int = 2023) -> RiskAnalysisResult:
    """Convenience function to run the Risk Extraction Agent."""
    return get_default_risk_agent().assess_financial_risks(company, fiscal_year=fiscal_year)
