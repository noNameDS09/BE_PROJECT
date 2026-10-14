"""Local persistence: DuckDB for documents, chunks, facts, prices and results."""

from loupe.store.db import connect, coverage_report, iter_chunks, record_coverage

__all__ = ["connect", "coverage_report", "iter_chunks", "record_coverage"]
