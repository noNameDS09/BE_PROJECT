"""
Tests for FARE-Style Statement Extraction Agent (Phase 7).
"""

import pytest

from src.agents.statement_extraction_agent import (
    StatementExtractionAgent,
    StatementExtractionResult,
    extract_financial_statement_fact,
    get_default_statement_agent,
)


@pytest.fixture
def agent():
    return get_default_statement_agent()


# ---------------------------------------------------------
# Test End-to-End Extraction Pipeline
# ---------------------------------------------------------

def test_extract_annual_revenue_abbott(agent):
    res = agent.answer_query("What was Abbott's revenue in FY2024?")
    assert isinstance(res, StatementExtractionResult)
    assert res.status == "SUCCESS"
    assert res.company == "ABBOTT LABORATORIES"
    assert res.metric == "Revenue"
    assert res.fiscal_year == 2024
    assert res.fiscal_period == "FY"
    assert res.value == 41950000000
    assert res.unit == "USD"
    assert "$41.95B" in res.answer
    assert "Form 10-K" in res.answer

    # Verify SEC evidence grounding
    assert res.evidence is not None
    assert res.evidence["form"] == "10-K"
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in res.evidence["concept"]
    assert res.evidence["accession_number"] is not None


def test_extract_net_income_amd(agent):
    res = agent.answer_query("What was AMD's net income in 2023?")
    assert res.status == "SUCCESS"
    assert res.company == "ADVANCED MICRO DEVICES INC"
    assert res.metric == "Net Income"
    assert res.fiscal_year == 2023
    assert res.value == 854000000
    assert res.unit == "USD"
    assert "$854.00M" in res.answer


def test_extract_cash_balance(agent):
    res = agent.answer_query("How much cash did Abbott have in 2024?")
    assert res.status == "SUCCESS"
    assert res.metric == "Cash"
    assert res.value == 7616000000
    assert "CashAndCashEquivalentsAtCarryingValue" in res.evidence["concept"]


def test_extract_quarterly_revenue(agent):
    res = agent.answer_query("What was Abbott revenue in Q1 2024?")
    assert res.status == "SUCCESS"
    assert res.fiscal_period == "Q1"
    assert res.value == 9964000000
    assert res.evidence["form"] == "10-Q"


# ---------------------------------------------------------
# Test Query Understanding / Slot Extraction
# ---------------------------------------------------------

def test_query_understanding_slots(agent):
    slots = agent.understand_query("What was the gross profit of Abbott Laboratories in fiscal year 2023?")
    assert slots["company"] is not None
    assert slots["company"].entity_name == "ABBOTT LABORATORIES"
    assert slots["metric"] == "Gross Profit"
    assert slots["fiscal_year"] == 2023
    assert slots["fiscal_period"] == "FY"


def test_query_understanding_quarterly_phrasing(agent):
    slots = agent.understand_query("What was AMD revenue in first quarter 2024?")
    assert slots["company"].cik == "0000002488"
    assert slots["fiscal_period"] == "Q1"
    assert slots["fiscal_year"] == 2024


# ---------------------------------------------------------
# Test Anti-Hallucination & Error Handling
# ---------------------------------------------------------

def test_missing_company_graceful_response(agent):
    res = agent.answer_query("What was the revenue of NonExistentCorpXYZ in 2024?")
    assert res.status == "ENTITY_NOT_FOUND"
    assert res.value is None
    assert "Could not identify the target company" in res.answer


def test_missing_metric_graceful_response(agent):
    res = agent.answer_query("Tell me about Abbott in 2024")
    assert res.status == "UNRESOLVED_METRIC"
    assert res.value is None
    assert "financial metric" in res.answer


def test_missing_fiscal_year_graceful_response(agent):
    res = agent.answer_query("What is Abbott's revenue?")
    assert res.status == "MISSING_FISCAL_YEAR"
    assert res.value is None
    assert "fiscal year" in res.answer


def test_unfiled_year_fact_not_found(agent):
    res = agent.answer_query("What was Abbott's revenue in 1950?")
    assert res.status == "FACT_NOT_FOUND"
    assert res.value is None
    assert "No audited SEC financial fact was found" in res.answer


def test_convenience_function():
    res = extract_financial_statement_fact("What was Abbott's revenue in FY2024?")
    assert res.status == "SUCCESS"
    assert res.value == 41950000000
