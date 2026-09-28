"""
FARE-Style Central Orchestrator Agent.

Classifies user query intent and routes to specialized financial agents:
- Statement Extraction Agent (Factual SEC line items)
- Investment Agent (Multi-period financial analysis & trends)
- Comparison Agent (Multi-company benchmarking)
- Risk Extraction Agent (Financial distress & risk analysis)

IMPORTANT:
The orchestrator strictly coordinates and routes; it NEVER performs financial calculations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union

from src.agents.comparison_agent import ComparisonAgent, get_default_comparison_agent
from src.agents.investment_agent import InvestmentAgent, get_default_investment_agent
from src.agents.risk_extraction_agent import RiskExtractionAgent
from src.agents.statement_extraction_agent import (
    StatementExtractionAgent,
    get_default_statement_agent,
)
from src.agents.tone_simulation_agent import (
    ToneSimulationAgent,
    get_default_tone_simulation_agent,
)

logger = logging.getLogger(__name__)


# Intent Constants
INTENT_STATEMENT_EXTRACTION = "STATEMENT_EXTRACTION"
INTENT_INVESTMENT_ANALYSIS = "INVESTMENT_ANALYSIS"
INTENT_COMPARISON = "COMPARISON"
INTENT_RISK_EXTRACTION = "RISK_EXTRACTION"
INTENT_TONE_ANALYSIS = "TONE_ANALYSIS"
INTENT_SCENARIO_SIMULATION = "SCENARIO_SIMULATION"
INTENT_GENERAL = "GENERAL"


@dataclass
class OrchestratorResponse:
    """
    Standardized response returned by the Orchestrator.
    Encapsulates the routing decision, rationale, and downstream agent result.
    """
    query: str
    intent: str
    routed_to: str
    routing_reason: str
    agent_result: Any
    answer: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts response to dictionary."""
        res_dict = {
            "query": self.query,
            "intent": self.intent,
            "routed_to": self.routed_to,
            "routing_reason": self.routing_reason,
            "answer": self.answer,
        }
        if hasattr(self.agent_result, "to_dict"):
            res_dict["agent_result"] = self.agent_result.to_dict()
        elif isinstance(self.agent_result, dict):
            res_dict["agent_result"] = self.agent_result
        else:
            res_dict["agent_result"] = str(self.agent_result)

        return res_dict

    def __repr__(self) -> str:
        return (
            f"OrchestratorResponse(intent='{self.intent}', routed_to='{self.routed_to}', "
            f"query='{self.query}')"
        )


