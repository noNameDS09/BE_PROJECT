"""
Tests for Financial Metric Mapping & Concept Resolution (Phase 5).
"""

import pytest

from src.retrieval.metric_mapper import (
    CONTROLLED_METRICS,
    UNRESOLVED_STATUS,
    MetricMapper,
    MetricResolutionResult,
    get_default_mapper,
    list_supported_metrics,
    resolve_metric,
)


@pytest.fixture
def mapper():
    return get_default_mapper()


# ---------------------------------------------------------
# Test Controlled Ontology Definitions
# ---------------------------------------------------------

def test_controlled_metrics_exist():
    expected = [
        "Revenue", "Net Income", "Total Assets", "Total Liabilities",
        "Stockholders Equity", "Cash", "Current Assets", "Current Liabilities",
        "Operating Income", "Gross Profit", "Operating Cash Flow"
    ]
    supported = list_supported_metrics()
    for metric in expected:
        assert metric in supported
        assert metric in CONTROLLED_METRICS


def test_alias_normalization(mapper):
    assert mapper.get_canonical_name("topline") == "Revenue"
    assert mapper.get_canonical_name("sales") == "Revenue"
    assert mapper.get_canonical_name("net_income") == "Net Income"
    assert mapper.get_canonical_name("ebit") == "Operating Income"
    assert mapper.get_canonical_name("cfo") == "Operating Cash Flow"
    assert mapper.get_canonical_name("assets") == "Total Assets"
    assert mapper.get_canonical_name("equity") == "Stockholders Equity"


# ---------------------------------------------------------
# Test Dynamic Company-Specific Concept Resolution
# ---------------------------------------------------------

def test_resolve_revenue_abbott(mapper):
    # Abbott uses ASC 606 concept
    res = mapper.resolve_metric("ABBOTT LABORATORIES", "revenue")
    assert isinstance(res, MetricResolutionResult)
    assert res.is_resolved is True
    assert res.status == "RESOLVED"
    assert res.canonical_metric == "Revenue"
    assert res.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert str(res) == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_resolve_revenue_acme_united(mapper):
    # Acme United Corp (CIK 0000002098) uses Revenues concept
    res = mapper.resolve_metric("0000002098", "Revenue")
    assert res.is_resolved is True
    assert res.concept == "Revenues"


def test_resolve_balance_sheet_metrics(mapper):
    # Total Assets
    res_assets = mapper.resolve_metric("Advanced Micro Devices", "Total Assets")
    assert res_assets.is_resolved is True
    assert res_assets.concept == "Assets"

    # Cash
    res_cash = mapper.resolve_metric("Advanced Micro Devices", "Cash")
    assert res_cash.is_resolved is True
    assert res_cash.concept == "CashAndCashEquivalentsAtCarryingValue"

    # Current Assets
    res_curr_assets = mapper.resolve_metric("Advanced Micro Devices", "Current Assets")
    assert res_curr_assets.is_resolved is True
    assert res_curr_assets.concept == "AssetsCurrent"


# ---------------------------------------------------------
# Test Unresolved / Unavailable Metric Handling
# ---------------------------------------------------------

def test_unresolved_metric_returns_unresolved_status():
    res = resolve_metric("ABBOTT LABORATORIES", "CompletelyFakeMetricXYZ")
    assert isinstance(res, MetricResolutionResult)
    assert res.is_resolved is False
    assert res.status == UNRESOLVED_STATUS
    assert res.concept is None
    assert str(res) == "Metric unavailable / unresolved"


def test_unresolved_metric_on_empty_company():
    # CIK 0000003521 has empty facts
    res = resolve_metric(3521, "Revenue")
    assert res.is_resolved is False
    assert res.status == UNRESOLVED_STATUS
    assert str(res) == "Metric unavailable / unresolved"


def test_candidate_concepts_fallback(mapper):
    cands = mapper.get_candidate_concepts("revenue")
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in cands
    assert "Revenues" in cands

    # Non-registered string returns direct query
    custom_cands = mapper.get_candidate_concepts("CustomXBRLTag")
    assert custom_cands == ["CustomXBRLTag"]
