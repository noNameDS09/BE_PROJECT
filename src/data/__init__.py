"""
Data loading, normalization, and registry modules for SEC Company Facts.
"""

from src.data.sec_loader import (
    CompanyFacts,
    SECDataLoader,
    load_company_facts,
    load_company_by_cik,
    load_company_by_name,
    list_available_companies,
    normalize_cik,
    SECDataError,
    CompanyNotFoundError,
    MalformedSECFileError,
)

from src.data.financial_normalizer import (
    NormalizedFact,
    FinancialFactNormalizer,
    normalize_facts,
    get_default_normalizer,
)

from src.data.company_registry import (
    CompanyMetadata,
    CompanyRegistry,
    get_registry,
    list_companies,
    get_company,
    get_company_by_cik as registry_get_by_cik,
    search_company,
)

__all__ = [
    "CompanyFacts",
    "SECDataLoader",
    "load_company_facts",
    "load_company_by_cik",
    "load_company_by_name",
    "list_available_companies",
    "normalize_cik",
    "SECDataError",
    "CompanyNotFoundError",
    "MalformedSECFileError",
    "NormalizedFact",
    "FinancialFactNormalizer",
    "normalize_facts",
    "get_default_normalizer",
    "CompanyMetadata",
    "CompanyRegistry",
    "get_registry",
    "list_companies",
    "get_company",
    "registry_get_by_cik",
    "search_company",
]
