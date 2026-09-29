"""
Stream A: Data & Ingestion
- NSE/BSE announcement fetcher (polite, cached)
- PDF text extraction with page numbers (PyMuPDF)
- XBRL download and parse
"""

from .edgar import EdgarSource
from .nse import NseSource
from .parser import FilingParser
from .models import Document, FilingMetadata

__all__ = [
    "EdgarSource",
    "NseSource",
    "FilingParser",
    "Document",
    "FilingMetadata",
]