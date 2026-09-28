"""
Tests for Explainability & Provenance Layer (Phase 13).
"""

import pytest

from src.agents.investment_agent import analyze_financial_performance
from src.agents.statement_extraction_agent import extract_financial_statement_fact
from src.explainability.provenance import (
    CalculationAuditRecord,
    ProvenanceEngine,
    SECSourceRecord,
    TraceabilityChain,
    build_provenance_chain,
    get_default_provenance_engine,
)
from src.retrieval.financial_query import query_financial_fact
from src.tools.financial_calculator import calculate_revenue_growth


@pytest.fixture
def engine():
    return get_default_provenance_engine()


# ---------------------------------------------------------
# Test 6-Tier Traceability Structure Conformance
# ---------------------------------------------------------

def test_traceability_chain_structure(engine):
    # From statement extraction
    stat_res = extract_financial_statement_fact("What was Abbott's revenue in FY2024?")
    chain = engine.build_from_statement_extraction(stat_res)

    assert isinstance(chain, TraceabilityChain)
    d = chain.to_dict()

    # Exact 6 tiers required
    assert "answer" in d and len(d["answer"]) > 0
    assert "reason" in d and len(d["reason"]) > 0
    assert "financial_metrics" in d and len(d["financial_metrics"]) > 0
    assert "calculations" in d
    assert "sec_evidence" in d and len(d["sec_evidence"]) > 0
    assert "source_metadata" in d and d["source_metadata"]["company"] == "ABBOTT LABORATORIES"


# ---------------------------------------------------------
# Test Calculation Provenance (Formula, Inputs, Lineage)
# ---------------------------------------------------------

def test_calculation_provenance(engine):
    rev24 = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2024)
    rev23 = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2023)
    growth_calc = calculate_revenue_growth(rev24, rev23)

    chain = engine.build_from_calculation(growth_calc, company="ABBOTT LABORATORIES")
    assert chain.financial_metrics == ["Revenue Growth"]
    assert len(chain.calculations) == 1

    audit_calc = chain.calculations[0]
    assert isinstance(audit_calc, CalculationAuditRecord)
    assert audit_calc.metric == "Revenue Growth"
    assert "Current Revenue" in audit_calc.formula
    assert len(audit_calc.inputs) == 2
    assert round(audit_calc.output_value, 2) == 4.59

    # Check SEC evidence attached
    assert len(chain.sec_evidence) == 2
    for ev in chain.sec_evidence:
        assert isinstance(ev, SECSourceRecord)
        assert ev.form == "10-K"
        assert ev.accession_number is not None

    # Check source metadata
    assert chain.source_metadata["company"] == "ABBOTT LABORATORIES"
    assert len(chain.source_metadata["accession_numbers"]) > 0


# ---------------------------------------------------------
# Test Multi-Period Investment Provenance
# ---------------------------------------------------------

def test_investment_analysis_provenance(engine):
    inv_res = analyze_financial_performance("ABBOTT LABORATORIES", 2022, 2024)
    chain = engine.build_from_investment_analysis(inv_res)

    assert len(chain.calculations) >= 3
    assert len(chain.sec_evidence) >= 4
    assert chain.source_metadata["company"] == "ABBOTT LABORATORIES"
    assert chain.source_metadata["cik"] == "0000001800"


# ---------------------------------------------------------
# Test Markdown Audit Card Generation
# ---------------------------------------------------------

def test_markdown_audit_card_rendering(engine):
    stat_res = extract_financial_statement_fact("What was Abbott's revenue in FY2024?")
    chain = engine.build_from_statement_extraction(stat_res)
    md = chain.to_markdown()

    assert "#### Financial Provenance & Audit Trail" in md
    assert "**1. Answer:**" in md
    assert "**2. Reason:**" in md
    assert "**3. Financial Metrics:**" in md
    assert "**4. Calculations:**" in md
    assert "**5. SEC Evidence:**" in md
    assert "**6. Source Metadata:**" in md
    assert "ABBOTT LABORATORIES" in md
    assert "Form 10-K" in md


# ---------------------------------------------------------
# Test Convenience Function
# ---------------------------------------------------------

def test_convenience_function():
    stat_res = extract_financial_statement_fact("What was Abbott's revenue in FY2024?")
    chain = build_provenance_chain(stat_res)
    assert isinstance(chain, TraceabilityChain)
    assert chain.source_metadata["company"] == "ABBOTT LABORATORIES"
