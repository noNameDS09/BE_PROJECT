"""
Stream B: Taxonomy & Extraction
- LODR event taxonomy (47 event types, 7 dimensions)
- Extractor with verbatim quote validation
- Second-pass quality scorer (1-5)
- Gold-set annotation guide
"""

from .taxonomy import Taxonomy, EventType, load_taxonomy
from .extractor import EventExtractor
from .scorer import QualityScorer
from .models import Event, Quote, ExtractionResult

__all__ = [
    "Taxonomy",
    "EventType",
    "load_taxonomy",
    "EventExtractor",
    "QualityScorer",
    "Event",
    "Quote",
    "ExtractionResult",
]