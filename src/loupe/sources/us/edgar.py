"""EDGAR filing index, filing documents and XBRL company facts."""

import html
import re
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from loupe.sources.us.sec_client import SecClient

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/{name}"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{name}"


def pad_cik(cik: int | str) -> str:
    return str(int(cik)).zfill(10)


class TickerInfo(BaseModel):
    ticker: str
    cik: str
    title: str


class FilingRef(BaseModel):
    cik: str
    accession: str
    form: str
    filing_date: date
    report_date: date | None
    items: list[str]
    primary_document: str
    size: int = 0

    @property
    def folder(self) -> str:
        return self.accession.replace("-", "")

    def archive_url(self, name: str) -> str:
        return ARCHIVE_URL.format(cik=int(self.cik), folder=self.folder, name=name)

    @property
    def url(self) -> str:
        return self.archive_url(self.primary_document)

    @property
    def index_url(self) -> str:
        return self.archive_url(f"{self.accession}-index.htm")


class FilingDocument(BaseModel):
    seq: str
    description: str
    name: str
    type: str
    size: int | None


def ticker_map(client: SecClient) -> dict[str, TickerInfo]:
    raw = client.get_json(TICKERS_URL)
    out = {}
    for row in raw.values():
        info = TickerInfo(ticker=row["ticker"], cik=pad_cik(row["cik_str"]), title=row["title"])
        out[info.ticker.upper()] = info
    return out


def _parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def _rows(columns: dict[str, list[Any]], cik: str) -> list[FilingRef]:
    return [
        FilingRef(
            cik=cik,
            accession=columns["accessionNumber"][i],
            form=columns["form"][i],
            filing_date=date.fromisoformat(columns["filingDate"][i]),
            report_date=_parse_date(columns["reportDate"][i]),
            items=[x for x in columns["items"][i].split(",") if x],
            primary_document=columns["primaryDocument"][i],
            size=columns["size"][i] or 0,
        )
        for i in range(len(columns["accessionNumber"]))
    ]


def submissions(client: SecClient, cik: str, since: date | None = None) -> dict[str, Any]:
    """Company metadata plus every filing (recent block and older pages back to `since`)."""
    meta = client.get_json(SUBMISSIONS_URL.format(name=f"CIK{pad_cik(cik)}.json"))
    filings = _rows(meta["filings"]["recent"], pad_cik(cik))
    for page in meta["filings"].get("files", []):
        if since and date.fromisoformat(page["filingTo"]) < since:
            continue
        filings += _rows(client.get_json(SUBMISSIONS_URL.format(name=page["name"])), pad_cik(cik))
    meta = {k: v for k, v in meta.items() if k != "filings"}
    return {"meta": meta, "filings": filings}


def select_window(
    filings: list[FilingRef], start: date, end: date, forms: tuple[str, ...]
) -> list[FilingRef]:
    """Periodic reports by period of report; 8-Ks by filing date. Amendments excluded."""
    selected = []
    for f in filings:
        if f.form not in forms:
            continue
        when = f.report_date if f.form in ("10-K", "10-Q") else f.filing_date
        if when and start <= when <= end:
            selected.append(f)
    return sorted(selected, key=lambda f: (f.filing_date, f.accession))


def parse_index(page: str) -> list[FilingDocument]:
    table = re.search(r'(?is)<table class="tableFile".*?</table>', page)
    if not table:
        return []
    docs = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", table.group(0)):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", " ").strip()
            for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)
        ]
        if len(cells) != 5 or not cells[2]:
            continue
        seq, description, name, doc_type, size = cells
        docs.append(
            FilingDocument(
                seq=seq,
                description=description,
                name=name.split()[0],  # drop the "iXBRL" marker
                type=doc_type,
                size=int(size) if size.isdigit() else None,
            )
        )
    return docs


def filing_documents(client: SecClient, ref: FilingRef) -> list[FilingDocument]:
    return parse_index(client.get(ref.index_url).decode("utf-8", errors="replace"))


def download_filing(
    client: SecClient, ref: FilingRef, exhibit_types: tuple[str, ...] = ("EX-99.1",)
) -> list[Path]:
    """Fetch the primary document and the requested exhibits; return their cache paths."""
    names = [ref.primary_document]
    if exhibit_types:
        names += [d.name for d in filing_documents(client, ref) if d.type in exhibit_types]
    paths = []
    for name in dict.fromkeys(names):
        url = ref.archive_url(name)
        client.get(url)
        paths.append(client.cache_path(url))
    return paths


def company_facts(client: SecClient, cik: str) -> dict[str, Any]:
    return client.get_json(FACTS_URL.format(cik=pad_cik(cik)))
