from datetime import date
from pathlib import Path

import pytest

from loupe.sources.us.xbrl import load_facts
from loupe.tools.facts import FactsStore, MetricSpec


def row(start, end, val, accn, fy, fp, form, filed, concept="Revenues", unit="USD"):
    return concept, unit, {
        "start": start, "end": end, "val": val, "accn": accn, "fy": fy, "fp": fp,
        "form": form, "filed": filed,
    }  # fmt: skip


# A retailer whose fiscal year ends in late January / early February and is labelled by the
# year it starts in (like Ulta / Kroger), with one filing carrying a wrong `fy` (like Kroger).
ROWS = [
    row("2022-01-30", "2023-01-28", 100, "k22", 2022, "FY", "10-K", "2023-03-20"),
    row("2023-01-29", "2024-02-03", 110, "k23", 2024, "FY", "10-K", "2024-03-20"),  # wrong fy
    row("2024-02-04", "2025-02-01", 120, "k24", 2024, "FY", "10-K", "2025-03-20"),
    row("2024-02-04", "2024-11-02", 85, "q324", 2024, "Q3", "10-Q", "2024-12-01"),  # 9M YTD
    row("2024-08-04", "2024-11-02", 29, "q324", 2024, "Q3", "10-Q", "2024-12-01"),  # Q3
    row(None, "2025-02-01", 999, "k24", 2024, "FY", "10-K", "2025-03-20", "Assets"),
]


@pytest.fixture
def store(tmp_path):
    facts = {"facts": {"us-gaap": {}}}
    for concept, unit, values in ROWS:
        v = {k: x for k, x in values.items() if x is not None}
        facts["facts"]["us-gaap"].setdefault(concept, {"units": {}})["units"].setdefault(
            unit, []
        ).append(v)
    db = tmp_path / "f.duckdb"
    load_facts(db, "RET", facts)
    metrics = {
        "revenue": MetricSpec(
            kind="duration", unit="USD", concepts=["SalesRevenueNet", "Revenues"]
        ),
        "total_assets": MetricSpec(kind="instant", unit="USD", concepts=["Assets"]),
    }
    return FactsStore(Path(db), metrics, {"RET": "1"})


def test_calendar_uses_majority_label_offset_despite_one_wrong_fy(store):
    cal = store.calendar("RET")
    assert cal.offset == -1
    assert [cal.fy_label(e) for e in cal.fy_ends] == [2022, 2023, 2024]


def test_annual_quarter_derived_q4_and_instant_values(store):
    fy = store.get("RET", "revenue", 2023)
    assert (fy.value, fy.period_end, fy.concept) == (110, date(2024, 2, 3), "Revenues")
    assert store.get("RET", "revenue", 2024, "Q3").value == 29
    q4 = store.get("RET", "revenue", 2024, "Q4")
    assert (q4.value, q4.derived) == (35, "FY - 9M YTD")
    assets = store.get("RET", "total_assets", 2024)
    assert assets.value == 999 and assets.period_start is None
    assert assets.url == "https://www.sec.gov/Archives/edgar/data/1/k24/"


def test_missing_values_return_none(store):
    assert store.get("RET", "revenue", 2019) is None
    assert store.get("RET", "total_assets", 2022) is None
