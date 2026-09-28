"""
Tests for FARE-Style Comparison Agent (Phase 9).
"""

import pytest

from src.agents.comparison_agent import (
    ComparisonAgent,
    ComparisonResult,
    compare_companies,
    get_default_comparison_agent,
)


@pytest.fixture
def agent():
    return get_default_comparison_agent()


# ---------------------------------------------------------
# Test End-to-End Company Comparison
# ---------------------------------------------------------

def test_compare_abbott_and_amd_2023(agent):
    res = agent.answer_query("Compare Abbott and AMD in 2023")
    assert isinstance(res, ComparisonResult)
    assert res.status == "SUCCESS"
    assert res.fiscal_year == 2023
    assert len(res.companies) == 2
    assert "ABBOTT LABORATORIES" in res.companies
    assert "ADVANCED MICRO DEVICES INC" in res.companies

    # Verify metrics table rows
    metrics_in_table = [row["metric"] for row in res.metrics_table]
    assert "Revenue" in metrics_in_table
    assert "Net Income" in metrics_in_table
    assert "Net Profit Margin" in metrics_in_table
    assert "ROA" in metrics_in_table
    assert "Current Ratio" in metrics_in_table

    # Check side-by-side alignment
    rev_row = next(r for r in res.metrics_table if r["metric"] == "Revenue")
    assert rev_row["values"]["ABBOTT LABORATORIES"] == 40109000000
    assert rev_row["values"]["ADVANCED MICRO DEVICES INC"] == 22680000000

    margin_row = next(r for r in res.metrics_table if r["metric"] == "Net Profit Margin")
    assert round(margin_row["values"]["ABBOTT LABORATORIES"], 2) == 14.27
    assert round(margin_row["values"]["ADVANCED MICRO DEVICES INC"], 2) == 3.77

    # Check comparative analysis text
    assert len(res.comparative_analysis) >= 3
    assert any("Scale" in line for line in res.comparative_analysis)
    assert any("Profitability" in line for line in res.comparative_analysis)


def test_no_arbitrary_winner_ranking(agent):
    res = agent.answer_query("Compare Abbott and AMD in 2023")
    # Must report transparent metrics without arbitrary winner declarations
    assert "is the winner" not in res.summary.lower()
    assert "is objectively better" not in res.summary.lower()
    assert "Scale:" in res.summary
    assert "Profitability:" in res.summary


# ---------------------------------------------------------
# Test Query Parsing & Multi-Entity Resolution
# ---------------------------------------------------------

def test_query_parsing_multi_entities(agent):
    p = agent.parse_query("Compare AAR Corp vs Acme United in 2023")
    assert len(p["companies"]) == 2
    c_names = [c.entity_name for c in p["companies"]]
    assert "AAR CORP." in c_names
    assert "ACME UNITED CORP" in c_names
    assert p["fiscal_year"] == 2023


def test_query_parsing_year_override(agent):
    p = agent.parse_query("Compare Abbott Laboratories and Advanced Micro Devices in 2024")
    assert p["fiscal_year"] == 2024
    assert len(p["companies"]) == 2


# ---------------------------------------------------------
# Test Error Handling & Edge Cases
# ---------------------------------------------------------

def test_single_company_insufficient_error(agent):
    res = agent.answer_query("Compare Abbott in 2023")
    assert res.status == "INSUFFICIENT_COMPANIES"
    assert "at least two company names" in res.summary


def test_convenience_function():
    res = compare_companies(["ABBOTT LABORATORIES", "ADVANCED MICRO DEVICES INC"], 2023)
    assert res.status == "SUCCESS"
    assert len(res.companies) == 2
