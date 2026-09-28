"""
Tests for Financial Validation Layer (Phase 12).
"""

import pytest

from src.retrieval.financial_query import FinancialFactResult, query_financial_fact
from src.tools.financial_calculator import CalculationResult, calculate_revenue_growth
from src.tools.validation import (
    FinancialValidator,
    ValidationIssue,
    ValidationReport,
    get_default_validator,
    validate_financial_data,
)


@pytest.fixture
def validator():
    return get_default_validator()


# ---------------------------------------------------------
# Test Retrieved Values Validation
# ---------------------------------------------------------

def test_valid_retrieved_fact(validator):
    fact = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2024)
    rep = validator.validate_retrieved_fact(fact)
    assert isinstance(rep, ValidationReport)
    assert rep.is_valid is True
    assert "RetrievedValueCheck" in rep.passed_checks
    assert "FiscalYearBoundsCheck" in rep.passed_checks
    assert "SourceMetadataCheck" in rep.passed_checks


def test_null_value_fails(validator):
    bad_fact = {
        "value": None,
        "concept": "Revenues",
        "fiscal_year": 2024,
        "source_company": "Test Corp",
        "source_cik": "0000000001",
        "form": "10-K",
        "filed_date": "2025-01-01"
    }
    rep = validator.validate_retrieved_fact(bad_fact)
    assert rep.is_valid is False
    assert any(i.check_name == "RetrievedValueCheck" for i in rep.issues)


def test_negative_assets_fails(validator):
    bad_fact = {
        "value": -50_000_000,
        "concept": "Assets",
        "fiscal_year": 2024,
        "source_company": "Test Corp",
        "source_cik": "0000000001",
        "form": "10-K",
        "filed_date": "2025-01-01"
    }
    rep = validator.validate_retrieved_fact(bad_fact)
    assert rep.is_valid is False
    assert any(i.check_name == "NonNegativityCheck" for i in rep.issues)


def test_invalid_fiscal_year(validator):
    bad_fact = {
        "value": 100_000,
        "concept": "Revenues",
        "fiscal_year": 1820,
        "source_company": "Test Corp",
        "source_cik": "0000000001",
        "form": "10-K",
        "filed_date": "2025-01-01"
    }
    rep = validator.validate_retrieved_fact(bad_fact)
    assert rep.is_valid is False
    assert any(i.check_name == "FiscalYearBoundsCheck" for i in rep.issues)


# ---------------------------------------------------------
# Test Calculation Inputs & Outputs Validation
# ---------------------------------------------------------

def test_valid_calculation(validator):
    calc = calculate_revenue_growth(110, 100)
    rep = validator.validate_calculation(calc)
    assert rep.is_valid is True
    assert "MathematicalConsistencyCheck" in rep.passed_checks
    assert "UnitConsistencyCheck" in rep.passed_checks


def test_mathematical_discrepancy_detected(validator):
    # Spoofed/corrupted calculation result (e.g. LLM hallucinates 50% instead of 10%)
    corrupted_calc = {
        "metric": "Revenue Growth",
        "value": 50.0,  # False arithmetic
        "formula": "((Current - Previous) / Previous) * 100",
        "inputs": [
            {"name": "Current", "value": 110.0, "unit": "USD"},
            {"name": "Previous", "value": 100.0, "unit": "USD"}
        ],
        "status": "SUCCESS"
    }
    rep = validator.validate_calculation(corrupted_calc)
    assert rep.is_valid is False
    assert any(i.check_name == "MathematicalConsistencyCheck" for i in rep.issues)


def test_unit_mismatch_in_calculation(validator):
    mismatched = {
        "metric": "Revenue Growth",
        "value": 10.0,
        "formula": "((Current - Previous) / Previous) * 100",
        "inputs": [
            {"name": "Current", "value": 110.0, "unit": "USD"},
            {"name": "Previous", "value": 100.0, "unit": "EUR"}
        ],
        "status": "SUCCESS"  # Claimed success despite mismatch
    }
    rep = validator.validate_calculation(mismatched)
    assert rep.is_valid is False
    assert any(i.check_name == "UnitConsistencyCheck" for i in rep.issues)


# ---------------------------------------------------------
# Test Contradictory Facts & Accounting Identity
# ---------------------------------------------------------

def test_contradictory_facts_warning(validator):
    f1 = {
        "source_cik": "0000001800", "concept": "Revenues", "fiscal_year": 2024,
        "fiscal_period": "FY", "value": 100_000, "filed_date": "2025-01-01",
        "form": "10-K", "source_company": "Abbott"
    }
    f2 = {
        "source_cik": "0000001800", "concept": "Revenues", "fiscal_year": 2024,
        "fiscal_period": "FY", "value": 120_000, "filed_date": "2025-02-01",
        "form": "10-K/A", "source_company": "Abbott"
    }
    rep = validator.validate_facts_consistency([f1, f2])
    assert rep.has_warnings is True
    assert any(i.check_name == "ContradictoryFactsCheck" for i in rep.issues)


def test_accounting_identity_balance(validator):
    # Assets = 100M, Liabilities = 40M, Equity = 60M
    rep = validator.validate_accounting_identity(100_000_000, 40_000_000, 60_000_000)
    assert rep.is_valid is True
    assert "AccountingIdentityCheck" in rep.passed_checks


def test_accounting_identity_discrepancy(validator):
    # Assets = 100M, Liabilities = 50M, Equity = 80M (Total = 130M, 30% error)
    rep = validator.validate_accounting_identity(100_000_000, 50_000_000, 80_000_000)
    assert rep.has_warnings is True
    assert any(i.check_name == "AccountingIdentityCheck" for i in rep.issues)


# ---------------------------------------------------------
# Test Full Pipeline Gatekeeper
# ---------------------------------------------------------

def test_pipeline_gatekeeper(validator):
    fact = query_financial_fact("ABBOTT LABORATORIES", "Revenue", 2024)
    calc = calculate_revenue_growth(110, 100)
    rep = validate_financial_data(facts=[fact], calculations=[calc])
    assert rep.is_valid is True
    assert rep.error_count == 0
