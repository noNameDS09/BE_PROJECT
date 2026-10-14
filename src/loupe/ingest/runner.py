"""Ingest: EDGAR filings and XBRL facts into the local store.

One company at a time, resumable, and honest about partial failure. A company
whose filings download but whose XBRL parse fails still gets its chunks; the
coverage report records the shortfall instead of hiding it.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from loupe.core.schemas import CompanyInfo
from loupe.ingest.chunk import chunk_document
from loupe.sources import us
from loupe.store import db

logger = logging.getLogger(__name__)


@dataclass
class IngestStats:
    ticker: str
    filings: int = 0
    sections: int = 0
    chunks: int = 0
    facts: int = 0
    prices: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "IngestStats") -> "IngestStats":
        return IngestStats(
            ticker=self.ticker,
            filings=self.filings + other.filings,
            sections=self.sections + other.sections,
            chunks=self.chunks + other.chunks,
            facts=self.facts + other.facts,
            prices=self.prices + other.prices,
            errors=[*self.errors, *other.errors],
        )


def ingest_company(
    company: CompanyInfo,
    *,
    start: str = "2023-01-01",
    end: str = "2025-12-31",
    forms: tuple[str, ...] = us.CORPUS_FORMS,
    with_facts: bool = True,
    with_prices: bool = True,
    max_filings: int | None = None,
    verbose: bool = False,
) -> IngestStats:
    """Fetch and store one company's corpus. Network calls happen here only."""
    stats = IngestStats(ticker=company.ticker)

    filings = us.list_filings(company, forms=forms, start=start, end=end)
    if max_filings is not None:
        filings = filings[-max_filings:]
    stats.filings = len(filings)

    conn = db.connect(_db_path())
    try:
        for filing in filings:
            try:
                counts = _ingest_filing(company, filing, conn)
                stats.sections += counts[0]
                stats.chunks += counts[1]
            except Exception as exc:  # pragma: no cover - network dependent
                message = f"{filing['form']} {filing['accession']}: {type(exc).__name__}: {exc}"
                logger.warning("%s: %s", company.ticker, message, exc_info=verbose)
                stats.errors.append(message)

        if with_facts:
            try:
                db.save_facts(conn, us.extract_facts(company, start=start, end=end))
                # Count what landed, not what we tried: the same fact id can
                # arrive from several filings, and a coverage number that
                # over-reports is worse than no number.
                stats.facts = db.count_rows(conn, "facts", company.ticker)
            except Exception as exc:  # pragma: no cover - network dependent
                stats.errors.append(f"facts: {type(exc).__name__}: {exc}")

        if with_prices:
            try:
                stats.prices = db.save_prices(
                    conn, company.ticker, us.fetch_daily_prices(company.ticker, start, end)
                )
            except us.PriceUnavailable as exc:
                # Prices are not needed for P1's coverage target, and losing
                # the filing text over a blocked price site would be worse.
                logger.info("%s: prices unavailable (%s)", company.ticker, exc)
                stats.errors.append(f"prices: {exc}")
            except Exception as exc:  # pragma: no cover - network dependent
                stats.errors.append(f"prices: {type(exc).__name__}: {exc}")

        db.record_coverage(conn, company.ticker)
    finally:
        conn.close()
    return stats


def _ingest_filing(company: CompanyInfo, filing: dict, conn) -> tuple[int, int]:
    """One filing: sections -> chunks -> store. Returns (sections, chunks)."""
    import edgar

    accession = filing["accession"]
    doc_id = _doc_id(company, accession)
    if conn.execute("SELECT 1 FROM documents WHERE doc_id = ?", [doc_id]).fetchone():
        return 0, 0  # already ingested; re-running must not duplicate work

    # edgartools 5 has no Company.get_filing; accession lookup is module-level.
    handle = edgar.get_by_accession_number(accession)
    if handle is None:
        raise FileNotFoundError(accession)

    filing_obj = handle.obj()
    sections, texts, full_text = us.extract_sections(doc_id, filing_obj)
    if not sections:
        return 0, 0

    document = us.build_document(company, filing, sections, full_text)
    keyed = {s.section_id: texts[s.section_id] for s in sections if s.section_id in texts}
    chunks = chunk_document(document, sections, keyed, company_id=company.ticker)

    db.save_documents(conn, [document])
    db.save_sections(conn, sections, keyed)
    db.save_chunks(conn, chunks)
    return len(sections), len(chunks)


def _doc_id(company: CompanyInfo, accession: str) -> str:
    import hashlib

    return hashlib.sha256(f"{company.cik}|{accession}".encode()).hexdigest()[:16]


_DB: Path | None = None


def configure_db(path: Path) -> None:
    global _DB
    _DB = path


def _db_path() -> Path:
    if _DB is None:
        from loupe.core.settings import get_settings

        return get_settings().duckdb_path
    return _DB


def ingest_universe(
    companies: list[CompanyInfo],
    *,
    progress=None,
    **kwargs,
) -> list[IngestStats]:
    out: list[IngestStats] = []
    for company in companies:
        if progress:
            progress(company)
        out.append(ingest_company(company, **kwargs))
    return out
