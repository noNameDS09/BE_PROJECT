"""Re-check every Loupe-Gold item against the data it was built from.

Numbers are re-queried from FactsStore and recomputed; premises of trick questions are
re-checked against FactsStore, the facts table and the SEC manifest; event labels against
the manifest and parsed documents. Returns a list of human-readable mismatches per set.
"""

import math
from collections.abc import Callable

from loupe.datasets.gold import calc, plan, trick
from loupe.datasets.gold.common import DATA_CUTOFF, YEARS, GoldContext
from loupe.datasets.gold.events import NOT_EVENTS
from loupe.datasets.gold.sec_items import EVENT_ITEMS, ITEM_NAMES
from loupe.eval.schema import EvalItem


def _same(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)


def _common(ctx: GoldContext, item: EvalItem) -> list[str]:
    errs = []
    for c in item.companies:
        if c not in ctx.universe:
            errs.append(f"{item.item_id}: unknown company {c}")
        elif item.split != ctx.split(c):
            errs.append(f"{item.item_id}: split {item.split} != company split {ctx.split(c)}")
    return errs


def _fact_matches(ctx: GoldContext, prov: dict, item_id: str) -> tuple[list[str], float | None]:
    fact = ctx.store.get(prov["company"], prov["metric"], prov["fiscal_year"], prov["period"])
    if fact is None:
        return [f"{item_id}: {prov['metric']} FY{prov['fiscal_year']} no longer resolves"], None
    errs = []
    if not _same(fact.value, prov["value"]):
        errs.append(f"{item_id}: {prov['metric']} value {fact.value} != stored {prov['value']}")
    for key in ("accession", "concept"):
        if getattr(fact, key) != prov[key]:
            errs.append(f"{item_id}: {key} {getattr(fact, key)} != stored {prov[key]}")
    if fact.period_end.isoformat() != prov["period_end"]:
        errs.append(f"{item_id}: period_end {fact.period_end} != stored {prov['period_end']}")
    return errs, fact.value


def verify_num(ctx: GoldContext, items: list[EvalItem]) -> list[str]:
    errs = []
    for item in items:
        errs += _common(ctx, item)
        e, value = _fact_matches(ctx, item.meta["fact"], item.item_id)
        errs += e
        if value is not None and not _same(value, item.answer_value):
            errs.append(f"{item.item_id}: answer_value {item.answer_value} != fact {value}")
    return errs


def verify_calc(ctx: GoldContext, items: list[EvalItem]) -> list[str]:
    errs = []
    for item in items:
        errs += _common(ctx, item)
        spec = calc.CALCS[item.meta["calc"]]
        values = {}
        for key, prov in item.meta["inputs"].items():
            e, value = _fact_matches(ctx, prov, f"{item.item_id}[{key}]")
            errs += e
            values[key] = value
        if any(v is None for v in values.values()):
            continue
        expected_keys = set(spec.inputs(item.fiscal_year or 0))
        if expected_keys != set(values):
            errs.append(f"{item.item_id}: inputs {sorted(values)} != spec {sorted(expected_keys)}")
            continue
        result = spec.compute(values)  # type: ignore[arg-type]
        if not _same(result, item.answer_value):
            errs.append(f"{item.item_id}: recomputed {result} != answer_value {item.answer_value}")
    return errs


