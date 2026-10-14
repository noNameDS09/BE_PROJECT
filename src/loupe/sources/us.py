"""US source adapters: EDGAR filings, XBRL facts and daily prices.

Everything here returns the common shapes in `loupe.core.schemas`, so no
downstream stage knows whether a number came from EDGAR, a PDF or India.

edgartools is the stack choice in docs/PLAN.md. Two behaviours of v5 that
shaped this code are recorded in docs/decisions.md:

1. `EntityFilings.__getitem__` raises TypeError on this pyarrow build, so we
   use `.to_pandas()` and treat the frame as read-only.
2. Section offsets are relative to the section's own text, and the section
   text is *not* a byte-exact slice of `document.text()` (whitespace is
   normalised differently). Quotes are therefore verified against the stored
   section text.
"""

import logging
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

from loupe.core.schemas import Chunk, CompanyInfo, Document, Fact, Section

logger = logging.getLogger(__name__)

CORPUS_FORMS = ("10-K", "10-Q", "8-K")
# 8-K items that mark a real risk event (docs/PLAN.md, company selection rule).
RISK_8K_ITEMS = {"1.01", "1.03", "2.01", "2.04", "4.01", "4.02", "5.02"}


class IdentityError(RuntimeError):
    """Raised when EDGAR is asked for data before an identity is set."""


def configure_identity(user_agent: str | None) -> str:
    """Tell edgartools who we are. SEC returns 403 without a contact address."""
    import edgar

    identity = user_agent or "Loupe research project (set SEC_USER_AGENT in .env)"
    edgar.set_identity(identity)
    return identity


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def _parse_dt(value: Any) -> datetime | None:
    parsed = _parse_date(value)
    return datetime.combine(parsed, datetime.min.time()) if parsed else None


def _stable_id(*parts: str) -> str:
    import hashlib

    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def set_cache_dir(path: Path) -> None:
    """Point edgartools' HTTP cache at our data dir so runs are reproducible."""
    import edgar

    edgar.set_cache_directory(str(path))


# --------------------------------------------------------------------------- #
# Filings
# --------------------------------------------------------------------------- #


def list_filings(
    company: CompanyInfo,
    forms: Iterable[str] = CORPUS_FORMS,
    start: str = "2023-01-01",
    end: str = "2025-12-31",
) -> list[dict]:
    """Filing index rows for a company within a window.

    Returns plain dicts, not edgartools objects, so the ingest layer can be
    tested against fixtures with no network.
    """
    import edgar

    filings = edgar.Company(company.ticker).get_filings(
        form=list(forms), filing_date=f"{start}:{end}"
    )
    if filings is None or getattr(filings, "empty", True):
        return []

    frame = filings.to_pandas()
    rows: list[dict] = []
    for record in frame.to_dict("records"):
        rows.append(
            {
                "accession": str(record.get("accession_number") or ""),
                "form": str(record.get("form") or ""),
                "filing_date": _parse_date(record.get("filing_date")),
                "report_date": _parse_date(record.get("reportDate")),
                "primary_document": record.get("primaryDocument"),
                "items": _split_items(record.get("items")),
            }
        )
    rows.sort(key=lambda r: (r["filing_date"] or date.min, r["accession"]))
    return rows


def _split_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def risk_items(filing: dict) -> list[str]:
    return sorted(set(filing.get("items") or []) & RISK_8K_ITEMS)


def build_document(
    company: CompanyInfo, filing: dict, sections: list[Section], text: str
) -> Document:
    return Document(
        doc_id=_stable_id(company.cik, filing["accession"]),
        company_id=company.ticker,
        source="sec_edgar",
        form=filing["form"],
        url=_filing_url(company, filing),
        content_hash=_stable_id(text),
        accession=filing["accession"],
        fiscal_year=filing["report_date"].year if filing["report_date"] else None,
        fiscal_period=_fiscal_period(filing),
        period_end=filing["report_date"],
        filed_at=_parse_dt(filing["filing_date"]),
        sections=sections,
    )


def _fiscal_period(filing: dict) -> str | None:
    if filing["form"] == "10-K":
        return "FY"
    if filing["form"] == "10-Q":
        report = filing["report_date"]
        if report is None:
            return None
        return {3: "Q1", 6: "Q2", 9: "Q3", 12: "Q4"}.get(report.month)
    return None


