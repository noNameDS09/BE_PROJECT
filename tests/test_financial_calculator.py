"""
Tests for Deterministic Financial Calculator (Phase 6).
"""

import pytest

from src.retrieval.financial_query import FinancialFactResult, query_financial_fact
from src.tools.financial_calculator import (
    CalculationResult,
    FinancialCalculator,
    calculate_current_ratio,
    calculate_debt_ratio,
    calculate_debt_to_equity,
    calculate_profit_margin,
    calculate_revenue_growth,
    calculate_roa,
    calculate_roe,
    get_default_calculator,
)


@pytest.fixture
def calculator():
    return get_default_calculator()


# ---------------------------------------------------------
# Test Core Deterministic Calculations
# ---------------------------------------------------------

def test_revenue_growth_calculation(calculator):
    # $100M to $120M -> +20.0%
    res = calculator.calculate_revenue_growth(120_000_000, 100_000_000)
    assert isinstance(res, CalculationResult)
    assert res.value == 20.0
    assert res.status == "SUCCESS"
    assert res.unit == "%"
    assert "Current Revenue" in res.formula


def test_profit_margin_calculation(calculator):
    # Net Income $25M on Revenue $100M -> 25.0%
    res = calculator.calculate_profit_margin(25_000_000, 100_000_000, "Net Profit Margin")
    assert res.value == 25.0
    assert res.status == "SUCCESS"


def test_roa_calculation(calculator):
    # Net Income $10M on Assets $100M -> 10.0%
    res = calculator.calculate_roa(10_000_000, 100_000_000)
    assert res.value == 10.0
    assert res.metric == "ROA"


def test_roe_calculation(calculator):
    # Net Income $15M on Equity $60M -> 25.0%
    res = calculator.calculate_roe(15_000_000, 60_000_000)
    assert res.value == 25.0
    assert res.metric == "ROE"


def test_current_ratio_calculation(calculator):
    # Current Assets $150M / Current Liabilities $75M -> 2.0x
    res = calculator.calculate_current_ratio(150_000_000, 75_000_000)
    assert res.value == 2.0
    assert res.unit == "ratio"


def test_debt_to_equity_calculation(calculator):
    # Debt $40M / Equity $80M -> 0.5x
    res = calculator.calculate_debt_to_equity(40_000_000, 80_000_000)
    assert res.value == 0.5


def test_debt_ratio_calculation(calculator):
    # Liabilities $40M / Assets $100M -> 0.4 (40%)
    res = calculator.calculate_debt_ratio(40_000_000, 100_000_000)
    assert res.value == 0.4


# ---------------------------------------------------------
# Test Required Output Schema & Reproducibility
# ---------------------------------------------------------

def test_result_dictionary_structure(calculator):
    res = calculator.calculate_revenue_growth(110, 100)
    d = res.to_dict()

    # Exact required keys from project specification
    assert "metric" in d
    assert "value" in d
    assert "formula" in d
    assert "inputs" in d
    assert "source_facts" in d

    assert isinstance(d["inputs"], list)
    assert len(d["inputs"]) == 2
    assert d["value"] == 10.0


def test_calculation_reproducibility(calculator):
    res1 = calculator.calculate_revenue_growth(123456789, 98765432)
    res2 = calculator.calculate_revenue_growth(123456789, 98765432)
    assert res1.value == res2.value
    assert res1.formula == res2.formula


# ---------------------------------------------------------
# Test Edge Cases & Defensive Arithmetic
# ---------------------------------------------------------

def test_zero_denominator_revenue_growth(calculator):
    res = calculator.calculate_revenue_growth(100, 0)
    assert res.value is None
    assert res.status == "ZERO_DENOMINATOR"


