"""Turn fetched filings into Documents (clean text + sections) and a parse-quality report.

Quality is measured against what each filing should contain:
  10-K: Items 1A, 7 and 8 found; 10-Q: Part I Items 1 and 2 found;
  8-K: every item code SEC lists for the filing found as a section.
"""

import hashlib
import json
import warnings
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from bs4 import XMLParsedAsHTMLWarning

from loupe.core.schemas import Document, Section
from loupe.ingest import sections
from loupe.ingest.html_text import html_to_text
from loupe.sources.us.fetch import FilingRecord

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

EXPECTED = {"10-K": {"1A", "7", "8"}, "10-Q": {"I-1", "I-2"}}


def expected_items(record: FilingRecord) -> set[str]:
    if record.form == "8-K":
        return set(record.items)
    return EXPECTED.get(record.form, set())


def build_documents(record: FilingRecord, raw_dir: Path, text_dir: Path) -> list[Document]:
    """One Document for the primary filing and one per exhibit, text written to text_dir."""
    docs = []
    for i, rel in enumerate(record.files):
        primary = i == 0
        form = record.form if primary else "EX-99.1"
        doc_id = f"{record.company_id}_{record.form}_{record.accession}" + (
            "" if primary else f"_ex{i}"
        )
        text = html_to_text((raw_dir / rel).read_bytes())
        (text_dir / f"{doc_id}.txt").write_text(text)
        spans = sections.split(form, text)
        docs.append(
            Document(
                doc_id=doc_id,
                company_id=record.company_id,
                source="sec_edgar",
                form=form,
                url=record.url
                if primary
                else f"https://www.sec.gov/{rel.split('www.sec.gov/', 1)[-1]}",
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
                accession=record.accession,
                period_end=record.report_date,
                fiscal_period="FY" if record.form == "10-K" else None,
                sections=[
                    Section(
                        section_id=f"{doc_id}#{s.item}",
                        doc_id=doc_id,
                        title=s.title,
                        item=s.item,
                        start_char=s.start,
                        end_char=s.end,
                    )
                    for s in spans
                ],
            )
        )
    return docs


def build_corpus(
    manifest: Path,
    raw_dir: Path,
    out_dir: Path,
    progress: Callable[[str], None] = lambda _: None,
) -> dict:
    text_dir = out_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    records = [FilingRecord.model_validate_json(line) for line in manifest.read_text().splitlines()]
    found = defaultdict(
        lambda: {"filings": 0, "complete": 0, "items_expected": 0, "items_found": 0}
    )
    misses: list[dict] = []
    errors: list[str] = []
    with (out_dir / "documents.jsonl").open("w") as out:
        for n, record in enumerate(records, 1):
            progress(f"{n}/{len(records)} {record.company_id} {record.form} {record.accession}")
            try:
                docs = build_documents(record, raw_dir, text_dir)
            except Exception as exc:
                errors.append(f"{record.accession}: {type(exc).__name__}: {exc}"[:200])
                continue
            for doc in docs:
                out.write(doc.model_dump_json() + "\n")
            expected = expected_items(record) - {"9.01"}  # exhibits list, often no body heading
            got = {s.item for s in docs[0].sections}
            stats = found[record.form]
            stats["filings"] += 1
            stats["items_expected"] += len(expected)
            stats["items_found"] += len(expected & got)
            if expected <= got:
                stats["complete"] += 1
            else:
                misses.append(
                    {
                        "doc_id": docs[0].doc_id,
                        "missing": sorted(expected - got),
                        "found": sorted(got),
                    }
                )
    report = {
        "by_form": {
            form: {
                **s,
                "complete_rate": round(s["complete"] / max(s["filings"], 1), 4),
                "item_recall": round(s["items_found"] / max(s["items_expected"], 1), 4),
            }
            for form, s in sorted(found.items())
        },
        "errors": errors,
        "misses": misses,
    }
    (out_dir / "parse_report.json").write_text(json.dumps(report, indent=1))
    return report