def verify_trick(ctx: GoldContext, items: list[EvalItem]) -> list[str]:
    errs = []
    for item in items:
        errs += _common(ctx, item)
        m, reason = item.meta, item.meta["reason"]
        company = item.companies[0] if item.companies else None
        bad = None
        if reason == "future_period":
            end = ctx.store.calendar(company).fy_end_for(m["fiscal_year"])
            if end is not None and end <= DATA_CUTOFF:
                bad = f"fiscal {m['fiscal_year']} ended {end}, before the cutoff"
            elif m["metric"] and ctx.store.get(company, m["metric"], m["fiscal_year"], m["period"]):
                bad = "a fact exists for the 'future' period"
        elif reason == "unreported_metric":
            if not trick.unreported(ctx, m["metric"], company):
                bad = f"{m['metric']} is reported by {company}"
        elif reason.startswith("false_premise_"):
            if m["item_code"] in ctx.eight_k_items(company):
                bad = f"{company} did file Item {m['item_code']}"
        elif reason == "outside_universe":
            if m["ticker"] in ctx.universe:
                bad = f"{m['ticker']} is in the universe"
        elif reason == "wrong_company_event":
            rec = next((r for r in ctx.manifest if r["accession"] == m["accession"]), None)
            if rec is None or rec["company_id"] != m["actual_company"]:
                bad = "accession does not belong to the stated company"
            elif m["item_code"] not in rec["items"]:
                bad = "the 8-K does not report the item"
            elif m["item_code"] in ctx.eight_k_items(company):
                bad = f"{company} also filed Item {m['item_code']}"
        elif reason == "false_number":
            own = ctx.store.get(company, m["metric"], m["fiscal_year"])
            other = ctx.store.get(m["stated_from"], m["metric"], m["fiscal_year"])
            if own is None or other is None:
                bad = "a value no longer resolves"
            elif not _same(own.value, m["actual_value"]) or not _same(
                other.value, m["stated_value"]
            ):
                bad = "stored values differ from FactsStore"
            elif abs(other.value - own.value) <= 0.25 * abs(own.value):
                bad = "stated value is too close to the real one"
        else:
            bad = f"unknown reason {reason}"
        if bad:
            errs.append(f"{item.item_id}: {bad}")
    return errs


def verify_events(ctx: GoldContext, items: list[EvalItem]) -> list[str]:
    errs = []
    by_acc = {r["accession"]: r for r in ctx.manifest if r["form"] == "8-K"}
    expected = {
        (r["company_id"], acc) for acc, r in by_acc.items() if set(EVENT_ITEMS) & set(r["items"])
    }
    got = set()
    for item in items:
        errs += _common(ctx, item)
        rec = by_acc.get(item.meta["accession"])
        if rec is None:
            errs.append(f"{item.item_id}: accession not in manifest")
            continue
        got.add((rec["company_id"], rec["accession"]))
        codes = [c for c in rec["items"] if c not in NOT_EVENTS]
        if [x["code"] for x in item.meta["items"]] != codes:
            errs.append(f"{item.item_id}: item codes differ from the manifest")
        if any(x["name"] != ITEM_NAMES.get(x["code"]) for x in item.meta["items"]):
            errs.append(f"{item.item_id}: item names differ from the SEC list")
        if not item.documents or any(d.doc_id not in ctx.doc_ids for d in item.documents):
            errs.append(f"{item.item_id}: missing parsed document")
    for company, acc in sorted(expected - got):
        errs.append(f"gold_event_labels: 8-K {company} {acc} has event items but no item")
    return errs


def verify_plan(ctx: GoldContext, items: list[EvalItem]) -> list[str]:
    errs = []
    allowed = set(plan.TOOLS) | set(plan.FUTURE_TOOLS)
    for item in items:
        errs += _common(ctx, item)
        if not item.expected_intents or set(item.expected_intents) - set(plan.INTENTS):
            errs.append(f"{item.item_id}: bad intents {item.expected_intents}")
        if not item.expected_tools or set(item.expected_tools) - allowed:
            errs.append(f"{item.item_id}: bad tools {item.expected_tools}")
        if set(item.meta["expected_tools_minimal"]) - set(plan.TOOLS):
            errs.append(f"{item.item_id}: minimal plan uses a future tool")
        for company in item.companies:
            for metric in item.meta["metrics"]:
                for year in item.meta["years"] or YEARS:
                    if ctx.store.get(company, metric, year) is None:
                        errs.append(f"{item.item_id}: {company} {metric} FY{year} unresolved")
    return errs


VERIFIERS: dict[str, Callable[[GoldContext, list[EvalItem]], list[str]]] = {
    "gold_num": verify_num,
    "gold_calc": verify_calc,
    "gold_trick": verify_trick,
    "gold_event_labels": verify_events,
    "gold_plan": verify_plan,
}
