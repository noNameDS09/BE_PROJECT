"""
Tests for Financial Fact Normalizer (Phase 2).
"""

from pathlib import Path
import pytest

from src.data.sec_loader import CompanyFacts, load_company_by_cik
from src.data.financial_normalizer import (
    NormalizedFact,
    FinancialFactNormalizer,
    normalize_facts,
)


@pytest.fixture
def sample_company_facts():
    """Returns a synthetic CompanyFacts object covering various namespaces, units, and edge cases."""
    return CompanyFacts(
        cik="0000001750",
        entity_name="AAR CORP.",
        facts={
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "label": "Shares Outstanding",
                    "description": "Common stock outstanding count",
                    "units": {
                        "shares": [
                            {
                                "end": "2023-08-31",
                                "val": 34912000,
                                "fy": 2024,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2023-09-21",
                                "frame": "CY2023Q3I",
                                "accn": "0001104659-23-102555"
                            }
                        ]
                    }
                }
            },
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "description": "Total revenue recognized",
                    "units": {
                        "USD": [
                            {
                                "start": "2022-06-01",
                                "end": "2023-05-31",
                                "val": 1990800000,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-07-18",
                                "frame": "CY2022",
                                "accn": "0001104659-23-082001"
                            },
                            {
                                "start": "2023-06-01",
                                "end": "2023-08-31",
                                "val": 549700000,
                                "fy": 2024,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2023-09-21",
                                "accn": "0001104659-23-102555"
                            }
                        ]
                    }
                },
                "GrossProfit": {
                    "label": "Gross Profit",
                    "units": {
                        "USD": [
                            {
                                "start": "2022-06-01",
                                "end": "2023-05-31",
                                "val": 361500000,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-07-18"
                            }
                        ]
                    }
                }
            },
            "custom-tax": {
                "NonStandardMetric": {
                    "label": "Custom Metric",
                    "units": {
                        "pure": [
                            {
                                "end": "2023-05-31",
                                "val": 0.85,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2023-07-18"
                            }
                        ]
                    }
                }
            }
        },
        file_path=Path("Data/CIK0000001750.json")
    )


# ---------------------------------------------------------
# Test Basic Normalization
# ---------------------------------------------------------

def test_normalization_structure(sample_company_facts):
    facts = normalize_facts(sample_company_facts)
    assert len(facts) == 5

    rev_fact = next(f for f in facts if f.concept == "Revenues" and f.fp == "FY")
    assert isinstance(rev_fact, NormalizedFact)
    assert rev_fact.company == "AAR CORP."
    assert rev_fact.cik == "0000001750"
    assert rev_fact.taxonomy == "us-gaap"
    assert rev_fact.concept == "Revenues"
    assert rev_fact.metric == "Revenues"
    assert rev_fact.unit == "USD"
    assert rev_fact.value == 1990800000
    assert rev_fact.start == "2022-06-01"
    assert rev_fact.end == "2023-05-31"
    assert rev_fact.fy == 2023
    assert rev_fact.fp == "FY"
    assert rev_fact.form == "10-K"
    assert rev_fact.filed == "2023-07-18"
    assert rev_fact.frame == "CY2022"
    assert rev_fact.accn == "0001104659-23-082001"
    assert rev_fact.label == "Revenues"


def test_fact_to_dict(sample_company_facts):
    facts = normalize_facts(sample_company_facts)
    d = facts[0].to_dict()
    expected_keys = {
        "company", "cik", "taxonomy", "concept", "metric", "unit",
        "value", "start", "end", "fy", "fp", "form", "filed",
        "frame", "accn", "label", "description"
    }
    assert expected_keys.issubset(set(d.keys()))


# ---------------------------------------------------------
# Test Multi-Namespace Support
# ---------------------------------------------------------

def test_multiple_taxonomies_supported(sample_company_facts):
    facts = normalize_facts(sample_company_facts)
    taxonomies = {f.taxonomy for f in facts}
    assert "dei" in taxonomies
    assert "us-gaap" in taxonomies
    assert "custom-tax" in taxonomies


def test_filter_by_taxonomy(sample_company_facts):
    normalizer = FinancialFactNormalizer()
    dei_facts = normalizer.normalize_company_facts(sample_company_facts, taxonomies=["dei"])
    assert len(dei_facts) == 1
    assert dei_facts[0].taxonomy == "dei"
    assert dei_facts[0].concept == "EntityCommonStockSharesOutstanding"