def _filing_url(company: CompanyInfo, filing: dict) -> str:
    accession = (filing["accession"] or "").replace("-", "")
    primary = filing.get("primary_document") or ""
    return f"https://www.sec.gov/Archives/edgar/data/{int(company.cik)}/{accession}/{primary}"


def extract_sections(doc_id: str, filing_obj: Any) -> tuple[list[Section], dict[str, str], str]:
    """Convert an edgartools filing object into our Section records.

    Returns (sections, section_id -> exact section text, full document text).
    Offsets are section-local and start at 0; see the module docstring for why.

    The text is returned keyed by *our* section_id so the caller never has to
    re-derive the mapping between edgartools' keys and our stable ids.
    """
    sections: list[Section] = []
    texts: dict[str, str] = {}
    container = getattr(filing_obj, "sections", None)
    if container is None:
        return sections, texts, _document_text(filing_obj)

    for key, section in container.items():
        text = section.text() or ""
        if not text.strip():
            continue
        section_id = _stable_id(doc_id, key)
        sections.append(
            Section(
                section_id=section_id,
                doc_id=doc_id,
                title=_pretty_title(section, key),
                item=section.item,
                start_char=0,
                end_char=len(text),
                part=section.part,
            )
        )
        texts[section_id] = text
    return sections, texts, _document_text(filing_obj)


def _pretty_title(section: Any, key: str) -> str:
    """A readable section title.

    edgartools already gives good titles for 8-Ks ('Item 5.02 - Departure...')
    but gives 10-K/10-Q sections the raw key ('part_i_item_7'). Prefer the
    library's title when it looks human-written, otherwise build one from the
    part and item numbers. `part` is a bare Roman numeral ('I', 'II') on
    10-K/10-Q and None on 8-K, where `item` is '502' rather than '5.02'.
    """
    title = getattr(section, "title", None)
    if title and not str(title).startswith("part_"):
        return str(title)
    item = getattr(section, "item", None)
    part = getattr(section, "part", None)
    if item:
        label = f"Part {part}" if part else "Item"
        return f"{label} {item}"
    return str(title or key)


def section_texts(filing_obj: Any) -> dict[str, str]:
    container = getattr(filing_obj, "sections", None)
    if container is None:
        return {}
    out: dict[str, str] = {}
    for key, section in container.items():
        text = section.text() or ""
        if text.strip():
            out[key] = text
    return out


def _document_text(filing_obj: Any) -> str:
    for attr in ("text",):
        method = getattr(filing_obj, attr, None)
        if callable(method):
            try:
                return method() or ""
            except Exception:  # pragma: no cover - defensive
                pass
    document = getattr(filing_obj, "document", None)
    if document is not None:
        try:
            return document.text() or ""
        except Exception:  # pragma: no cover - defensive
            pass
    return ""


# --------------------------------------------------------------------------- #
# XBRL facts
# --------------------------------------------------------------------------- #

# Concepts the tools need in P2+, as bare names. Filers differ in which revenue
# tag they use, so revenue has accepted synonyms; the rest are single-tag.
CONCEPT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ),
    "GrossProfit": ("GrossProfit",),
    "OperatingIncome": ("OperatingIncomeLoss",),
    "NetIncome": ("NetIncomeLoss",),
    "Assets": ("Assets",),
    "Liabilities": ("Liabilities",),
    "StockholdersEquity": ("StockholdersEquity",),
    "Cash": ("CashAndCashEquivalentsAtCarryingValue",),
}
CORE_CONCEPTS = tuple(tag for synonyms in CONCEPT_SYNONYMS.values() for tag in synonyms)
# Every accepted tag, in filing order, so the first match wins.
_ALL_TAGS = set(CORE_CONCEPTS)


def _bare(concept: Any) -> str:
    """'us-gaap:Revenues' -> 'Revenues'. edgartools prefixes the taxonomy."""
    return str(concept).split(":")[-1]


def canonical_concept(concept: Any) -> str | None:
    """Map a filing tag to our canonical name, or None if we do not track it."""
    bare = _bare(concept)
    for canonical, synonyms in CONCEPT_SYNONYMS.items():
        if bare in synonyms:
            return canonical
    return None


