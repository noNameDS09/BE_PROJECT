"""Fetch the US corpus: periodic reports, 8-Ks with earnings releases, XBRL facts."""

import json
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from loupe.core.schemas import Company
from loupe.sources.us import edgar
from loupe.sources.us.sec_client import SecClient

FORMS = ("10-K", "10-Q", "8-K")
# press releases: most filers use EX-99.1, some (PFE, BBY, VZ) plain EX-99
EXHIBITS = {"8-K": ("EX-99.1", "EX-99"), "10-K": (), "10-Q": ()}


class FilingRecord(BaseModel):
    company_id: str
    cik: str
    form: str
    accession: str
    filing_date: date
    report_date: date | None
    items: list[str]
    files: list[str]  # paths relative to the SEC raw dir
    url: str


class Coverage(BaseModel):
    company_id: str
    listed: dict[str, int]
    fetched: dict[str, int]
    facts: bool
    errors: list[str]


def fetch_company(
    client: SecClient,
    company: Company,
    start: date,
    end: date,
    progress: Callable[[str], None] = lambda _: None,
) -> tuple[list[FilingRecord], Coverage]:
    assert company.cik, f"{company.id} has no CIK"
    subs = edgar.submissions(client, company.cik, since=start)
    window = edgar.select_window(subs["filings"], start, end, FORMS)
    records, errors = [], []
    for i, ref in enumerate(window, 1):
        progress(f"{company.id} {i}/{len(window)} {ref.form} {ref.filing_date}")
        try:
            paths = edgar.download_filing(client, ref, EXHIBITS[ref.form])
        except Exception as exc:  # keep going; the coverage report shows the gap
            errors.append(f"{ref.accession} {ref.form}: {type(exc).__name__}: {exc}"[:200])
            continue
        records.append(
            FilingRecord(
                company_id=company.id,
                cik=company.cik,
                form=ref.form,
                accession=ref.accession,
                filing_date=ref.filing_date,
                report_date=ref.report_date,
                items=ref.items,
                files=[str(p.relative_to(client.raw_dir)) for p in paths],
                url=ref.url,
            )
        )
    try:
        edgar.company_facts(client, company.cik)
        facts = True
    except Exception as exc:
        errors.append(f"companyfacts: {type(exc).__name__}: {exc}"[:200])
        facts = False
    coverage = Coverage(
        company_id=company.id,
        listed=dict(Counter(f.form for f in window)),
        fetched=dict(Counter(r.form for r in records)),
        facts=facts,
        errors=errors,
    )
    return records, coverage


def write_manifest(path: Path, records: list[FilingRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def write_coverage(path: Path, coverage: list[Coverage]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([c.model_dump() for c in coverage], indent=1))
