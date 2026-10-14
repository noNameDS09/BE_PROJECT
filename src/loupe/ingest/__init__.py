"""Ingest: turn raw filings into section-aware chunks and store them."""

from loupe.ingest.chunk import chunk_document, dedupe_chunks, split_text
from loupe.ingest.runner import IngestStats, configure_db, ingest_company, ingest_universe

__all__ = [
    "IngestStats",
    "chunk_document",
    "configure_db",
    "dedupe_chunks",
    "ingest_company",
    "ingest_universe",
    "split_text",
]
