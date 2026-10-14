"""Store tests against a real temporary DuckDB file."""

from datetime import date, datetime

import pytest

from loupe.core.schemas import Chunk, CompanyInfo, Document, Fact, Section
from loupe.store import db


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.duckdb")
    yield connection
    connection.close()


def test_connect_is_idempotent(tmp_path):
    path = tmp_path / "test.duckdb"
    first = db.connect(path)
    first.close()
    second = db.connect(path)
    tables = {r[0] for r in second.execute("SHOW TABLES").fetchall()}
    assert "chunks" in tables
    second.close()


def test_save_and_read_chunks(conn):
    chunk = Chunk(
        chunk_id="s1:000",
        doc_id="d1",
        company_id="AMD",
        text="Body text here.",
        start_char=0,
        end_char=14,
        section_id="s1",
        metadata={
            "title": "Item 7",
            "item": "7",
            "form": "10-K",
            "fiscal_year": 2024,
            "fiscal_period": "FY",
            "period_end": "2024-12-28",
        },
    )
    assert db.save_chunks(conn, [chunk]) == 1
    rows = list(db.iter_chunks(conn))
    assert len(rows) == 1
    assert rows[0]["text"] == "Body text here."
    assert rows[0]["item"] == "7"


def test_upsert_replaces_rather_than_duplicates(conn):
    doc = Document(
        doc_id="d1",
        company_id="AMD",
        source="sec_edgar",
        form="10-K",
        url="u",
        content_hash="h1",
        accession="0001",
        fiscal_year=2024,
        period_end=date(2024, 12, 28),
        filed_at=datetime(2025, 2, 5),
    )
    db.save_documents(conn, [doc])
    db.save_documents(conn, [doc])
    assert conn.execute("SELECT count(*) FROM documents").fetchone()[0] == 1


def test_facts_roundtrip_and_dedupe(conn):
    fact = Fact(
        fact_id="f1",
        company_id="AMD",
        concept="us-gaap:Revenue",
        value=25.8,
        unit="USD",
        period_end=date(2024, 12, 28),
        fiscal_year=2024,
        fiscal_period="FY",
        form="10-K",
        accession="0001",
    )
    db.save_facts(conn, [fact, fact])
    assert db.count_rows(conn, "facts", "AMD") == 1


def test_sections_store_text_separately(conn):
    section = Section(
        section_id="s1",
        doc_id="d1",
        title="Item 1A",
        item="1A",
        start_char=0,
        end_char=25,
        part="Part I",
    )
    db.save_sections(conn, [section], {"s1": "Risk factor body text."})
    text = conn.execute("SELECT text FROM section_text WHERE section_id = ?", ["s1"]).fetchone()
    assert text[0] == "Risk factor body text."


def test_coverage_recorded_per_company(conn):
    db.save_companies(conn, [CompanyInfo(ticker="AMD", name="AMD", cik="0000002488")])
    db.save_documents(
        conn,
        [
            Document(
                doc_id="d1",
                company_id="AMD",
                source="sec_edgar",
                form="10-K",
                url="u",
                content_hash="h",
                accession="1",
                period_end=date(2024, 12, 28),
            )
        ],
    )
    db.save_chunks(
        conn,
        [Chunk(chunk_id="c1", doc_id="d1", company_id="AMD", text="x", start_char=0, end_char=1)],
    )
    db.save_prices(conn, "AMD", [(date(2024, 1, 2), 100.0)])
    stats = db.record_coverage(conn, "AMD")
    assert stats["filings"] == 1
    assert stats["chunks"] == 1
    assert stats["price_rows"] == 1


def test_coverage_report_includes_companies_with_no_data(conn):
    db.save_companies(
        conn,
        [
            CompanyInfo(ticker="AMD", name="AMD", cik="1"),
            CompanyInfo(ticker="KO", name="KO", cik="2"),
        ],
    )
    rows = db.coverage_report(conn)
    assert len(rows) == 2
    assert all(row["chunks"] == 0 for row in rows)


def test_count_rows_is_scoped_to_company(conn):
    db.save_facts(
        conn,
        [
            Fact(
                fact_id="f1",
                company_id="AMD",
                concept="us-gaap:Assets",
                value=1.0,
                unit="USD",
                period_end=date(2024, 12, 28),
            ),
            Fact(
                fact_id="f2",
                company_id="KO",
                concept="us-gaap:Assets",
                value=2.0,
                unit="USD",
                period_end=date(2024, 12, 28),
            ),
        ],
    )
    assert db.count_rows(conn, "facts", "AMD") == 1
    assert db.count_rows(conn, "facts", "KO") == 1


def test_save_empty_lists_is_noop(conn):
    assert db.save_chunks(conn, []) == 0
    assert db.save_facts(conn, []) == 0
