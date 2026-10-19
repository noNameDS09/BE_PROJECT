"""8-K item codes -> an events table (one row per item per filing).

The item codes come from SEC's own filing index, so this table is an exact, free
label set: what kind of material event each 8-K reports. LLM extraction later adds
typed fields and verbatim quotes on top of these rows.
"""

from pathlib import Path

import duckdb

from loupe.core.jsonl import jsonl_lines
from loupe.sources.us.fetch import FilingRecord

# Form 8-K item names (SEC General Instructions for Form 8-K)
ITEM_NAMES = {
    "1.01": "Entry into a material definitive agreement",
    "1.02": "Termination of a material definitive agreement",
    "1.03": "Bankruptcy or receivership",
    "1.04": "Mine safety: shutdowns and patterns of violations",
    "1.05": "Material cybersecurity incident",
    "2.01": "Completion of acquisition or disposition of assets",
    "2.02": "Results of operations and financial condition",
    "2.03": "Creation of a direct financial obligation",
    "2.04": "Triggering event accelerating a financial obligation",
    "2.05": "Costs associated with exit or disposal activities",
    "2.06": "Material impairment",
    "3.01": "Notice of delisting or failure to satisfy a listing rule",
    "3.02": "Unregistered sales of equity securities",
    "3.03": "Material modification to rights of security holders",
    "4.01": "Change in registrant's certifying accountant",
    "4.02": "Non-reliance on previously issued financial statements",
    "5.01": "Change in control of registrant",
    "5.02": "Departure or appointment of directors or officers; compensation",
    "5.03": "Amendments to articles of incorporation or bylaws",
    "5.04": "Temporary suspension of trading under employee benefit plans",
    "5.05": "Amendment to or waiver of the code of ethics",
    "5.06": "Change in shell company status",
    "5.07": "Submission of matters to a vote of security holders",
    "5.08": "Shareholder director nominations",
    "6.01": "ABS informational and computational material",
    "7.01": "Regulation FD disclosure",
    "8.01": "Other events",
    "9.01": "Financial statements and exhibits",
}
RISK_ITEMS = {"1.03", "1.05", "2.04", "2.05", "2.06", "3.01", "4.01", "4.02"}

SCHEMA = """
CREATE OR REPLACE TABLE filing_events (
    company_id VARCHAR, accession VARCHAR, filing_date DATE, item VARCHAR,
    item_name VARCHAR, risk BOOLEAN, doc_id VARCHAR, url VARCHAR
)
"""


def load_events(db_path: Path, manifest: Path) -> int:
    rows = []
    for line in jsonl_lines(manifest):
        r = FilingRecord.model_validate_json(line)
        if r.form != "8-K":
            continue
        doc_id = f"{r.company_id}_8-K_{r.accession}"
        for item in r.items:
            name = ITEM_NAMES.get(item, "Unknown item")
            rows.append(
                (
                    r.company_id,
                    r.accession,
                    r.filing_date,
                    item,
                    name,
                    item in RISK_ITEMS,
                    doc_id,
                    r.url,
                )
            )
    with duckdb.connect(str(db_path)) as con:
        con.execute(SCHEMA)
        if rows:
            con.executemany("INSERT INTO filing_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return len(rows)
