"""
Tests for SEC Data Loader (Phase 1).
"""

import json
from pathlib import Path
import pytest

from src.data.sec_loader import (
    CompanyFacts,
    SECDataLoader,
    normalize_cik,
    load_company_facts,
    load_company_by_cik,
    load_company_by_name,
    list_available_companies,
    CompanyNotFoundError,
    MalformedSECFileError,
)


@pytest.fixture
def loader():
    """Returns a SECDataLoader pointing to the actual workspace Data directory."""
    return SECDataLoader(data_dir="Data", mapping_file="file_to_company.json")


@pytest.fixture
def temp_sec_env(tmp_path):
    """Creates a temporary test environment with sample valid and invalid SEC files."""
    data_dir = tmp_path / "Data"
    data_dir.mkdir()

    # 1. Valid company file (CIK 0000001750)
    valid_data = {
        "cik": 1750,
        "entityName": "AAR CORP.",
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "label": "Shares Outstanding",
                    "units": {"shares": [{"val": 39000000, "fy": 2020, "fp": "FY"}]}
                }
            },
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "units": {"USD": [{"val": 2000000000, "fy": 2020, "fp": "FY"}]}
                }
            }
        }
    }
    with open(data_dir / "CIK0000001750.json", "w", encoding="utf-8") as f:
        json.dump(valid_data, f)

    # 2. File with missing entityName
    no_entity_data = {
        "cik": "0000002110",
        "entityName": "",
        "facts": {}
    }
    with open(data_dir / "CIK0000002110.json", "w", encoding="utf-8") as f:
        json.dump(no_entity_data, f)

    # 3. Empty JSON dictionary file
    with open(data_dir / "CIK0000003521.json", "w", encoding="utf-8") as f:
        f.write("{}")

    # 4. Corrupted / Malformed JSON file
    with open(data_dir / "CIK0000009999.json", "w", encoding="utf-8") as f:
        f.write("{\"cik\": 9999, entityName: INVALID_JSON_NO_QUOTES")

    # 5. Mapping file
    mapping_path = tmp_path / "file_to_company.json"
    mapping_data = {
        "CIK0000001750.json": "AAR CORP.",
        "CIK0000002110.json": "Unknown",
        "CIK0000003521.json": "Unknown"
    }
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping_data, f)

    return SECDataLoader(data_dir=data_dir, mapping_file=mapping_path)


# ---------------------------------------------------------
# Test CIK Normalization
# ---------------------------------------------------------

def test_normalize_cik():
    assert normalize_cik(1750) == "0000001750"
    assert normalize_cik("1750") == "0000001750"
    assert normalize_cik("0000001750") == "0000001750"
    assert normalize_cik("CIK0000001750") == "0000001750"
    assert normalize_cik("CIK0000001750.json") == "0000001750"
    assert normalize_cik("  cik1800  ") == "0000001800"

    with pytest.raises(ValueError):
        normalize_cik("invalid_no_digits")


# ---------------------------------------------------------
# Test Valid Company File Loading
# ---------------------------------------------------------

def test_load_valid_company_file(temp_sec_env):
    facts = temp_sec_env.load_company_by_cik(1750)
    assert isinstance(facts, CompanyFacts)
    assert facts.cik == "0000001750"
    assert facts.entity_name == "AAR CORP."
    assert "us-gaap" in facts.namespaces
    assert "dei" in facts.namespaces
    assert "Revenues" in facts.get_concepts("us-gaap")


# ---------------------------------------------------------
# Test Real Dataset Integration
# ---------------------------------------------------------

def test_real_dataset_load_by_cik(loader):
    facts = loader.load_company_by_cik(1800)
    assert facts.cik == "0000001800"
    assert facts.entity_name == "ABBOTT LABORATORIES"
    assert "us-gaap" in facts.namespaces


def test_real_dataset_load_by_name(loader):
    # Substring / case-insensitive search
    facts = loader.load_company_by_name("advanced micro devices")
    assert facts.cik == "0000002488"
    assert "ADVANCED MICRO DEVICES" in facts.entity_name.upper()


def test_list_available_companies(loader):
    companies = loader.list_available_companies()
    assert len(companies) == 50
    first = companies[0]
    assert "cik" in first
    assert "filename" in first
    assert "entity_name" in first


# ---------------------------------------------------------
# Test Edge Cases & Error Handling
# ---------------------------------------------------------

def test_load_nonexistent_file(temp_sec_env):
    with pytest.raises(CompanyNotFoundError):
        temp_sec_env.load_company_facts("Data/non_existent_file.json")


def test_load_missing_company_by_cik(temp_sec_env):
    with pytest.raises(CompanyNotFoundError):
        temp_sec_env.load_company_by_cik("9999999999")


def test_load_missing_company_by_name(temp_sec_env):
    with pytest.raises(CompanyNotFoundError):
        temp_sec_env.load_company_by_name("NonExistentCompanyXYZ")


def test_missing_entity_name_fallback(temp_sec_env):
    facts = temp_sec_env.load_company_by_cik(2110)
    assert facts.cik == "0000002110"
    # Should fall back cleanly without error
    assert facts.entity_name is not None
    assert len(facts.entity_name) > 0


def test_empty_json_file_handling(temp_sec_env):
    facts = temp_sec_env.load_company_by_cik(3521)
    assert facts.cik == "0000003521"
    assert facts.facts == {}
    assert facts.namespaces == []


def test_malformed_json_handling(temp_sec_env):
    with pytest.raises(MalformedSECFileError):
        temp_sec_env.load_company_facts(temp_sec_env.data_dir / "CIK0000009999.json")


def test_load_multiple_companies(temp_sec_env):
    results = temp_sec_env.load_multiple_companies([1750, "CIK0000002110.json"])
    assert len(results) == 2
    assert results[0].cik == "0000001750"
    assert results[1].cik == "0000002110"


def test_load_multiple_companies_ignore_missing(temp_sec_env):
    results = temp_sec_env.load_multiple_companies([1750, 9999999], ignore_missing=True)
    assert len(results) == 1
    assert results[0].cik == "0000001750"
