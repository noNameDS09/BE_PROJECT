"""
Tests for FARE-Style Risk Extraction Agent (Phase 11).
"""

import pytest

from src.agents.risk_extraction_agent import (
    LIMITATION_NOTICE,
    RiskAnalysisResult,
    RiskExtractionAgent,
    RiskItem,
    assess_company_risks,
    get_default_risk_agent,
)


@pytest.fixture
def agent():
    return get_default_risk_agent()


# ---------------------------------------------------------
# Test Research Data Boundary & Notice
# ---------------------------------------------------------

def test_data_limitation_notice_present(agent):
    res = agent.assess_financial_risks("ABBOTT LABORATORIES", 2023)
    assert res.status == "SUCCESS"
    assert LIMITATION_NOTICE in res.data_limitation_notice
    assert "DATA LIMITATION" in res.data_limitation_notice or "LIMITATION" in res.data_limitation_notice


# ---------------------------------------------------------
# Test Structured RiskItem Schema (6 Required Fields)
# ---------------------------------------------------------

def test_risk_item_schema_conformance(agent):
    res = agent.assess_financial_risks("ABBOTT LABORATORIES", 2023)
    assert len(res.risks) >= 3

    for item in res.risks:
        assert isinstance(item, RiskItem)
        d = item.to_dict()

        # All 6 required research attributes must be present and non-empty
        assert "Risk" in d and len(d["Risk"]) > 0
        assert "Category" in d and len(d["Category"]) > 0
        assert "Evidence" in d and len(d["Evidence"]) > 0
        assert "Source" in d and len(d["Source"]) > 0
        assert "Reasoning" in d and len(d["Reasoning"]) > 0
        assert "Confidence" in d and isinstance(d["Confidence"], (int, float))
        assert 0.0 <= d["Confidence"] <= 1.0


# ---------------------------------------------------------
# Test Quantitative Risk Signals & Distress Detection
# ---------------------------------------------------------

def test_distress_detection_aceto_corp(agent):
    # Aceto Corp (CIK 0000002034) prior to bankruptcy had severe leverage and net losses
    res = agent.assess_financial_risks("ACETO CORP", 2018)
    assert res.status == "SUCCESS"

    high_risks = [r for r in res.risks if r.severity == "HIGH"]
    assert len(high_risks) >= 1

    # Check Solvency / Leverage Risk triggered HIGH
    solvency_risk = next(r for r in res.risks if r.category == "Solvency / Capital Structure")
    assert solvency_risk.severity == "HIGH"
    assert "87.6%" in solvency_risk.reasoning or "87.5%" in solvency_risk.reasoning or "High leverage" in solvency_risk.reasoning

    # Check Operational / Profitability Risk triggered HIGH (due to negative net margin)
    profitability_risk = next(r for r in res.risks if r.category == "Operational / Profitability")
    assert profitability_risk.severity == "HIGH"


def test_abbott_low_to_moderate_risk_profile(agent):
    res = agent.assess_financial_risks("ABBOTT LABORATORIES", 2024)
    assert res.status == "SUCCESS"

    # Abbott has sound liquidity (Current Ratio > 1.5)
    cr_risk = next(r for r in res.risks if r.category == "Liquidity")
    assert cr_risk.severity == "LOW"
    assert "Sound liquidity buffer" in cr_risk.reasoning


# ---------------------------------------------------------
# Test Narrative Risk Ingestion (Prepared for SEC 10-K Text)
# ---------------------------------------------------------

def test_narrative_risk_ingestion(agent):
    sample_10k_text = (
        "• We face intense competition in our diagnostics and pharmaceutical markets. "
        "Our competitors may develop more effective or less costly products that render our offerings obsolete.\n\n"
        "• Our substantial indebtedness could adversely affect our financial condition and limit our ability "
        "to react to changes in our business or raise additional capital to satisfy debt covenants.\n\n"
        "• We are subject to stringent government regulations and healthcare compliance laws, including FDA oversight. "
        "Failure to comply with regulatory standards could lead to product recalls or fines."
    )

    items = agent.ingest_narrative_risk_factors(
        company="ABBOTT LABORATORIES",
        filing_text=sample_10k_text,
        source="SEC Form 10-K Item 1A"
    )

    assert len(items) == 3
    categories = {item.category for item in items}
    assert "Market & Competitive" in categories
    assert "Solvency / Capital Structure" in categories
    assert "Regulatory & Legal" in categories

    for item in items:
        assert item.is_quantitative is False
        assert "SEC Form 10-K Item 1A" in item.source


# ---------------------------------------------------------
# Test Natural Language Query & Convenience Function
# ---------------------------------------------------------

def test_answer_query_risk(agent):
    res = agent.answer_query("What financial risks does Abbott face in 2023?")
    assert isinstance(res, RiskAnalysisResult)
    assert res.status == "SUCCESS"
    assert res.company == "ABBOTT LABORATORIES"
    assert len(res.risks) >= 3


def test_convenience_function():
    res = assess_company_risks("ABBOTT LABORATORIES", 2023)
    assert res.status == "SUCCESS"
    assert len(res.risks) >= 3
