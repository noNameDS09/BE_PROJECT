"""
Tests for FARE-Style Investment / Financial Analysis Agent (Phase 8).
"""

import pytest

from src.agents.investment_agent import (
    InvestmentAgent,
    InvestmentAnalysisResult,
    analyze_financial_performance,
    get_default_investment_agent,
)


@pytest.fixture
def agent():
    return get_default_investment_agent()


# ---------------------------------------------------------
# Test End-to-End Investment Analysis
# ---------------------------------------------------------

def test_analyze_abbott_performance_multi_period(agent):
    res = agent.answer_query("Analyze Abbott's financial performance from 2022 to 2024.")
    assert isinstance(res, InvestmentAnalysisResult)
    assert res.status == "SUCCESS"
    assert res.company == "ABBOTT LABORATORIES"
    assert res.start_year == 2022
    assert res.end_year == 2024

    # 1. Verify FACTS
    assert len(res.facts) > 0
    for fact in res.facts:
        assert fact["type"] == "FACT"
        assert "concept" in fact
        assert "form" in fact
        assert "value" in fact
        assert fact["value"] is not None

    # 2. Verify CALCULATIONS
    assert len(res.calculations) > 0
    calc_metrics = {c["metric"] for c in res.calculations}
    assert "Revenue Growth" in calc_metrics
    assert "Net Profit Margin" in calc_metrics
    assert "ROA" in calc_metrics
    assert "ROE" in calc_metrics
    assert "Current Ratio" in calc_metrics

    for calc in res.calculations:
        assert calc["type"] == "CALCULATION"
        assert "formula" in calc
        assert "inputs" in calc
        assert calc["value"] is not None

    # 3. Verify INTERPRETATIONS
    assert len(res.interpretations) >= 3
    for interp in res.interpretations:
        assert interp.startswith("[INTERPRETATION]")

    # Check summary contains analysis
    assert "ABBOTT LABORATORIES" in res.summary
    assert "Revenue Trajectory" in res.summary


def test_fact_calculation_interpretation_separation(agent):
    res = agent.analyze_company_performance("ABBOTT LABORATORIES", 2022, 2024)
    # Ensure items in facts are purely raw SEC data
    fact_concepts = [f["concept"] for f in res.facts]
    assert any("Revenue" in c for c in fact_concepts)

    # Ensure items in calculations contain math formulas
    for calc in res.calculations:
        assert "formula" in calc
        assert len(calc["inputs"]) > 0

    # Ensure interpretations are analytical statements
    assert any("Profitability" in interp for interp in res.interpretations)
    assert any("Solvency & Liquidity" in interp for interp in res.interpretations)


# ---------------------------------------------------------
# Test Query Parsing
# ---------------------------------------------------------

def test_query_parsing_year_range(agent):
    p = agent.parse_query("Evaluate AMD performance between 2021 and 2023")
    assert p["company"].cik == "0000002488"
    assert p["start_year"] == 2021
    assert p["end_year"] == 2023


def test_query_parsing_single_year(agent):
    p = agent.parse_query("Analyze Abbott in 2024")
    assert p["company"].cik == "0000001800"
    assert p["start_year"] == 2023
    assert p["end_year"] == 2024


# ---------------------------------------------------------
# Test Error Handling & Edge Cases
# ---------------------------------------------------------

def test_unknown_company_handling(agent):
    res = agent.answer_query("Analyze financial health of NonExistentCorp123 from 2022 to 2024")
    assert res.status == "COMPANY_NOT_FOUND"
    assert len(res.facts) == 0
    assert len(res.calculations) == 0


def test_insufficient_data_handling(agent):
    res = agent.analyze_company_performance("ABBOTT LABORATORIES", 1950, 1952)
    assert res.status == "INSUFFICIENT_DATA"
    assert "No audited revenue data found" in res.summary


def test_convenience_function():
    res = analyze_financial_performance("ABBOTT LABORATORIES", 2022, 2024)
    assert res.status == "SUCCESS"
    assert res.company == "ABBOTT LABORATORIES"
