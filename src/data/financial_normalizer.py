"""
Financial Fact Normalization Module.

Converts raw, nested SEC XBRL Company Facts into standardized, typed internal
representations while preserving complete SEC provenance and metadata.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterator, List, Optional, Set, Union

from src.data.sec_loader import CompanyFacts

logger = logging.getLogger(__name__)


@dataclass
class NormalizedFact:
    """
    Standardized internal representation of a single SEC financial fact.
    Preserves raw SEC metadata for auditability, lineage, and explainability.
    """
    company: str
    cik: str
    taxonomy: str
    concept: str
    metric: str
    unit: str
    value: Optional[Union[int, float]]
    start: Optional[str] = None
    end: Optional[str] = None
    fy: Optional[int] = None
    fp: Optional[str] = None
    form: Optional[str] = None
    filed: Optional[str] = None
    frame: Optional[str] = None
    accn: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Returns the fact as a clean Python dictionary."""
        return asdict(self)

    @property
    def is_annual(self) -> bool:
        """Indicates if the fact corresponds to an annual reporting period."""
        if self.fp and self.fp.upper() == "FY":
            return True
        if self.form and self.form.upper() in ("10-K", "10-K/A", "20-F", "40-F"):
            # If fp is None or FY on a 10-K
            return self.fp is None or self.fp.upper() == "FY"
        return False

    @property
    def is_quarterly(self) -> bool:
        """Indicates if the fact corresponds to a quarterly reporting period."""
        if self.fp and self.fp.upper() in ("Q1", "Q2", "Q3", "Q4"):
            return True
        if self.form and self.form.upper() in ("10-Q", "10-Q/A"):
            return True
        return False

    @property
    def duration_days(self) -> Optional[int]:
        """Returns the duration of the reporting period in days if start and end exist."""
        if not self.start or not self.end:
            return None
        try:
            d_start = datetime.strptime(self.start, "%Y-%m-%d").date()
            d_end = datetime.strptime(self.end, "%Y-%m-%d").date()
            return (d_end - d_start).days
        except (ValueError, TypeError):
            return None

    @property
    def end_date(self) -> Optional[date]:
        """Parses the end date string into a datetime.date object."""
        if not self.end:
            return None
        try:
            return datetime.strptime(self.end, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    @property
    def filed_date(self) -> Optional[date]:
        """Parses the filed date string into a datetime.date object."""
        if not self.filed:
            return None
        try:
            return datetime.strptime(self.filed, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None


class FinancialFactNormalizer:
    """
    Normalizes raw SEC XBRL Company Facts into structured NormalizedFact instances.
    Supports taxonomy filtering, concept variation resolution, and metric mapping.
    """

    def __init__(
        self,
        concept_alias_map: Optional[Dict[str, str]] = None,
        default_taxonomies: Optional[List[str]] = None
    ):
        """
        :param concept_alias_map: Optional mapping from XBRL concept name to logical metric name
                                  e.g. {'Revenues': 'Revenue', 'SalesRevenueNet': 'Revenue'}.
        :param default_taxonomies: List of taxonomies to normalize by default (e.g. ['us-gaap', 'dei']).
        """
        self.concept_alias_map = concept_alias_map or {}
        self.default_taxonomies = default_taxonomies

    def iter_normalized_facts(
        self,
        company_facts: CompanyFacts,
        taxonomies: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None
    ) -> Iterator[NormalizedFact]:
        """
        Memory-efficient generator yielding NormalizedFact objects from CompanyFacts.

        :param company_facts: The loaded CompanyFacts object.
        :param taxonomies: Optional filter of namespaces to include (e.g. ['us-gaap']).
        :param concepts: Optional filter of specific XBRL concepts to include.
        :yield: NormalizedFact objects.
        """
        if not company_facts or not company_facts.facts:
            return

        target_taxonomies = taxonomies or self.default_taxonomies or list(company_facts.facts.keys())
        target_concepts_set: Optional[Set[str]] = set(concepts) if concepts else None

        company_name = company_facts.entity_name
        cik = company_facts.cik

        for tax in target_taxonomies:
            tax_dict = company_facts.facts.get(tax)
            if not isinstance(tax_dict, dict):
                continue

            for concept_name, concept_data in tax_dict.items():
                if target_concepts_set and concept_name not in target_concepts_set:
                    continue

                if not isinstance(concept_data, dict):
                    continue

                label = concept_data.get("label")
                description = concept_data.get("description")
                units_dict = concept_data.get("units")

                if not isinstance(units_dict, dict):
                    continue

                # Determine logical metric name (default to concept name if unmapped)
                metric_name = self.concept_alias_map.get(concept_name, concept_name)

                for unit_str, items in units_dict.items():
                    if not isinstance(items, list):
                        continue

                    for item in items:
                        if not isinstance(item, dict):
                            continue

                        # Parse and sanitize numerical value
                        raw_val = item.get("val")
                        parsed_val: Optional[Union[int, float]] = None
                        if raw_val is not None:
                            try:
                                parsed_val = int(raw_val) if isinstance(raw_val, int) else float(raw_val)
                            except (ValueError, TypeError):
                                parsed_val = None

                        # Parse fiscal year
                        raw_fy = item.get("fy")
                        parsed_fy: Optional[int] = None
                        if raw_fy is not None:
                            try:
                                parsed_fy = int(raw_fy)
                            except (ValueError, TypeError):
                                parsed_fy = None

                        yield NormalizedFact(
                            company=company_name,
                            cik=cik,
                            taxonomy=tax,
                            concept=concept_name,
                            metric=metric_name,
                            unit=unit_str,
                            value=parsed_val,
                            start=item.get("start"),
                            end=item.get("end"),
                            fy=parsed_fy,
                            fp=str(item.get("fp")).strip() if item.get("fp") is not None else None,
                            form=str(item.get("form")).strip() if item.get("form") is not None else None,
                            filed=item.get("filed"),
                            frame=item.get("frame"),
                            accn=item.get("accn"),
                            label=label,
                            description=description
                        )

    def normalize_company_facts(
        self,
        company_facts: CompanyFacts,
        taxonomies: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None
    ) -> List[NormalizedFact]:
        """
        Normalizes all requested facts of a company into a list of NormalizedFact objects.

        :param company_facts: The loaded CompanyFacts object.
        :param taxonomies: Optional list of namespaces (e.g. ['us-gaap', 'dei']).
        :param concepts: Optional list of specific concepts to extract.
        :return: List of NormalizedFact instances.
        """
        return list(self.iter_normalized_facts(company_facts, taxonomies=taxonomies, concepts=concepts))


# Module-level convenience functions
_DEFAULT_NORMALIZER: Optional[FinancialFactNormalizer] = None


def get_default_normalizer() -> FinancialFactNormalizer:
    global _DEFAULT_NORMALIZER
    if _DEFAULT_NORMALIZER is None:
        _DEFAULT_NORMALIZER = FinancialFactNormalizer()
    return _DEFAULT_NORMALIZER


def normalize_facts(
    company_facts: CompanyFacts,
    taxonomies: Optional[List[str]] = None,
    concepts: Optional[List[str]] = None
) -> List[NormalizedFact]:
    """
    Convenience function to normalize facts from a CompanyFacts container.
    """
    return get_default_normalizer().normalize_company_facts(
        company_facts=company_facts,
        taxonomies=taxonomies,
        concepts=concepts
    )
