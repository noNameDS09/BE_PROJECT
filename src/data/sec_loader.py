"""
SEC Company Facts Data Loader.

Provides on-demand, memory-efficient loading of SEC EDGAR Company Facts JSON files
with robust CIK and entityName resolution.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class SECDataError(Exception):
    """Base exception for SEC data loader errors."""
    pass


class CompanyNotFoundError(SECDataError):
    """Raised when a company cannot be found by CIK, name, or filename."""
    pass


class MalformedSECFileError(SECDataError):
    """Raised when an SEC JSON file is corrupted or contains invalid JSON."""
    pass


def normalize_cik(cik: Union[int, str]) -> str:
    """
    Normalizes a CIK value to a standard 10-digit zero-padded string.

    Examples:
        1750 -> "0000001750"
        "1750" -> "0000001750"
        "CIK0000001750" -> "0000001750"
        "0000001750.json" -> "0000001750"
    """
    if isinstance(cik, int):
        return f"{cik:010d}"

    cleaned = str(cik).strip()
    # Strip any leading 'CIK' prefix (case-insensitive)
    if cleaned.upper().startswith("CIK"):
        cleaned = cleaned[3:]
    # Strip any trailing '.json' suffix
    if cleaned.lower().endswith(".json"):
        cleaned = cleaned[:-5]

    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        raise ValueError(f"Invalid CIK specification: '{cik}' contains no digits.")

    return f"{int(digits):010d}"


@dataclass
class CompanyFacts:
    """
    Container representing loaded SEC Company Facts for a single company.
    """
    cik: str
    entity_name: str
    facts: Dict[str, Any]
    file_path: Path

    @property
    def namespaces(self) -> List[str]:
        """List of available XBRL namespaces/taxonomies (e.g. ['us-gaap', 'dei'])."""
        return list(self.facts.keys())

    @property
    def taxonomies(self) -> List[str]:
        """Alias for namespaces."""
        return self.namespaces

    def get_concepts(self, namespace: str = "us-gaap") -> List[str]:
        """Returns all concepts available under a specific namespace."""
        tax_data = self.facts.get(namespace, {})
        return list(tax_data.keys())

    def __repr__(self) -> str:
        return (
            f"CompanyFacts(cik='{self.cik}', entity_name='{self.entity_name}', "
            f"namespaces={self.namespaces}, file='{self.file_path.name}')"
        )


class SECDataLoader:
    """
    Loader for SEC EDGAR Company Facts files.
    Reads file metadata lazily without loading all facts into memory at once.
    """

    def __init__(
        self,
        data_dir: Union[str, Path] = "Data",
        mapping_file: Optional[Union[str, Path]] = "file_to_company.json"
    ):
        self.data_dir = Path(data_dir)
        self.mapping_file = Path(mapping_file) if mapping_file else None
        self._filename_to_company: Optional[Dict[str, str]] = None
        self._cik_to_filename: Optional[Dict[str, str]] = None

    def _ensure_index(self) -> None:
        """Lazily loads or builds index mapping filename, CIK, and company names."""
        if self._filename_to_company is not None and self._cik_to_filename is not None:
            return

        self._filename_to_company = {}
        self._cik_to_filename = {}

        # 1. Try to load from pre-built mapping file if available
        if self.mapping_file and self.mapping_file.exists():
            try:
                with open(self.mapping_file, "r", encoding="utf-8") as f:
                    self._filename_to_company = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load mapping file '{self.mapping_file}': {e}. Falling back to directory scan.")

        # 2. Reconcile with actual files on disk
        if self.data_dir.exists() and self.data_dir.is_dir():
            for f in self.data_dir.glob("*.json"):
                filename = f.name
                try:
                    norm_cik = normalize_cik(filename)
                    self._cik_to_filename[norm_cik] = filename
                except ValueError:
                    continue

                if filename not in self._filename_to_company:
                    self._filename_to_company[filename] = "Unknown"
        else:
            logger.warning(f"Data directory '{self.data_dir}' does not exist.")

    def list_available_companies(self) -> List[Dict[str, str]]:
        """
        Lists metadata for all companies available in the data directory.
        Does NOT load large fact dictionaries into memory.

        Returns:
            List of dicts: [{'cik': '0000001750', 'filename': 'CIK0000001750.json', 'entity_name': 'AAR CORP.'}, ...]
        """
        self._ensure_index()
        assert self._cik_to_filename is not None
        assert self._filename_to_company is not None

        result = []
        for norm_cik in sorted(self._cik_to_filename.keys()):
            fname = self._cik_to_filename[norm_cik]
            name = self._filename_to_company.get(fname, "Unknown")
            result.append({
                "cik": norm_cik,
                "filename": fname,
                "entity_name": name
            })
        return result

    def load_company_facts(self, file_path: Union[str, Path]) -> CompanyFacts:
        """
        Loads and parses a single SEC Company Facts JSON file.

        :param file_path: Path to the JSON file.
        :return: CompanyFacts object.
        :raises CompanyNotFoundError: If the file does not exist.
        :raises MalformedSECFileError: If the JSON is invalid or corrupted.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise CompanyNotFoundError(f"SEC fact file not found at: '{path}'")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    raise MalformedSECFileError(f"SEC file '{path.name}' is empty.")
                raw_data = json.loads(content)
        except json.JSONDecodeError as e:
            raise MalformedSECFileError(f"Failed to parse JSON in '{path.name}': {e}") from e
        except Exception as e:
            if isinstance(e, MalformedSECFileError):
                raise
            raise SECDataError(f"Unexpected error reading '{path.name}': {e}") from e

        if not isinstance(raw_data, dict):
            raise MalformedSECFileError(f"Root structure of '{path.name}' must be a JSON object, got {type(raw_data).__name__}")

        # Extract CIK
        raw_cik = raw_data.get("cik")
        if raw_cik is not None and str(raw_cik).strip():
            try:
                norm_cik = normalize_cik(raw_cik)
            except ValueError:
                norm_cik = normalize_cik(path.name)
        else:
            try:
                norm_cik = normalize_cik(path.name)
            except ValueError:
                norm_cik = "0000000000"

        # Extract entityName
        entity_name = raw_data.get("entityName")
        if not entity_name or not str(entity_name).strip():
            self._ensure_index()
            assert self._filename_to_company is not None
            lookup_name = self._filename_to_company.get(path.name)
            if lookup_name and lookup_name != "Unknown":
                entity_name = lookup_name
            else:
                entity_name = f"CIK {norm_cik}"

        facts = raw_data.get("facts")
        if not isinstance(facts, dict):
            facts = {}

        return CompanyFacts(
            cik=norm_cik,
            entity_name=str(entity_name).strip(),
            facts=facts,
            file_path=path
        )

    def load_company_by_cik(self, cik: Union[int, str]) -> CompanyFacts:
        """
        Loads facts for a company given its CIK.

        :param cik: CIK as int, string, or filename (e.g. 1750, "0000001750", "CIK0000001750").
        :return: CompanyFacts object.
        :raises CompanyNotFoundError: If no file exists for the given CIK.
        """
        self._ensure_index()
        assert self._cik_to_filename is not None

        try:
            norm_cik = normalize_cik(cik)
        except ValueError as e:
            raise CompanyNotFoundError(str(e)) from e

        filename = self._cik_to_filename.get(norm_cik)
        if not filename:
            # Fallback direct check in data_dir
            potential_file = self.data_dir / f"CIK{norm_cik}.json"
            if potential_file.exists():
                filename = potential_file.name
            else:
                raise CompanyNotFoundError(f"No SEC facts file found for CIK: '{cik}' (normalized: '{norm_cik}')")

        target_path = self.data_dir / filename
        return self.load_company_facts(target_path)

    def load_company_by_name(self, name: str, exact: bool = False) -> CompanyFacts:
        """
        Searches for a company by name and loads its facts.

        :param name: Company name or search substring (e.g. "Abbott", "AMD", "AAR CORP.").
        :param exact: If True, requires exact case-sensitive match; otherwise case-insensitive substring search.
        :return: CompanyFacts object.
        :raises CompanyNotFoundError: If no company matches the name.
        """
        self._ensure_index()
        assert self._filename_to_company is not None

        query = name.strip()
        if not query:
            raise ValueError("Company name query cannot be empty.")

        matched_filename: Optional[str] = None

        if exact:
            for fname, cname in self._filename_to_company.items():
                if cname == query:
                    matched_filename = fname
                    break
        else:
            query_lower = query.lower()
            # 1. Exact match case-insensitive
            for fname, cname in self._filename_to_company.items():
                if cname.lower() == query_lower:
                    matched_filename = fname
                    break

            # 2. Substring match
            if not matched_filename:
                candidates = []
                for fname, cname in self._filename_to_company.items():
                    if query_lower in cname.lower() and cname.lower() != "unknown":
                        candidates.append((fname, cname))
                if candidates:
                    # Pick shortest or closest match
                    candidates.sort(key=lambda item: len(item[1]))
                    matched_filename = candidates[0][0]

        if not matched_filename:
            raise CompanyNotFoundError(f"No company matching name '{name}' found in registry.")

        target_path = self.data_dir / matched_filename
        return self.load_company_facts(target_path)

    def load_multiple_companies(
        self,
        identifiers: List[Union[int, str]],
        ignore_missing: bool = False
    ) -> List[CompanyFacts]:
        """
        Loads multiple companies by list of CIKs, filenames, or company names.

        :param identifiers: List of CIKs, filenames, or names.
        :param ignore_missing: If True, skips identifiers that fail to load without raising an exception.
        :return: List of CompanyFacts objects.
        """
        results: List[CompanyFacts] = []
        for item in identifiers:
            try:
                # Try by CIK first
                try:
                    norm_cik = normalize_cik(item)
                    cf = self.load_company_by_cik(norm_cik)
                    results.append(cf)
                    continue
                except (ValueError, CompanyNotFoundError):
                    pass

                # Try by filename
                if str(item).endswith(".json"):
                    cf = self.load_company_facts(self.data_dir / str(item))
                    results.append(cf)
                    continue

                # Try by company name
                cf = self.load_company_by_name(str(item))
                results.append(cf)
            except Exception as e:
                if ignore_missing:
                    logger.warning(f"Skipping '{item}': {e}")
                    continue
                raise
        return results


# Module-level default instance and convenience functions
_DEFAULT_LOADER: Optional[SECDataLoader] = None


def get_default_loader() -> SECDataLoader:
    global _DEFAULT_LOADER
    if _DEFAULT_LOADER is None:
        _DEFAULT_LOADER = SECDataLoader()
    return _DEFAULT_LOADER


def load_company_facts(file_path: Union[str, Path]) -> CompanyFacts:
    """Convenience function to load facts from a specific file path."""
    return get_default_loader().load_company_facts(file_path)


def load_company_by_cik(cik: Union[int, str]) -> CompanyFacts:
    """Convenience function to load facts by CIK."""
    return get_default_loader().load_company_by_cik(cik)


def load_company_by_name(name: str, exact: bool = False) -> CompanyFacts:
    """Convenience function to load facts by company name."""
    return get_default_loader().load_company_by_name(name, exact=exact)


def list_available_companies() -> List[Dict[str, str]]:
    """Convenience function to list all companies available in SEC data."""
    return get_default_loader().list_available_companies()
