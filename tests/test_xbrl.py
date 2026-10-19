import duckdb

from loupe.sources.us.xbrl import iter_rows, load_facts, to_fact

FACTS = {
    "facts": {
        "us-gaap": {
            "Revenues": {
                "label": "Revenues",
                "units": {
                    "USD": [
                        # FY2023 value, first reported in the FY2023 10-K ...
                        {"start": "2023-01-01", "end": "2023-12-31", "val": 100, "accn": "a1",
                         "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01"},
                        # ... and restated in the FY2024 10-K
                        {"start": "2023-01-01", "end": "2023-12-31", "val": 98, "accn": "a2",
                         "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01"},
                        {"start": "2010-01-01", "end": "2010-12-31", "val": 1, "accn": "a0",
                         "fy": 2010, "fp": "FY", "form": "10-K", "filed": "2011-02-01"},
                    ]
                },
            }
        },
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {"shares": [{"end": "2024-01-31", "val": 5, "accn": "a1",
                                      "form": "10-K", "filed": "2024-02-01"}]}
            }
        },
    }
}  # fmt: skip


def test_rows_keep_provenance_and_skip_old_periods():
    rows = iter_rows("ACME", FACTS)
    assert len(rows) == 3
    fact = to_fact(next(r for r in rows if r[12] == "a2"))
    assert (fact.concept, fact.value, fact.unit) == ("us-gaap:Revenues", 98.0, "USD")


def test_latest_view_prefers_most_recent_filing_and_reload_replaces(tmp_path):
    db = tmp_path / "loupe.duckdb"
    assert load_facts(db, "ACME", FACTS) == 3
    assert load_facts(db, "ACME", FACTS) == 3  # idempotent per company

    with duckdb.connect(str(db)) as con:
        assert con.execute("SELECT count(*) FROM facts").fetchone()[0] == 3
        latest = con.execute(
            "SELECT value, accession FROM facts_latest WHERE concept = 'Revenues'"
        ).fetchall()
    assert latest == [(98.0, "a2")]
