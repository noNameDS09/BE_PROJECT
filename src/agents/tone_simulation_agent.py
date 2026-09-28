"""
FARE-Style Tone & Scenario Simulation Agent.

Evaluates qualitative managerial sentiment, tone shifts across corporate disclosures,
and performs deterministic financial sensitivity & stress simulations on grounded SEC facts.

RESEARCH DATA LIMITATION:
Company Facts ('companyfacts.zip') contains structured numerical XBRL data.
It does not contain spoken earnings call audio or full 10-K Item 1A narrative paragraphs.
When text is supplied, the agent computes Loughran-McDonald sentiment and tone shifts.
In the absence of text, the agent computes quantitative fundamental momentum proxies
or deterministic financial stress simulations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from src.data.company_registry import CompanyMetadata, CompanyRegistry, get_registry
from src.tools.scenario_simulator import (
    SIMULATION_LIMITATION_NOTICE,
    ScenarioSimulator,
    SimulationResult,
    get_default_simulator,
)
from src.tools.tone_analyzer import (
    TONE_LIMITATION_NOTICE,
    QuantitativeToneProxy,
    ToneAnalyzer,
    ToneScore,
    ToneShift,
    get_default_tone_analyzer,
)

logger = logging.getLogger(__name__)


@dataclass
class ToneSimulationResult:
    """
    Standardized response from the Tone & Scenario Simulation Agent.
    """
    query: str
    mode: str  # TONE_ANALYSIS, TONE_SHIFT, SCENARIO_SIMULATION, QUANTITATIVE_TONE_PROXY
    company: Optional[str] = None
    fiscal_year: Optional[int] = None
    summary: str = ""
    tone_score: Optional[ToneScore] = None
    tone_shift: Optional[ToneShift] = None
    tone_proxy: Optional[QuantitativeToneProxy] = None
    simulation_result: Optional[SimulationResult] = None
    data_limitation_notice: str = TONE_LIMITATION_NOTICE
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "query": self.query,
            "mode": self.mode,
            "company": self.company,
            "fiscal_year": self.fiscal_year,
            "summary": self.summary,
            "status": self.status,
            "data_limitation_notice": self.data_limitation_notice,
        }
        if self.tone_score:
            res["tone_score"] = self.tone_score.to_dict()
        if self.tone_shift:
            res["tone_shift"] = self.tone_shift.to_dict()
        if self.tone_proxy:
            res["tone_proxy"] = self.tone_proxy.to_dict()
        if self.simulation_result:
            res["simulation_result"] = self.simulation_result.to_dict()
        return res


class ToneSimulationAgent:
    """
    Unified FARE Agent for Sentiment, Tone Evolution, and Deterministic Financial Simulation.
    """

    def __init__(
        self,
        simulator: Optional[ScenarioSimulator] = None,
        tone_analyzer: Optional[ToneAnalyzer] = None,
        registry: Optional[CompanyRegistry] = None,
    ):
        self.simulator = simulator or get_default_simulator()
        self.tone_analyzer = tone_analyzer or get_default_tone_analyzer()
        self.registry = registry or get_registry()

    def _extract_company(self, query: str) -> Optional[CompanyMetadata]:
        q_clean = query.lower()
        if "apple" in q_clean:
            try:
                return self.registry.get_company("Apple")
            except Exception:
                pass
        if "abbott" in q_clean:
            try:
                return self.registry.get_company("0000001800")
            except Exception:
                pass
        if "amd" in q_clean or "advanced micro" in q_clean:
            try:
                return self.registry.get_company("0000002488")
            except Exception:
                pass
        if "tesla" in q_clean:
            try:
                return self.registry.get_company("Tesla")
            except Exception:
                pass
        if "microsoft" in q_clean:
            try:
                return self.registry.get_company("Microsoft")
            except Exception:
                pass

        all_companies = self.registry.list_companies()
        for meta in all_companies:
            name_lower = meta.entity_name.lower()
            pattern = rf"\b{re.escape(name_lower)}\b"
            if re.search(pattern, query.lower()):
                return meta

        return None

    def _extract_years(self, query: str) -> List[int]:
        matches = re.findall(r"\b(201\d|202\d)\b", query)
        return sorted([int(m) for m in set(matches)])

    def _extract_percentage(self, query: str) -> Optional[float]:
        match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", query)
        if match:
            return float(match.group(1))
        # Look for keywords like "drop 10" or "drop 10 percent"
        match_drop = re.search(r"(?:drop|decline|contraction|shock|fall|loss)\s+(?:of\s+)?(\d+(?:\.\d+)?)", query.lower())
        if match_drop:
            return -float(match_drop.group(1))
        match_rise = re.search(r"(?:growth|increase|expansion|rise)\s+(?:of\s+)?(\d+(?:\.\d+)?)", query.lower())
        if match_rise:
            return float(match_rise.group(1))
        return None

    def answer_query(
        self,
        query: str,
        text_a: Optional[str] = None,
        text_b: Optional[str] = None,
        label_a: str = "Period A",
        label_b: str = "Period B",
    ) -> ToneSimulationResult:
        """
        Executes tone scoring, tone shift analysis, or financial simulation based on inputs.
        """
        q_lower = query.lower()
        company_meta = self._extract_company(query)
        years = self._extract_years(query)
        target_year = years[-1] if years else 2023
        company_name = company_meta.entity_name if company_meta else "Company"

        is_simulation = any(kw in q_lower for kw in [
            "simulate", "simulation", "stress", "shock", "what if", "breakeven", "break-even", "sensitivity"
        ])
        is_tone_shift = any(kw in q_lower for kw in [
            "tone shift", "shift in tone", "tone change", "sentiment shift", "compare tone"
        ]) or (text_a is not None and text_b is not None)
        is_tone = any(kw in q_lower for kw in [
            "tone", "sentiment", "optimism", "pessimism", "mood", "uncertainty"
        ]) or text_a is not None

        # -------------------------------------------------------------
        # 1. SCENARIO / STRESS SIMULATION
        # -------------------------------------------------------------
        if is_simulation or (not is_tone and not is_tone_shift and any(kw in q_lower for kw in ["drop", "inflation", "rate hike"])):
            pct = self._extract_percentage(query)

            # A. Breakeven Query
            if "breakeven" in q_lower or "break-even" in q_lower:
                breakeven_info = self.simulator.calculate_operating_breakeven(company_name, target_year)
                summary_text = (
                    f"### Operating Breakeven Analysis: {company_name} (FY{target_year})\n\n"
                    f"- **Baseline Revenue**: ${breakeven_info.get('baseline_revenue', 0):,.0f}\n"
                    f"- **Baseline Operating Income**: ${breakeven_info.get('baseline_operating_income', 0):,.0f}\n"
                    f"- **Breakeven Revenue Decline**: `{breakeven_info.get('breakeven_revenue_decline_pct', 'N/A')}%`\n"
                    f"- **Conclusion**: {breakeven_info.get('notes', '')}\n\n"
                    f"> [!NOTE]\n> {SIMULATION_LIMITATION_NOTICE}"
                )
                return ToneSimulationResult(
                    query=query,
                    mode="SCENARIO_SIMULATION",
                    company=company_name,
                    fiscal_year=target_year,
                    summary=summary_text,
                    data_limitation_notice=SIMULATION_LIMITATION_NOTICE,
                )

            # B. Cost Inflation Shock
            if any(kw in q_lower for kw in ["inflation", "cogs", "cost", "input cost", "opex"]):
                inflation_pct = abs(pct) if pct is not None else 5.0
                sim_res = self.simulator.simulate_cost_inflation(
                    company=company_name,
                    fiscal_year=target_year,
                    cogs_inflation_pct=inflation_pct,
                    sga_inflation_pct=inflation_pct / 2.0,
                )
                return ToneSimulationResult(
                    query=query,
                    mode="SCENARIO_SIMULATION",
                    company=company_name,
                    fiscal_year=target_year,
                    summary=sim_res.to_markdown_table(),
                    simulation_result=sim_res,
                    data_limitation_notice=SIMULATION_LIMITATION_NOTICE,
                )

            # C. Interest Rate Shock
            if any(kw in q_lower for kw in ["interest", "rate hike", "debt burden", "bps"]):
                # Extract bps or default to 150 bps
                bps_match = re.search(r"(\d+)\s*bps", q_lower)
                bps = float(bps_match.group(1)) if bps_match else 150.0
                sim_res = self.simulator.simulate_interest_rate_shock(
                    company=company_name,
                    fiscal_year=target_year,
                    rate_shock_bps=bps,
                )
                return ToneSimulationResult(
                    query=query,
                    mode="SCENARIO_SIMULATION",
                    company=company_name,
                    fiscal_year=target_year,
                    summary=sim_res.to_markdown_table(),
                    simulation_result=sim_res,
                    data_limitation_notice=SIMULATION_LIMITATION_NOTICE,
                )

            # D. Revenue Shock (Default Simulation)
            shock = pct if pct is not None else -10.0
            # Ensure negative if word is drop/decline
            if any(w in q_lower for w in ["drop", "decline", "fall", "contraction", "loss"]) and shock > 0:
                shock = -shock

            sim_res = self.simulator.simulate_revenue_shock(
                company=company_name,
                fiscal_year=target_year,
                shock_pct=shock,
            )
            return ToneSimulationResult(
                query=query,
                mode="SCENARIO_SIMULATION",
                company=company_name,
                fiscal_year=target_year,
                summary=sim_res.to_markdown_table(),
                simulation_result=sim_res,
                data_limitation_notice=SIMULATION_LIMITATION_NOTICE,
            )

        # -------------------------------------------------------------
        # 2. TONE SHIFT ANALYSIS
        # -------------------------------------------------------------
        if is_tone_shift and text_a and text_b:
            shift_res = self.tone_analyzer.compare_tone_shift(
                text_a=text_a,
                text_b=text_b,
                label_a=label_a,
                label_b=label_b,
            )
            summary_lines = [
                f"### Loughran-McDonald Financial Tone Shift Analysis",
                f"**Comparison**: {label_a} $\\rightarrow$ {label_b}",
                "",
                f"| Metric | {label_a} | {label_b} | Shift (Delta) |",
                f"| :--- | :--- | :--- | :--- |",
                f"| **Polarity Score** | {shift_res.score_a.polarity_score:+.3f} | {shift_res.score_b.polarity_score:+.3f} | {shift_res.delta_polarity:+.3f} |",
                f"| **Dominant Tone** | {shift_res.score_a.dominant_sentiment} | {shift_res.score_b.dominant_sentiment} | {shift_res.shift_category} |",
                f"| **Positive Words** | {shift_res.score_a.positive_count} | {shift_res.score_b.positive_count} | {shift_res.score_b.positive_count - shift_res.score_a.positive_count:+d} |",
                f"| **Negative Words** | {shift_res.score_a.negative_count} | {shift_res.score_b.negative_count} | {shift_res.score_b.negative_count - shift_res.score_a.negative_count:+d} |",
                f"| **Uncertainty Ratio** | {shift_res.score_a.uncertainty_ratio:.2%} | {shift_res.score_b.uncertainty_ratio:.2%} | {shift_res.delta_uncertainty*100:+.2f} pts |",
                "",
                f"**Evaluation**: {shift_res.interpretation}",
            ]
            return ToneSimulationResult(
                query=query,
                mode="TONE_SHIFT",
                company=company_name,
                fiscal_year=target_year,
                summary="\n".join(summary_lines),
                tone_shift=shift_res,
                data_limitation_notice="Evaluated directly on user-supplied textual disclosure transcripts.",
            )

        # -------------------------------------------------------------
        # 3. DIRECT TEXT TONE ANALYSIS
        # -------------------------------------------------------------
        if text_a:
            score = self.tone_analyzer.analyze_tone(text_a)
            pos_sample = ", ".join(score.top_positive_words) if score.top_positive_words else "None"
            neg_sample = ", ".join(score.top_negative_words) if score.top_negative_words else "None"

            summary_lines = [
                f"### Loughran-McDonald Tone Analysis ({label_a})",
                f"- **Dominant Tone**: `{score.dominant_sentiment}`",
                f"- **Polarity Score**: `{score.polarity_score:+.3f}` (range [-1.0, +1.0])",
                f"- **Word Volume**: {score.total_words} total words ({score.positive_count} positive, {score.negative_count} negative)",
                f"- **Uncertainty Ratio**: {score.uncertainty_ratio:.2%}",
                f"- **Positive Identifiers**: {pos_sample}",
                f"- **Negative Identifiers**: {neg_sample}",
                "",
                f"> [!NOTE]\n> Text scored using domain-standard financial dictionary (Loughran-McDonald).",
            ]
            return ToneSimulationResult(
                query=query,
                mode="TONE_ANALYSIS",
                company=company_name,
                fiscal_year=target_year,
                summary="\n".join(summary_lines),
                tone_score=score,
                data_limitation_notice="Evaluated directly on user-supplied financial disclosure text.",
            )

        # -------------------------------------------------------------
        # 4. QUANTITATIVE TONE PROXY (SEC Facts Fallback)
        # -------------------------------------------------------------
        proxy = self.tone_analyzer.derive_quantitative_tone_proxy(company_name, target_year)
        summary_lines = [
            f"### Quantitative Tone Proxy: {proxy.company} (FY{proxy.fiscal_year} vs FY{proxy.prior_year})",
            "",
            f"- **Implied Tone**: `{proxy.implied_tone}`",
            f"- **Fundamental Momentum Score**: `{proxy.proxy_score:+.3f}` (range [-1.0, +1.0])",
            f"- **YoY Revenue Growth**: `{proxy.revenue_growth_pct:+.2f}%`" if proxy.revenue_growth_pct is not None else "- **YoY Revenue Growth**: `N/A`",
            f"- **Operating Margin Shift**: `{proxy.operating_margin_delta_pts:+.2f} pts`" if proxy.operating_margin_delta_pts is not None else "- **Operating Margin Shift**: `N/A`",
            f"- **YoY Net Income Trajectory**: `{proxy.net_income_growth_pct:+.2f}%`" if proxy.net_income_growth_pct is not None else "- **YoY Net Income Trajectory**: `N/A`",
            "",
            f"> [!NOTE]\n> {TONE_LIMITATION_NOTICE}",
        ]
        return ToneSimulationResult(
            query=query,
            mode="QUANTITATIVE_TONE_PROXY",
            company=proxy.company,
            fiscal_year=proxy.fiscal_year,
            summary="\n".join(summary_lines),
            tone_proxy=proxy,
            data_limitation_notice=TONE_LIMITATION_NOTICE,
        )


# Global singleton and helper
_DEFAULT_TONE_SIMULATION_AGENT: Optional[ToneSimulationAgent] = None


def get_default_tone_simulation_agent() -> ToneSimulationAgent:
    global _DEFAULT_TONE_SIMULATION_AGENT
    if _DEFAULT_TONE_SIMULATION_AGENT is None:
        _DEFAULT_TONE_SIMULATION_AGENT = ToneSimulationAgent()
    return _DEFAULT_TONE_SIMULATION_AGENT
