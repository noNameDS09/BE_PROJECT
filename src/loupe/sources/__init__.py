"""Source adapters: EDGAR, XBRL and prices for the US corpus.

Each adapter returns the common shapes in `loupe.core.schemas`. `sources/india/`
arrives in P6 and will honour the same contract.
"""

from loupe.sources import us
from loupe.sources.identity import (
    UniverseError,
    candidate_tickers,
    resolve_universe,
    to_companies,
)

__all__ = [
    "UniverseError",
    "candidate_tickers",
    "resolve_universe",
    "to_companies",
    "us",
]