class FinancialOrchestrator:
    """
    Central router following the FARE multi-agent architecture.
    Analyzes user intent and coordinates execution across specialized agents.
    """

    def __init__(
        self,
        statement_agent: Optional[StatementExtractionAgent] = None,
        investment_agent: Optional[InvestmentAgent] = None,
        comparison_agent: Optional[ComparisonAgent] = None,
        risk_agent: Optional[RiskExtractionAgent] = None,
        tone_simulation_agent: Optional[ToneSimulationAgent] = None,
    ):
        self.statement_agent = statement_agent or get_default_statement_agent()
        self.investment_agent = investment_agent or get_default_investment_agent()
        self.comparison_agent = comparison_agent or get_default_comparison_agent()
        self.risk_agent = risk_agent or RiskExtractionAgent()
        self.tone_simulation_agent = tone_simulation_agent or get_default_tone_simulation_agent()

    def classify_intent(self, query: str) -> tuple[str, str]:
        """
        Classifies user query into one of the specialized FARE intents.
        Returns (intent, reasoning).
        """
        q_clean = query.strip().lower()

        # 1. Scenario Simulation Intent
        simulation_keywords = [
            "simulate", "simulation", "stress test", "stress-test", "what if",
            "revenue shock", "breakeven", "break-even", "sensitivity analysis"
        ]
        if any(kw in q_clean for kw in simulation_keywords):
            return (
                INTENT_SCENARIO_SIMULATION,
                "Query requests deterministic financial sensitivity, stress testing, or scenario simulation."
            )

        # 2. Tone Analysis Intent
        tone_keywords = [
            "tone shift", "shift in tone", "tone", "sentiment", "optimism",
            "pessimism", "managerial tone", "mood"
        ]
        if any(re.search(rf"\b{re.escape(kw)}\b", q_clean) for kw in tone_keywords):
            return (
                INTENT_TONE_ANALYSIS,
                "Query requests qualitative managerial sentiment, tone evolution, or fundamental momentum proxy."
            )

        # 3. Comparison Intent (priority: comparing multiple companies)
        comparison_keywords = ["compare", "versus", "vs", "vs.", "better than", "against each other", "benchmarking"]
        if any(kw in q_clean for kw in comparison_keywords):
            return (
                INTENT_COMPARISON,
                "Query involves comparative evaluation across multiple entities or explicitly uses comparison keywords."
            )

        # 4. Risk Extraction Intent
        risk_keywords = ["risk", "risks", "distress", "threat", "threats", "leverage risk", "solvency risk", "default", "bankruptcy"]
        if any(re.search(rf"\b{re.escape(kw)}\b", q_clean) for kw in risk_keywords):
            return (
                INTENT_RISK_EXTRACTION,
                "Query requests financial risk factors, distress signals, or solvency exposure."
            )

        # 5. Investment / Performance Analysis Intent
        investment_keywords = [
            "analyze", "analysis", "performance", "trend", "trends", "financial health",
            "evaluate", "trajectory", "growth over time", "from 20", "between 20"
        ]
        if any(kw in q_clean for kw in investment_keywords):
            return (
                INTENT_INVESTMENT_ANALYSIS,
                "Query requests multi-period financial evaluation, trend reasoning, or corporate performance analysis."
            )

        # 6. Statement Extraction Intent (specific financial line item or fact questions)
        financial_metric_keywords = [
            "revenue", "revenues", "sales", "net income", "profit", "earnings", "cash",
            "assets", "liabilities", "equity", "gross profit", "operating income",
            "operating cash flow", "shares", "debt", "topline", "ebit"
        ]
        has_metric = any(re.search(rf"\b{re.escape(kw)}\b", q_clean) for kw in financial_metric_keywords)
        has_fact_inquiry = any(kw in q_clean for kw in ["what was", "what is", "how much", "tell me the", "give me the"])

        # Must have a financial metric or combine inquiry phrase with fiscal period/numbers
        if has_metric or (has_fact_inquiry and any(tok in q_clean for tok in ["2020", "2021", "2022", "2023", "2024", "fy", "q1", "q2", "q3", "q4"])):
            return (
                INTENT_STATEMENT_EXTRACTION,
                "Query asks for specific audited financial statement figures or SEC fact line items."
            )

        # Default Fallback
        return (
            INTENT_GENERAL,
            "Query intent could not be unambiguously mapped to a specialized financial agent."
        )

    def route_query(self, query: str) -> OrchestratorResponse:
        """
        Orchestration pipeline:
        1. Classify user intent
        2. Route to specialized agent
        3. Encapsulate evidence and response
        """
        intent, reason = self.classify_intent(query)
        logger.info(f"Orchestrator classified query as '{intent}' ({reason})")

        if intent == INTENT_COMPARISON:
            result = self.comparison_agent.answer_query(query)
            return OrchestratorResponse(
                query=query,
                intent=intent,
                routed_to="ComparisonAgent",
                routing_reason=reason,
                agent_result=result,
                answer=result.summary
            )

        elif intent == INTENT_RISK_EXTRACTION:
            result = self.risk_agent.answer_query(query)
            return OrchestratorResponse(
                query=query,
                intent=intent,
                routed_to="RiskExtractionAgent",
                routing_reason=reason,
                agent_result=result,
                answer=result.summary
            )

        elif intent == INTENT_INVESTMENT_ANALYSIS:
            result = self.investment_agent.answer_query(query)
            return OrchestratorResponse(
                query=query,
                intent=intent,
                routed_to="InvestmentAgent",
                routing_reason=reason,
                agent_result=result,
                answer=result.summary
            )

        elif intent == INTENT_STATEMENT_EXTRACTION:
            result = self.statement_agent.answer_query(query)
            return OrchestratorResponse(
                query=query,
                intent=intent,
                routed_to="StatementExtractionAgent",
                routing_reason=reason,
                agent_result=result,
                answer=result.answer
            )

        elif intent in (INTENT_TONE_ANALYSIS, INTENT_SCENARIO_SIMULATION):
            result = self.tone_simulation_agent.answer_query(query)
            return OrchestratorResponse(
                query=query,
                intent=intent,
                routed_to="ToneSimulationAgent",
                routing_reason=reason,
                agent_result=result,
                answer=result.summary
            )

        else:
            fallback_answer = (
                "I am the SEC Financial Intelligence Orchestrator. I can help you with:\n"
                "1. Factual Line Item Extraction (e.g. 'What was Abbott's revenue in 2024?')\n"
                "2. Multi-Period Performance Analysis (e.g. 'Analyze Abbott's performance from 2022 to 2024')\n"
                "3. Cross-Company Comparison (e.g. 'Compare Abbott and AMD in 2023')\n"
                "4. Financial Risk Assessment (e.g. 'What financial risks does Abbott face?')\n"
                "5. Managerial Tone & Sentiment Analysis (e.g. 'Analyze management tone for Apple in 2023')\n"
                "6. Financial Scenario & Stress Simulation (e.g. 'Simulate a 10% revenue drop for Abbott in 2024')"
            )
            return OrchestratorResponse(
                query=query,
                intent=INTENT_GENERAL,
                routed_to="FallbackHandler",
                routing_reason=reason,
                agent_result={"help": fallback_answer},
                answer=fallback_answer
            )


# Singleton instance and convenience function
_DEFAULT_ORCHESTRATOR: Optional[FinancialOrchestrator] = None


def get_default_orchestrator() -> FinancialOrchestrator:
    global _DEFAULT_ORCHESTRATOR
    if _DEFAULT_ORCHESTRATOR is None:
        _DEFAULT_ORCHESTRATOR = FinancialOrchestrator()
    return _DEFAULT_ORCHESTRATOR


def process_query(query: str) -> OrchestratorResponse:
    """Convenience function to run the full FARE Orchestrator pipeline."""
    return get_default_orchestrator().route_query(query)
