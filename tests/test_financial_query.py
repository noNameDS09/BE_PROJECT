"""
Tests for Financial Query Engine (Phase 4).
"""

import pytest

from src.retrieval.financial_query import (
    FinancialFactResult,
    FinancialQueryEngine,
    query_financial_fact,
    query_facts_timeseries,
    get_default_query_engine,
)


@pytest.fixture
def engine():
    return get_default_query_engine()


# ---------------------------------------------------------
# Test Core Structured Fact Retrieval
# ---------------------------------------------------------

def test_query_annual_revenue_abbott(engine):
    result = engine.query_financial_fact(
        company="ABBOTT LABORATORIES",
        metric="Revenue",
        fiscal_year=2023,
        fiscal_period="FY"
    )
    assert result is not None
    assert isinstance(result, FinancialFactResult)
    assert result.value == 40109000000
    assert result.unit == "USD"
    assert result.fiscal_year == 2023
    assert result.fiscal_period == "FY"
    assert result.form == "10-K"
    assert result.source_company == "ABBOTT LABORATORIES"
    assert result.source_cik == "0000001800"
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in result.concept
    assert result.accession_number is not None
    assert result.selection_notes != ""


def test_query_annual_revenue_amd(engine):
    result = query_financial_fact(
        company="Advanced Micro Devices",
        metric="Revenue",
        fiscal_year=2023
    )
    assert result is not None
    assert result.value == 22680000000
    assert result.unit == "USD"
    assert result.fiscal_year == 2023
    assert result.source_cik == "0000002488"


# ---------------------------------------------------------
# Test Balance Sheet (Instantaneous) Facts
# ---------------------------------------------------------

def test_query_balance_sheet_assets(engine):
    result = query_financial_fact(
        company="0000002488",  # Query by CIK
        metric="Total Assets",
        fiscal_year=2023
    )
    assert result is not None
    assert result.concept == "Assets"
    assert result.value == 67885000000
    assert result.unit == "USD"


def test_query_cash(engine):
    result = query_financial_fact(
        company="Advanced Micro Devices",
        metric="Cash",
        fiscal_year=2023
    )
    assert result is not None
    assert result.value == 3933000000
    assert result.unit == "USD"


# ---------------------------------------------------------
# Test Annual vs Quarterly Discrimination
# ---------------------------------------------------------

def test_query_quarterly_revenue_discrete_periods(engine):
    # Abbott Q1 2024
    q1 = query_financial_fact(
        company="ABBOTT LABORATORIES",
        metric="Revenue",
        fiscal_year=2024,
        fiscal_period="Q1"
    )
    assert q1 is not None
    assert q1.fiscal_period == "Q1"
    assert q1.form == "10-Q"
    assert q1.value == 9964000000

    # Abbott Q2 2024 (must be discrete quarter ~$10.377B, NOT cumulative 6-month ~$20.341B)
    q2 = query_financial_fact(
        company="ABBOTT LABORATORIES",
        metric="Revenue",
        fiscal_year=2024,
        fiscal_period="Q2"
    )
    assert q2 is not None
    assert q2.fiscal_period == "Q2"
    assert q2.form == "10-Q"
    assert q2.value == 10377000000


# ---------------------------------------------------------
# Test Multi-Year Time-Series Retrieval
# ---------------------------------------------------------

def test_query_facts_timeseries(engine):
    ts = query_facts_timeseries(
        company="ABBOTT LABORATORIES",
        metric="Revenue",
        start_year=2022,
        end_year=2024
    )
    assert len(ts) == 3
    years = [r.fiscal_year for r in ts]
    assert years == [2022, 2023, 2024]

    vals = [r.value for r in ts]
    assert vals == [43653000000, 40109000000, 41950000000]


# ---------------------------------------------------------
# Test Missing Data & Safety (No Hallucinations)
# ---------------------------------------------------------

def test_query_nonexistent_year_returns_none(engine):
    # Year 1950 is not in SEC XBRL data
    res = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 1950)
    assert res is None


def test_query_nonexistent_metric_returns_none(engine):
    res = query_financial_fact("ABBOTT LABORATORIES", "CompletelyFakeNonExistentMetric123", 2023)
    assert res is None


def test_result_to_dict_structure(engine):
    res = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2023)
    assert res is not None
    d = res.to_dict()
    required_keys = [
        "value", "unit", "fiscal_year", "fiscal_period", "form",
        "filed_date", "concept", "source_company", "source_cik"
    ]
    for key in required_keys:
        assert key in d
        assert d[key] is not None
