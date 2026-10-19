"""Loupe-Gold builders and verifiers on a small fake context (no data dir, no DuckDB)."""

from datetime import date
from pathlib import Path

import pytest

from loupe.datasets.gold import calc, events, plan, trick
from loupe.datasets.gold.common import GoldContext, calendar_year_end, fmt_usd
from loupe.datasets.gold.sec_items import EVENT_ITEMS, EVENT_PHRASES, ITEM_NAMES
from loupe.datasets.gold.verify import verify_events, verify_trick
from loupe.datasets.universe import load_universe


def _ctx(manifest: list[dict], doc_ids: set[str]) -> GoldContext:
    return GoldContext(Path("."), None, load_universe(), manifest, doc_ids)  # type: ignore[arg-type]


def _8k(company: str, acc: str, items: list[str], filed: str = "2024-02-22") -> dict:
    return {
        "company_id": company,
        "form": "8-K",
        "accession": acc,
        "filing_date": filed,
        "report_date": filed,
        "items": items,
        "url": f"https://www.sec.gov/{acc}",
    }


MANIFEST = [
    _8k("UNH", "0000731766-24-000045", ["1.05", "9.01"]),
    _8k("DBD", "0000028823-23-000001", ["1.03", "7.01", "9.01"], "2023-06-01"),
    _8k("PEP", "0000077476-23-000009", ["2.02", "9.01"]),  # earnings only: not an event
    _8k("MMM", "0000066740-24-000010", ["5.02"]),
]
DOCS = {
    "UNH_8-K_0000731766-24-000045",
    "UNH_8-K_0000731766-24-000045_ex1",
    "DBD_8-K_0000028823-23-000001",
    "PEP_8-K_0000077476-23-000009",
    "MMM_8-K_0000066740-24-000010",
}


def test_event_labels_build_and_verify():
    ctx = _ctx(MANIFEST, DOCS)
    items = events.build(ctx)
    assert [i.companies[0] for i in items] == ["DBD", "MMM", "UNH"]
    unh = items[-1]
    assert unh.kind == "event" and unh.split == "test"
    assert [d.doc_id for d in unh.documents] == [
        "UNH_8-K_0000731766-24-000045",
        "UNH_8-K_0000731766-24-000045_ex1",
    ]
    assert unh.meta["items"] == [{"code": "1.05", "name": "Material Cybersecurity Incidents"}]
    assert unh.meta["quotes"] == {} and unh.evidence[0].item == "1.05"
    assert verify_events(ctx, items) == []
    items[0].meta["items"] = items[0].meta["items"][:1]
    assert any("item codes differ" in e for e in verify_events(ctx, items))
    assert any("has event items but no item" in e for e in verify_events(ctx, items[1:]))


def test_invented_events_avoid_real_filers():
    ctx = _ctx(MANIFEST, DOCS)
    items = trick.invented_events(ctx)
    for item in items:
        assert item.kind == "refusal"
        assert item.meta["item_code"] not in ctx.eight_k_items(item.companies[0])
    assert all(i.companies != ["DBD"] for i in items if i.meta["item_code"] == "1.03")
    assert verify_trick(ctx, items) == []
    bad = next(i for i in items if i.meta["item_code"] == "1.03")
    bad.companies, bad.split = ["DBD"], "test"
    assert verify_trick(ctx, [bad])


def test_wrong_company_attribution():
    ctx = _ctx(MANIFEST, DOCS)
    items = trick.wrong_company(ctx)
    assert {i.meta["actual_company"] for i in items} == {"UNH", "DBD"}
    for item in items:
        assert item.companies[0] != item.meta["actual_company"]
        assert ctx.split(item.companies[0]) == ctx.split(item.meta["actual_company"])
    assert verify_trick(ctx, items) == []


def test_outside_universe():
    ctx = _ctx(MANIFEST, DOCS)
    items = trick.outside_universe(ctx)
    assert len(items) == len(trick.OUTSIDE) and all(not i.companies for i in items)
    assert verify_trick(ctx, items) == []


@pytest.mark.parametrize(
    ("name", "values", "expected"),
    [
        ("yoy_growth_revenue", {"current": 110.0, "prior": 100.0}, 10.0),
        ("yoy_growth_net_income", {"current": 5.0, "prior": -1.0}, None),  # loss base
        ("yoy_growth_net_income", {"current": -5.0, "prior": 1.0}, None),  # into a loss
        ("gross_margin", {"gross_profit": 40.0, "revenue": 100.0}, 40.0),
        ("gross_margin_from_cost", {"revenue": 100.0, "cost_of_revenue": 65.0}, 35.0),
        ("operating_margin", {"operating_income": 12.0, "revenue": 0.0}, None),
        ("current_ratio", {"current_assets": 3.0, "current_liabilities": 2.0}, 1.5),
        ("debt_to_equity", {"long_term_debt": 5.0, "equity": -1.0}, None),  # negative equity
        ("debt_to_equity", {"long_term_debt": 5.0, "equity": 10.0}, 0.5),
        ("free_cash_flow", {"operating_cash_flow": 10.0, "capex": 4.0}, 6.0),
        ("cagr_2y_revenue", {"start": 100.0, "end": 121.0}, 10.0),
    ],
)
def test_calc_formulas(name, values, expected):
    result = calc.CALCS[name].compute(values)
    assert result == (pytest.approx(expected) if expected is not None else None)


def test_calc_inputs_match_years():
    assert calc.CALCS["yoy_growth_revenue"].inputs(2025) == {
        "current": ("revenue", 2025),
        "prior": ("revenue", 2024),
    }
    assert calc.CALCS["cagr_2y_revenue"].inputs(2025)["start"] == ("revenue", 2023)
    assert calc.tolerance("%", 0.4) == pytest.approx(0.125)  # 0.05 pp rounding
    assert calc.tolerance("USD", 5e9) == 0.01


def test_plan_templates_use_known_labels():
    allowed = set(plan.TOOLS) | set(plan.FUTURE_TOOLS)
    for t in plan.TEMPLATES:
        assert set(t.intents) <= set(plan.INTENTS), t.id
        assert set(t.tools) <= allowed and set(t.minimal) <= set(plan.TOOLS), t.id
    assert sum(t.count for t in plan.TEMPLATES) >= 190
    assert any(len(t.intents) > 1 for t in plan.TEMPLATES)


def test_sec_items_and_helpers():
    assert set(EVENT_ITEMS) <= set(ITEM_NAMES) and set(EVENT_PHRASES) <= set(ITEM_NAMES)
    assert ITEM_NAMES["4.02"].startswith("Non-Reliance")
    assert calendar_year_end(date(2023, 1, 1)) and calendar_year_end(date(2024, 12, 28))
    assert not calendar_year_end(date(2025, 2, 1))
    assert fmt_usd(25_785_000_000) == "$25,785 million"
    assert fmt_usd(-28_900_000) == "-$28.9 million"
    assert fmt_usd(2.431, "per_share") == "$2.43 per share"