def test_zero_denominator_ratios(calculator):
    # ROA with 0 assets
    res_roa = calculator.calculate_roa(10, 0)
    assert res_roa.value is None
    assert res_roa.status == "ZERO_DENOMINATOR"

    # Current ratio with 0 liabilities
    res_cr = calculator.calculate_current_ratio(10, 0)
    assert res_cr.value is None
    assert res_cr.status == "ZERO_DENOMINATOR"


def test_missing_input_values(calculator):
    res = calculator.calculate_profit_margin(None, 100)
    assert res.value is None
    assert res.status == "MISSING_INPUTS"


def test_negative_values_handling(calculator):
    # Company with net loss (-$20M on $100M revenue)
    res = calculator.calculate_profit_margin(-20_000_000, 100_000_000)
    assert res.value == -20.0
    assert res.status == "SUCCESS"


def test_unit_mismatch_detection(calculator):
    fact_usd = FinancialFactResult(
        value=100, unit="USD", fiscal_year=2024, fiscal_period="FY",
        form="10-K", filed_date="2025-01-01", concept="Revenues",
        source_company="Test Corp", source_cik="0000000001"
    )
    fact_eur = FinancialFactResult(
        value=80, unit="EUR", fiscal_year=2023, fiscal_period="FY",
        form="10-K", filed_date="2024-01-01", concept="Revenues",
        source_company="Test Corp", source_cik="0000000001"
    )
    res = calculator.calculate_revenue_growth(fact_usd, fact_eur)
    assert res.value is None
    assert res.status == "UNIT_MISMATCH"


# ---------------------------------------------------------
# Test Real Dataset Integration
# ---------------------------------------------------------

def test_abbott_2024_calculations(calculator):
    # Retrieve real facts from Abbott Laboratories
    rev24 = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2024)
    rev23 = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2023)
    ni24 = query_financial_fact("ABBOTT LABORATORIES", "Net Income", 2024)
    assets24 = query_financial_fact("ABBOTT LABORATORIES", "Total Assets", 2024)
    equity24 = query_financial_fact("ABBOTT LABORATORIES", "Stockholders Equity", 2024)
    ca24 = query_financial_fact("ABBOTT LABORATORIES", "Current Assets", 2024)
    cl24 = query_financial_fact("ABBOTT LABORATORIES", "Current Liabilities", 2024)

    # 1. Revenue Growth
    growth = calculator.calculate_revenue_growth(rev24, rev23)
    assert growth.status == "SUCCESS"
    assert round(growth.value, 2) == 4.59  # 41,950M vs 40,109M is +4.59%
    assert len(growth.source_facts) == 2

    # 2. Net Margin
    margin = calculator.calculate_profit_margin(ni24, rev24)
    assert margin.status == "SUCCESS"
    assert round(margin.value, 2) == 31.95  # 13,402M / 41,950M is 31.95%

    # 3. ROA
    roa = calculator.calculate_roa(ni24, assets24)
    assert roa.status == "SUCCESS"
    assert round(roa.value, 2) == 16.46  # 13,402M / 81,414M is 16.46%

    # 4. ROE
    roe = calculator.calculate_roe(ni24, equity24)
    assert roe.status == "SUCCESS"
    assert round(roe.value, 2) == 28.12  # 13,402M / 47,664M is 28.12%

    # 5. Current Ratio
    cr = calculator.calculate_current_ratio(ca24, cl24)
    assert cr.status == "SUCCESS"
    assert round(cr.value, 2) == 1.67  # 23,656M / 14,157M is 1.67x


def test_automated_compute_all_ratios(calculator):
    ratios = calculator.compute_all_ratios("ABBOTT LABORATORIES", 2024)
    assert "Revenue Growth" in ratios
    assert "Net Profit Margin" in ratios
    assert "ROA" in ratios
    assert "ROE" in ratios
    assert "Current Ratio" in ratios
    assert "Debt-to-Equity" in ratios
    assert "Debt Ratio" in ratios

    for metric_name, result in ratios.items():
        assert isinstance(result, CalculationResult)
        assert result.status == "SUCCESS"
        assert result.value is not None