def extract_facts(
    company: CompanyInfo,
    taxonomy: str = "us-gaap",
    start: str | None = None,
    end: str | None = None,
) -> list[Fact]:
    """XBRL facts for a company, in our Fact shape.

    Only concepts in CONCEPT_SYNONYMS are kept: a 10-K has ~800 us-gaap tags
    and we want the handful the calc and comparison tools read. Facts outside
    the corpus window are dropped, because docs/PLAN.md D4 fixes the window at
    FY2023-25 and a benchmark answer must not quietly come from 2010.
    """
    import edgar

    if start is None or end is None:
        from loupe.core.settings import get_settings

        settings = get_settings()
        start = start or settings.corpus_start
        end = end or settings.corpus_end
    window_start, window_end = _parse_date(start), _parse_date(end)

    facts = edgar.Company(company.ticker).facts
    if facts is None:
        return []
    try:
        frame = facts.to_dataframe(taxonomy)
    except Exception as exc:  # pragma: no cover - network/parse failures
        logger.warning("%s: XBRL frame unavailable (%s)", company.ticker, exc)
        return []
    if frame is None or frame.empty or "concept" not in frame:
        return []

    frame = frame[frame["concept"].map(_bare).isin(_ALL_TAGS)]

    out: list[Fact] = []
    for record in frame.to_dict("records"):
        period_end = _parse_date(record.get("period_end"))
        if period_end is None:
            continue
        if window_start and period_end < window_start:
            continue
        if window_end and period_end > window_end:
            continue
        canonical = canonical_concept(record["concept"]) or _bare(record["concept"])
        out.append(
            Fact(
                fact_id=_stable_id(
                    company.cik,
                    canonical,
                    str(period_end),
                    str(record.get("period_type")),
                    str(record.get("fiscal_year")),
                ),
                company_id=company.ticker,
                concept=f"{taxonomy}:{canonical}",
                value=float(record.get("numeric_value") or 0.0),
                unit=str(record.get("unit") or "USD"),
                period_end=period_end,
                period_start=_parse_date(record.get("period_start")),
                fiscal_year=record.get("fiscal_year"),
                fiscal_period=record.get("fiscal_period"),
                form=record.get("form_type"),
                accession=record.get("accession"),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #


BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class PriceUnavailable(RuntimeError):
    """Raised when no configured price provider can serve a ticker.

    Prices are optional in P1 (docs/PLAN.md "done when" is about filings and
    cited chunks). Ingest records the failure and carries on, because a
    missing price series must not cost us the filing text that the rest of the
    benchmark depends on.
    """


def _stooq(ticker: str, start: str, end: str) -> Iterator[tuple[date, float]]:
    import csv
    import io

    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&d1={start}&d2={end}&i=d"
    response = httpx.get(
        url, timeout=60.0, follow_redirects=True, headers={"User-Agent": BROWSER_UA}
    )
    response.raise_for_status()
    text = response.text.lstrip()
    if text.startswith("<"):
        # Stooq answers scrapers with a JavaScript proof-of-work page.
        raise PriceUnavailable("stooq returned an HTML challenge, not CSV")
    for row in csv.DictReader(io.StringIO(text)):
        close = row.get("Close")
        day = _parse_date(row.get("Date"))
        if day and close:
            yield day, float(close)


PRICE_PROVIDERS = {"stooq": _stooq}


def fetch_daily_prices(
    ticker: str,
    start: str = "2023-01-01",
    end: str = "2025-12-31",
    provider: str = "stooq",
) -> Iterator[tuple[date, float]]:
    """Daily closes from a free, key-less provider.

    Returns (date, close) pairs. Yielding rather than returning keeps a
    multi-year series out of memory during ingest. Raises PriceUnavailable
    if the provider is blocked; callers record that and continue.
    """
    fetch = PRICE_PROVIDERS.get(provider)
    if fetch is None:
        raise PriceUnavailable(f"unknown price provider {provider!r}")
    series = list(fetch(ticker, start, end))
    if not series:
        raise PriceUnavailable(f"{provider} returned no rows for {ticker}")
    return iter(series)


def chunk_for_section(section: Section, section_text: str, chunk_id: str) -> Chunk:
    """A Chunk that carries the exact section text, so quotes resolve locally."""
    return Chunk(
        chunk_id=chunk_id,
        doc_id=section.doc_id,
        company_id="",
        text=section_text,
        start_char=0,
        end_char=len(section_text),
        section_id=section.section_id,
        metadata={
            "title": section.title,
            "item": section.item,
            "part": section.part,
        },
    )
