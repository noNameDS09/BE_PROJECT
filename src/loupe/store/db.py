"""DuckDB persistence for the corpus and run results.

One file, `data/loupe.duckdb`, holding documents, sections, chunks, facts and
prices. Chunks are stored with their text so that a citation can be verified
later without re-fetching a filing: a benchmark run must not depend on the
network being up or on SEC still serving the same bytes.
"""

from collections.abc import Iterable, Iterator
from pathlib import Path

import duckdb

from loupe.core.schemas import Chunk, CompanyInfo, Document, Fact, Section

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker VARCHAR PRIMARY KEY,
    name VARCHAR,
    cik VARCHAR,
    sector VARCHAR,
    split VARCHAR,
    source VARCHAR
);
CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR PRIMARY KEY,
    company_id VARCHAR,
    form VARCHAR,
    accession VARCHAR,
    fiscal_year INTEGER,
    fiscal_period VARCHAR,
    period_end DATE,
    filed_at TIMESTAMP,
    url VARCHAR,
    content_hash VARCHAR
);
CREATE TABLE IF NOT EXISTS sections (
    section_id VARCHAR PRIMARY KEY,
    doc_id VARCHAR,
    title VARCHAR,
    item VARCHAR,
    part VARCHAR,
    start_char INTEGER,
    end_char INTEGER
);
CREATE TABLE IF NOT EXISTS section_text (
    section_id VARCHAR PRIMARY KEY,
    text VARCHAR
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id VARCHAR PRIMARY KEY,
    doc_id VARCHAR,
    company_id VARCHAR,
    section_id VARCHAR,
    text VARCHAR,
    start_char INTEGER,
    end_char INTEGER,
    title VARCHAR,
    item VARCHAR,
    form VARCHAR,
    fiscal_year INTEGER,
    fiscal_period VARCHAR,
    period_end DATE
);
CREATE TABLE IF NOT EXISTS facts (
    fact_id VARCHAR PRIMARY KEY,
    company_id VARCHAR,
    concept VARCHAR,
    value DOUBLE,
    unit VARCHAR,
    period_end DATE,
    period_start DATE,
    fiscal_year INTEGER,
    fiscal_period VARCHAR,
    form VARCHAR,
    accession VARCHAR
);
CREATE TABLE IF NOT EXISTS prices (
    company_id VARCHAR,
    day DATE,
    close DOUBLE,
    PRIMARY KEY (company_id, day)
);
CREATE TABLE IF NOT EXISTS coverage (
    company_id VARCHAR PRIMARY KEY,
    filings INTEGER,
    sections INTEGER,
    chunks INTEGER,
    facts INTEGER,
    price_rows INTEGER,
    updated_at TIMESTAMP
);
"""


def connect(path: Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path), read_only=read_only)
    if not read_only:
        for statement in SCHEMA.strip().split(";"):
            if statement.strip():
                conn.execute(statement)
    return conn


def _rows(values: Iterable[tuple]) -> list[tuple]:
    return list(values)


def upsert(conn: duckdb.DuckDBPyConnection, table: str, rows: Iterable[tuple]) -> int:
    rows = _rows(rows)
    if not rows:
        return 0
    placeholders = ", ".join(["?"] * len(rows[0]))
    conn.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", rows)
    return len(rows)


def save_companies(conn: duckdb.DuckDBPyConnection, companies: Iterable[CompanyInfo]) -> int:
    return upsert(
        conn,
        "companies",
        [(c.ticker, c.name, c.cik, c.sector, c.split, c.source) for c in companies],
    )


def save_documents(conn: duckdb.DuckDBPyConnection, docs: Iterable[Document]) -> int:
    return upsert(
        conn,
        "documents",
        [
            (
                d.doc_id,
                d.company_id,
                d.form,
                d.accession,
                d.fiscal_year,
                d.fiscal_period,
                d.period_end,
                d.filed_at,
                d.url,
                d.content_hash,
            )
            for d in docs
        ],
    )


def save_sections(
    conn: duckdb.DuckDBPyConnection,
    sections: Iterable[Section],
    texts: dict[str, str],
) -> int:
    rows = [
        (s.section_id, s.doc_id, s.title, s.item, s.part, s.start_char, s.end_char)
        for s in sections
    ]
    count = upsert(conn, "sections", rows)
    upsert(conn, "section_text", [(sid, txt) for sid, txt in texts.items()])
    return count


def save_chunks(conn: duckdb.DuckDBPyConnection, chunks: Iterable[Chunk]) -> int:
    return upsert(
        conn,
        "chunks",
        [
            (
                c.chunk_id,
                c.doc_id,
                c.company_id,
                c.section_id,
                c.text,
                c.start_char,
                c.end_char,
                c.metadata.get("title"),
                c.metadata.get("item"),
                c.metadata.get("form"),
                c.metadata.get("fiscal_year"),
                c.metadata.get("fiscal_period"),
                c.metadata.get("period_end"),
            )
            for c in chunks
        ],
    )


def save_facts(conn: duckdb.DuckDBPyConnection, facts: Iterable[Fact]) -> int:
    return upsert(
        conn,
        "facts",
        [
            (
                f.fact_id,
                f.company_id,
                f.concept,
                f.value,
                f.unit,
                f.period_end,
                f.period_start,
                f.fiscal_year,
                f.fiscal_period,
                f.form,
                f.accession,
            )
            for f in facts
        ],
    )


def save_prices(conn: duckdb.DuckDBPyConnection, company_id: str, pairs: Iterable[tuple]) -> int:
    return upsert(conn, "prices", [(company_id, day, close) for day, close in pairs])


def count_rows(conn: duckdb.DuckDBPyConnection, table: str, company_id: str) -> int:
    """Rows actually stored for a company, used so reports cannot over-count."""
    return conn.execute(
        f"SELECT count(*) FROM {table} WHERE company_id = ?", [company_id]
    ).fetchone()[0]


def record_coverage(conn: duckdb.DuckDBPyConnection, company_id: str) -> dict:
    def count(table: str, extra: str = "") -> int:
        return conn.execute(
            f"SELECT count(*) FROM {table} WHERE company_id = ? {extra}", [company_id]
        ).fetchone()[0]

    prices = conn.execute(
        "SELECT count(*) FROM prices WHERE company_id = ?", [company_id]
    ).fetchone()[0]
    stats = {
        "filings": count("documents"),
        "chunks": count("chunks"),
        "facts": count("facts"),
        "price_rows": prices,
        "sections": conn.execute(
            """SELECT count(*) FROM sections s
               JOIN documents d ON d.doc_id = s.doc_id
               WHERE d.company_id = ?""",
            [company_id],
        ).fetchone()[0],
    }
    conn.execute(
        """INSERT OR REPLACE INTO coverage VALUES (?, ?, ?, ?, ?, ?, now())""",
        [
            company_id,
            stats["filings"],
            stats["sections"],
            stats["chunks"],
            stats["facts"],
            stats["price_rows"],
        ],
    )
    return stats


def iter_chunks(conn: duckdb.DuckDBPyConnection) -> Iterator[dict]:
    result = conn.execute(
        """SELECT chunk_id, doc_id, company_id, section_id, text, title, item, form,
                  fiscal_year, fiscal_period, period_end
           FROM chunks"""
    )
    columns = [c[0] for c in result.description]
    for row in result.fetchall():
        yield dict(zip(columns, row, strict=True))


def coverage_report(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    result = conn.execute(
        """SELECT c.ticker,
                  coalesce(v.filings, 0)  AS filings,
                  coalesce(v.sections, 0) AS sections,
                  coalesce(v.chunks, 0)   AS chunks,
                  coalesce(v.facts, 0)    AS facts,
                  coalesce(v.price_rows, 0) AS price_rows
           FROM companies c LEFT JOIN coverage v ON v.company_id = c.ticker
           ORDER BY coalesce(v.chunks, 0) DESC, c.ticker"""
    )
    columns = [c[0] for c in result.description]
    return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
