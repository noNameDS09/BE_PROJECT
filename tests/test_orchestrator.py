"""
Tests for FARE-Style Financial Orchestrator (Phase 10).
"""

import pytest

from src.agents.comparison_agent import ComparisonResult
from src.agents.investment_agent import InvestmentAnalysisResult
from src.agents.orchestrator import (
    INTENT_COMPARISON,
    INTENT_GENERAL,
    INTENT_INVESTMENT_ANALYSIS,
    INTENT_RISK_EXTRACTION,
    INTENT_STATEMENT_EXTRACTION,
    FinancialOrchestrator,
    OrchestratorResponse,
    get_default_orchestrator,
    process_query,
)
from src.agents.risk_extraction_agent import RiskExtractionResult
from src.agents.statement_extraction_agent import StatementExtractionResult


@pytest.fixture
def orchestrator():
    return get_default_orchestrator()


# ---------------------------------------------------------
# Test Intent Classification
# ---------------------------------------------------------

def test_intent_classification_statement_extraction(orchestrator):
    intent, _ = orchestrator.classify_intent("What was Abbott's revenue in 2024?")
    assert intent == INTENT_STATEMENT_EXTRACTION

    intent2, _ = orchestrator.classify_intent("How much cash did AMD have in 2023?")
    assert intent2 == INTENT_STATEMENT_EXTRACTION


def test_intent_classification_investment_analysis(orchestrator):
    intent, _ = orchestrator.classify_intent("Analyze Abbott's financial performance from 2022 to 2024")
    assert intent == INTENT_INVESTMENT_ANALYSIS

    intent2, _ = orchestrator.classify_intent("Evaluate AMD financial trends over time")
    assert intent2 == INTENT_INVESTMENT_ANALYSIS


def test_intent_classification_comparison(orchestrator):
    intent, _ = orchestrator.classify_intent("Compare Abbott and AMD in 2023")
    assert intent == INTENT_COMPARISON

    intent2, _ = orchestrator.classify_intent("Abbott vs AMD performance comparison")
    assert intent2 == INTENT_COMPARISON


def test_intent_classification_risk_extraction(orchestrator):
    intent, _ = orchestrator.classify_intent("What financial risks does Abbott face?")
    assert intent == INTENT_RISK_EXTRACTION

    intent2, _ = orchestrator.classify_intent("Assess liquidity distress for AMD")
    assert intent2 == INTENT_RISK_EXTRACTION


def test_intent_classification_fallback(orchestrator):
    intent, _ = orchestrator.classify_intent("Hello, what is the weather today?")
    assert intent == INTENT_GENERAL


# ---------------------------------------------------------
# Test End-to-End Routing Execution
# ---------------------------------------------------------

def test_route_statement_extraction(orchestrator):
    res = orchestrator.route_query("What was Abbott's revenue in FY2024?")
    assert isinstance(res, OrchestratorResponse)
    assert res.intent == INTENT_STATEMENT_EXTRACTION
    assert res.routed_to == "StatementExtractionAgent"
    assert isinstance(res.agent_result, StatementExtractionResult)
    assert res.agent_result.value == 41950000000
    assert "$41.95B" in res.answer


def test_route_investment_analysis(orchestrator):
    res = orchestrator.route_query("Analyze Abbott's financial performance from 2022 to 2024")
    assert res.intent == INTENT_INVESTMENT_ANALYSIS
    assert res.routed_to == "InvestmentAgent"
    assert isinstance(res.agent_result, InvestmentAnalysisResult)
    assert len(res.agent_result.calculations) > 0


def test_route_comparison(orchestrator):
    res = orchestrator.route_query("Compare Abbott and AMD in 2023")
    assert res.intent == INTENT_COMPARISON
    assert res.routed_to == "ComparisonAgent"
    assert isinstance(res.agent_result, ComparisonResult)
    assert len(res.agent_result.metrics_table) > 0


def test_route_risk_extraction(orchestrator):
    res = orchestrator.route_query("What financial risks does Abbott face?")
    assert res.intent == INTENT_RISK_EXTRACTION
    assert res.routed_to == "RiskExtractionAgent"
    assert isinstance(res.agent_result, RiskExtractionResult)
    assert len(res.agent_result.quantitative_risk_signals) > 0
    assert "DATA LIMITATION" in res.agent_result.data_limitation_notice


def test_route_fallback_help(orchestrator):
    res = orchestrator.route_query("Tell me something general")
    assert res.intent == INTENT_GENERAL
    assert res.routed_to == "FallbackHandler"
    assert "I can help you with" in res.answer


def test_convenience_function():
    res = process_query("What was Abbott's revenue in FY2024?")
    assert isinstance(res, OrchestratorResponse)
    assert res.agent_result.value == 41950000000
