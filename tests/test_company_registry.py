"""
Tests for Company Registry (Phase 3).
"""

import pytest

from src.data.company_registry import (
    CompanyMetadata,
    CompanyRegistry,
    get_registry,
    get_company,
    get_company_by_cik,
    search_company,
    list_companies,
)
from src.data.sec_loader import CompanyNotFoundError


@pytest.fixture
def registry():
    """Returns a fresh CompanyRegistry instance on the actual workspace."""
    return CompanyRegistry(data_dir="Data", mapping_file="file_to_company.json")


# ---------------------------------------------------------
# Test Listing & Count
# ---------------------------------------------------------

def test_registry_count_and_listing(registry):
    assert registry.count() == 50
    all_companies = registry.list_companies()
    assert len(all_companies) == 50
    assert all(isinstance(c, CompanyMetadata) for c in all_companies)


def test_registry_filter_empty(registry):
    # Should exclude files like CIK0000003521 (2 bytes) or CIK0000002110 (47 bytes)
    non_empty = registry.list_companies(include_empty=False)
    assert len(non_empty) < 50
    assert len(non_empty) >= 40


# ---------------------------------------------------------
# Test Search by CIK
# ---------------------------------------------------------

def test_get_by_cik_integer(registry):
    comp = registry.get_company_by_cik(1800)
    assert comp.cik == "0000001800"
    assert comp.entity_name == "ABBOTT LABORATORIES"
    assert comp.filename == "CIK0000001800.json"


def test_get_by_cik_string_variations(registry):
    assert registry.get_company_by_cik("1800").cik == "0000001800"
    assert registry.get_company_by_cik("0000001800").cik == "0000001800"
    assert registry.get_company_by_cik("CIK0000001800").cik == "0000001800"
    assert registry.get_company_by_cik("CIK0000001800.json").cik == "0000001800"


def test_get_by_cik_not_found(registry):
    with pytest.raises(CompanyNotFoundError):
        registry.get_company_by_cik("9999999999")


# ---------------------------------------------------------
# Test Search by Name
# ---------------------------------------------------------

def test_search_company_by_name_exact(registry):
    matches = registry.search_company_by_name("ABBOTT LABORATORIES", exact=True)
    assert len(matches) == 1
    assert matches[0].cik == "0000001800"


def test_search_company_by_name_substring(registry):
    # Lowercase substring
    matches = registry.search_company_by_name("abbott")
    assert len(matches) >= 1
    assert matches[0].cik == "0000001800"
    assert "ABBOTT" in matches[0].entity_name


def test_search_company_by_tokens(registry):
    # Multi-token partial search
    matches = registry.search_company_by_name("micro devices")
    assert len(matches) >= 1
    assert matches[0].cik == "0000002488"
    assert "ADVANCED MICRO DEVICES" in matches[0].entity_name


def test_search_whitespace_handling(registry):
    # Matson, Inc. has non-breaking whitespace in the original data
    matches = registry.search_company_by_name("Matson")
    assert len(matches) >= 1
    assert matches[0].cik == "0000003453"


def test_search_company_not_found(registry):
    matches = registry.search_company_by_name("TotallyFakeCompany123")
    assert matches == []


# ---------------------------------------------------------
# Test Filename Resolution (Bidirectional)
# ---------------------------------------------------------

def test_resolve_filename_to_company(registry):
    name = registry.resolve_filename_to_company("CIK0000001750.json")
    assert name == "AAR CORP."


def test_resolve_company_to_filename(registry):
    # By name
    fname = registry.resolve_company_to_filename("AAR CORP.")
    assert fname == "CIK0000001750.json"
    # By CIK
    fname_cik = registry.resolve_company_to_filename("0000001800")
    assert fname_cik == "CIK0000001800.json"


def test_get_company_by_filename(registry):
    comp = registry.get_company_by_filename("CIK0000001750.json")
    assert comp.cik == "0000001750"
    assert comp.entity_name == "AAR CORP."


# ---------------------------------------------------------
# Test Universal Resolver & Convenience Functions
# ---------------------------------------------------------

def test_universal_get_company(registry):
    # Via CIK int
    assert registry.get_company(1800).cik == "0000001800"
    # Via CIK str
    assert registry.get_company("0000001800").cik == "0000001800"
    # Via Filename
    assert registry.get_company("CIK0000001800.json").cik == "0000001800"
    # Via partial name
    assert registry.get_company("Abbott").cik == "0000001800"


def test_module_level_convenience_functions():
    comp = get_company("ABBOTT LABORATORIES")
    assert comp.cik == "0000001800"

    comp_cik = get_company_by_cik(2488)
    assert comp_cik.cik == "0000002488"

    companies = list_companies()
    assert len(companies) == 50

    search_res = search_company("AAR")
    assert len(search_res) >= 1
    assert search_res[0].cik == "0000001750"


def test_unknown_company_metadata(registry):
    # CIK 0000003521 has empty data
    comp = registry.get_company_by_cik(3521)
    assert comp.cik == "0000003521"
    assert "Unknown" in comp.entity_name
    assert comp.has_facts is False
