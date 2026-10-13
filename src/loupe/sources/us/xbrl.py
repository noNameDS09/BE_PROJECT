"""XBRL company facts -> Fact rows -> DuckDB.

Every reported value keeps its provenance (accession, form, filing date), so the
same number reported in several filings appears once per filing. The `facts_latest`
view keeps the most recently filed value for each (company, concept, unit, period),
which is what questions and tools should use.
"""

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from loupe.core.schemas import Fact

MIN_PERIOD_END = date(2015, 1, 1)  # enough history for trend backtests

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    fact_id VARCHAR PRIMARY KEY,
    company_id VARCHAR,
    taxonomy VARCHAR,
    concept VARCHAR,
    label VARCHAR,
    unit VARCHAR,
    value DOUBLE,
    period_start DATE,
    period_end DATE,
    fiscal_year INTEGER,
    fiscal_period VARCHAR,
    form VARCHAR,
    accession VARCHAR,
    filed DATE,
    frame VARCHAR
);
CREATE OR REPLACE VIEW facts_latest AS
SELECT * EXCLUDE (rn) FROM (
    SELECT *, row_number() OVER (
        PARTITION BY company_id, concept, unit, period_start, period_end
        ORDER BY filed DESC, accession DESC
    ) AS rn
    FROM facts
) WHERE rn = 1;
"""

COLUMNS = (
    "fact_id, company_id, taxonomy, concept, label, unit, value, period_start, period_end, "
    "fiscal_year, fiscal_period, form, accession, filed, frame"
)


def iter_rows(company_id: str, companyfacts: dict[str, Any]) -> list[tuple]:
    rows = {}
    for taxonomy, concepts in companyfacts.get("facts", {}).items():
        for concept, body in concepts.items():
            for unit, values in body.get("units", {}).items():
                for v in values:
                    end = date.fromisoformat(v["end"])
                    if end < MIN_PERIOD_END:
                        continue
                    key = "|".join(
                        str(x)
                        for x in (company_id, taxonomy, concept, unit, v.get("start"), v["end"],
                                  v["accn"], v.get("fp"), v.get("frame"))
                    )  # fmt: skip
                    fact_id = hashlib.sha256(key.encode()).hexdigest()[:20]
                    rows[fact_id] = (
                        fact_id,
                        company_id,
                        taxonomy,
                        concept,
                        body.get("label"),
                        unit,
                        float(v["val"]),
                        v.get("start"),
                        v["end"],
                        v.get("fy"),
                        v.get("fp"),
                        v.get("form"),
                        v["accn"],
                        v.get("filed"),
                        v.get("frame"),
                    )
    return list(rows.values())


def to_fact(row: tuple) -> Fact:
    return Fact(
        fact_id=row[0],
        company_id=row[1],
        concept=f"{row[2]}:{row[3]}",
        unit=row[5],
        value=row[6],
        period_start=row[7],
        period_end=row[8],
        fiscal_year=row[9],
        fiscal_period=row[10],
        form=row[11],
        accession=row[12],
    )


def load_facts(db_path: Path, company_id: str, companyfacts: dict[str, Any]) -> int:
    """Replace one company's facts in the DuckDB store; return the number of rows."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    rows = iter_rows(company_id, companyfacts)
    with duckdb.connect(str(db_path)) as con:
        con.execute(SCHEMA)
        con.execute("DELETE FROM facts WHERE company_id = ?", [company_id])
        if rows:
            placeholders = ", ".join("?" * len(rows[0]))
            con.executemany(f"INSERT INTO facts ({COLUMNS}) VALUES ({placeholders})", rows)
    return len(rows)
