"""
Company Registry Module.

Provides bidirectional resolution and fuzzy/structured lookup between
company names, CIK identifiers, and SEC JSON filenames.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.data.sec_loader import (
    CompanyNotFoundError,
    normalize_cik,
)

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Replaces non-breaking spaces and collapses whitespace."""
    if not text:
        return ""
    cleaned = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class CompanyMetadata:
    """
    Metadata representation for a registered company in the SEC dataset.
    """
    cik: str
    entity_name: str
    filename: str
    file_path: Path
    file_size_bytes: int = 0
    has_facts: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Converts company metadata to dictionary."""
        data = asdict(self)
        data["file_path"] = str(self.file_path)
        return data

    def __repr__(self) -> str:
        return f"CompanyMetadata(cik='{self.cik}', name='{self.entity_name}', file='{self.filename}')"


class CompanyRegistry:
    """
    Bidirectional index and search engine for SEC companies.
    Loads and reconciles file_to_company.json with the SEC Data/ directory.
    """

    def __init__(
        self,
        data_dir: Union[str, Path] = "Data",
        mapping_file: Optional[Union[str, Path]] = "file_to_company.json"
    ):
        self.data_dir = Path(data_dir)
        self.mapping_file = Path(mapping_file) if mapping_file else None

        self._by_cik: Dict[str, CompanyMetadata] = {}
        self._by_filename: Dict[str, CompanyMetadata] = {}
        self._companies: List[CompanyMetadata] = []

        self._build_index()

    def _build_index(self) -> None:
        """Constructs in-memory lookup indices from mapping file and disk."""
        self._by_cik.clear()
        self._by_filename.clear()
        self._companies.clear()

        # 1. Load name mappings from JSON if present
        mapping: Dict[str, str] = {}
        if self.mapping_file and self.mapping_file.exists():
            try:
                with open(self.mapping_file, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read mapping file '{self.mapping_file}': {e}")

        # 2. Scan data directory for actual files
        if not self.data_dir.exists() or not self.data_dir.is_dir():
            logger.warning(f"Data directory '{self.data_dir}' does not exist.")
            return

        for path in sorted(self.data_dir.glob("*.json")):
            filename = path.name
            try:
                norm_cik = normalize_cik(filename)
            except ValueError:
                continue

            raw_name = mapping.get(filename, "Unknown")
            name = clean_text(raw_name)
            if not name or name.lower() == "unknown":
                name = f"Unknown (CIK {norm_cik})"

            size_bytes = path.stat().st_size
            has_facts = size_bytes > 50  # 2-byte empty files or 47-byte empty facts have no facts

            metadata = CompanyMetadata(
                cik=norm_cik,
                entity_name=name,
                filename=filename,
                file_path=path,
                file_size_bytes=size_bytes,
                has_facts=has_facts
            )

            self._by_cik[norm_cik] = metadata
            self._by_filename[filename] = metadata
            self._companies.append(metadata)

    def refresh(self) -> None:
        """Reloads indices from disk."""
        self._build_index()

    def count(self) -> int:
        """Returns total number of indexed companies."""
        return len(self._companies)

    def list_companies(self, include_empty: bool = True) -> List[CompanyMetadata]:
        """
        Lists all companies in the registry.

        :param include_empty: If False, filters out companies with empty fact files.
        :return: List of CompanyMetadata objects.
        """
        if include_empty:
            return list(self._companies)
        return [c for c in self._companies if c.has_facts]

    def get_company_by_cik(self, cik: Union[str, int]) -> CompanyMetadata:
        """
        Retrieves company metadata by its CIK.

        :param cik: CIK as int, string, or filename (e.g. 1800, "0000001800").
        :return: CompanyMetadata.
        :raises CompanyNotFoundError: If CIK is not found.
        """
        try:
            norm_cik = normalize_cik(cik)
        except ValueError as e:
            raise CompanyNotFoundError(str(e)) from e

        company = self._by_cik.get(norm_cik)
        if not company:
            raise CompanyNotFoundError(f"Company with CIK '{cik}' (normalized: '{norm_cik}') not found in registry.")
        return company

    def get_company_by_filename(self, filename: str) -> CompanyMetadata:
        """
        Retrieves company metadata given its filename (e.g. 'CIK0000001750.json').

        :param filename: JSON filename.
        :return: CompanyMetadata.
        :raises CompanyNotFoundError: If filename is not in registry.
        """
        fname = filename.strip()
        company = self._by_filename.get(fname)
        if not company:
            # Try by normalized CIK if filename pattern is recognized
            try:
                norm_cik = normalize_cik(fname)
                if norm_cik in self._by_cik:
                    return self._by_cik[norm_cik]
            except ValueError:
                pass
            raise CompanyNotFoundError(f"Filename '{filename}' not found in company registry.")
        return company

    def search_company_by_name(
        self,
        query: str,
        exact: bool = False,
        limit: int = 10
    ) -> List[CompanyMetadata]:
        """
        Searches for companies matching the given name query.

        :param query: Company name or search substring (e.g. "Abbott", "AMD", "Air Products").
        :param exact: If True, requires exact case-insensitive match.
        :param limit: Maximum number of search results to return.
        :return: Ranked list of matching CompanyMetadata objects.
        """
        cleaned_query = clean_text(query).lower()
        if not cleaned_query:
            return []

        # 1. Exact match (case-insensitive)
        exact_matches = [
            c for c in self._companies
            if c.entity_name.lower() == cleaned_query
        ]
        if exact_matches:
            return exact_matches[:limit]

        if exact:
            return []

        # 2. Substring & Token matching
        query_tokens = [tok for tok in re.split(r"\W+", cleaned_query) if tok]
        scored_matches: List[tuple[int, int, CompanyMetadata]] = []

        for comp in self._companies:
            name_lower = comp.entity_name.lower()
            score = 0

            # Substring match
            if cleaned_query in name_lower:
                score += 100
                # Bonus if it starts with the query
                if name_lower.startswith(cleaned_query):
                    score += 50
            else:
                # Token overlap
                matched_tokens = sum(1 for tok in query_tokens if tok in name_lower)
                if matched_tokens > 0:
                    score += (matched_tokens * 20)

            if score > 0:
                # Prefer higher score, then shorter name length for precision
                scored_matches.append((score, len(comp.entity_name), comp))

        # Sort descending by score, ascending by name length
        scored_matches.sort(key=lambda x: (-x[0], x[1]))
        return [item[2] for item in scored_matches[:limit]]

    def get_company(self, query: Union[str, int]) -> CompanyMetadata:
        """
        Universal resolver: resolves by CIK if numeric, or searches by name/filename.

        :param query: Company name, CIK, or filename.
        :return: Best matching CompanyMetadata.
        :raises CompanyNotFoundError: If no matching company is found.
        """
        q_str = str(query).strip()

        # 1. Check if it's a CIK or CIK filename
        if q_str.isdigit() or (q_str.upper().startswith("CIK") and re.search(r"\d+", q_str)):
            try:
                return self.get_company_by_cik(q_str)
            except CompanyNotFoundError:
                pass

        # 2. Check if it's an exact filename
        if q_str in self._by_filename:
            return self._by_filename[q_str]

        # 3. Search by company name
        matches = self.search_company_by_name(q_str, exact=False, limit=1)
        if matches:
            return matches[0]

        raise CompanyNotFoundError(f"Could not resolve company for query: '{query}'")

    def resolve_filename_to_company(self, filename: str) -> str:
        """Resolves a filename to its company entity name."""
        return self.get_company_by_filename(filename).entity_name

    def resolve_company_to_filename(self, name_or_cik: Union[str, int]) -> str:
        """Resolves a company name or CIK to its SEC JSON filename."""
        return self.get_company(name_or_cik).filename


# Singleton registry instance and convenience functions
_REGISTRY_INSTANCE: Optional[CompanyRegistry] = None


def get_registry(
    data_dir: Union[str, Path] = "Data",
    mapping_file: Optional[Union[str, Path]] = "file_to_company.json"
) -> CompanyRegistry:
    """Returns the singleton CompanyRegistry instance."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = CompanyRegistry(data_dir=data_dir, mapping_file=mapping_file)
    return _REGISTRY_INSTANCE


def list_companies(include_empty: bool = True) -> List[CompanyMetadata]:
    """Lists all registered companies."""
    return get_registry().list_companies(include_empty=include_empty)


def get_company(query: Union[str, int]) -> CompanyMetadata:
    """Universal resolver for company name, CIK, or filename."""
    return get_registry().get_company(query)


def get_company_by_cik(cik: Union[str, int]) -> CompanyMetadata:
    """Resolves company metadata by CIK."""
    return get_registry().get_company_by_cik(cik)


def search_company(query: str, limit: int = 10) -> List[CompanyMetadata]:
    """Fuzzy/token search for company by name."""
    return get_registry().search_company_by_name(query, limit=limit)