def test_filter_by_concept(sample_company_facts):
    normalizer = FinancialFactNormalizer()
    rev_facts = normalizer.normalize_company_facts(sample_company_facts, concepts=["Revenues"])
    assert len(rev_facts) == 2
    for f in rev_facts:
        assert f.concept == "Revenues"


# ---------------------------------------------------------
# Test Concept Variation / Alias Mapping
# ---------------------------------------------------------

def test_concept_alias_mapping(sample_company_facts):
    alias_map = {
        "Revenues": "Revenue",
        "GrossProfit": "Gross Profit"
    }
    normalizer = FinancialFactNormalizer(concept_alias_map=alias_map)
    facts = normalizer.normalize_company_facts(sample_company_facts)

    rev_fact = next(f for f in facts if f.concept == "Revenues")
    assert rev_fact.metric == "Revenue"

    gp_fact = next(f for f in facts if f.concept == "GrossProfit")
    assert gp_fact.metric == "Gross Profit"

    # Unmapped concept should default to its concept name
    dei_fact = next(f for f in facts if f.concept == "EntityCommonStockSharesOutstanding")
    assert dei_fact.metric == "EntityCommonStockSharesOutstanding"


# ---------------------------------------------------------
# Test Helper Properties & Date Logic
# ---------------------------------------------------------

def test_annual_and_quarterly_properties(sample_company_facts):
    facts = normalize_facts(sample_company_facts)
    annual_fact = next(f for f in facts if f.concept == "Revenues" and f.fp == "FY")
    quarterly_fact = next(f for f in facts if f.concept == "Revenues" and f.fp == "Q1")

    assert annual_fact.is_annual is True
    assert annual_fact.is_quarterly is False

    assert quarterly_fact.is_annual is False
    assert quarterly_fact.is_quarterly is True


def test_duration_days_calculation(sample_company_facts):
    facts = normalize_facts(sample_company_facts)
    annual_fact = next(f for f in facts if f.concept == "Revenues" and f.fp == "FY")
    # 2022-06-01 to 2023-05-31 is 364 days
    assert annual_fact.duration_days == 364

    # Instantaneous fact (shares outstanding) has no start
    instant_fact = next(f for f in facts if f.concept == "EntityCommonStockSharesOutstanding")
    assert instant_fact.duration_days is None


def test_date_parsing_helpers(sample_company_facts):
    facts = normalize_facts(sample_company_facts)
    fact = facts[0]
    assert fact.end_date is not None
    assert fact.filed_date is not None


# ---------------------------------------------------------
# Test Edge Cases
# ---------------------------------------------------------

def test_empty_company_facts():
    empty_cf = CompanyFacts(
        cik="0000003521",
        entity_name="CIK 0000003521",
        facts={},
        file_path=Path("Data/CIK0000003521.json")
    )
    facts = normalize_facts(empty_cf)
    assert facts == []


def test_none_and_malformed_values():
    cf = CompanyFacts(
        cik="0000009999",
        entity_name="Test Company",
        facts={
            "us-gaap": {
                "MalformedConcept": {
                    "units": {
                        "USD": [
                            {"val": "not_a_number", "fy": "invalid_year"},
                            {"val": None, "fy": None}
                        ]
                    }
                }
            }
        },
        file_path=Path("dummy.json")
    )
    facts = normalize_facts(cf)
    assert len(facts) == 2
    assert facts[0].value is None
    assert facts[0].fy is None
    assert facts[1].value is None
    assert facts[1].fy is None


# ---------------------------------------------------------
# Test Real Dataset Integration
# ---------------------------------------------------------

def test_real_dataset_normalization():
    # Load AMD facts (CIK 0000002488)
    cf = load_company_by_cik(2488)
    # Normalize with specific concept filter to keep test fast
    facts = normalize_facts(cf, taxonomies=["us-gaap"], concepts=["Revenues"])
    assert len(facts) > 0
    sample = facts[0]
    assert sample.company == "ADVANCED MICRO DEVICES INC"
    assert sample.cik == "0000002488"
    assert sample.taxonomy == "us-gaap"
    assert sample.concept == "Revenues"
    assert sample.unit == "USD"
    assert sample.value is not None
