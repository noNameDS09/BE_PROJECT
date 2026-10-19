"""Gold-Trick: questions whose correct answer is to refuse or correct the premise.

Every premise is checked against data before an item is written, and `gold verify` checks
it again: future periods have no facts and end after the data cutoff; "unreported" metrics
have no XBRL fact at all for that company; invented events have no matching 8-K item in
the corpus window; outside-universe companies are not among the 25; wrong-company
attributions point at a real 8-K filed by a different company.
"""

from datetime import date
from typing import Any

from loupe.datasets.gold.common import (
    DATA_CUTOFF,
    WINDOW,
    YEARS,
    GoldContext,
    fmt_date,
    fmt_usd,
    label_for,
)
from loupe.datasets.gold.sec_items import EVENT_PHRASES, ITEM_NAMES
from loupe.eval.schema import EvalItem, GoldEvidence

NAME = "gold_trick"
FUTURE_YEARS = (2027, 2028)

# Line items a company genuinely does not present (business model), as a curated allow-list.
# The builder additionally requires that FactsStore resolves nothing for FY2023-25 and that
# the facts table has no row for any of the metric's concepts for that company.
NOT_PRESENTED: dict[str, tuple[str, ...]] = {
    "operating_income": ("AXP", "JPM", "PFE", "ADM"),  # banks; pharma/agri skip the subtotal
    "gross_profit": ("AXP", "JPM", "BFH", "UNH", "MGM", "VZ", "RIG", "SHAK", "KR", "MMM", "PFE"),
    "rd_expense": ("AXP", "JPM", "BFH", "MGM", "ULTA", "BBY", "KR", "SAH", "SHAK", "CVS", "UNH"),
    "inventory": ("AXP", "JPM", "ADBE"),
    "cost_of_revenue": ("AXP", "JPM"),
}
NO_EVENT_TEMPLATES = {
    "1.03": (
        "Why did {co} file for Chapter 11 bankruptcy in {year}?",
        "What were the terms of {co}'s {year} bankruptcy reorganization?",
    ),
    "4.02": (
        "Explain {co}'s {year} restatement of its previously issued financial statements.",
        "Which periods did {co} restate in {year}, and why were its earlier financial "
        "statements declared unreliable?",
    ),
    "1.05": (
        "How did {co} respond to the material cybersecurity incident it disclosed in {year}?",
        "What did {co}'s {year} 8-K say about the impact of its cybersecurity breach?",
    ),
    "4.01": ("Why did {co} change its independent auditor in {year}?",),
}
NO_EVENT_COUNTS = {"1.03": 10, "4.02": 10, "1.05": 6, "4.01": 4}
MAX_UNREPORTED = 25  # at most 2 per company
MAX_WRONG_EVENTS = 20  # every rare item (1.03, 1.05, 4.01, 4.02) plus a sample of 2.04/2.06
RARE = ("1.03", "1.05", "4.01", "4.02")
OUTSIDE = (
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("TSLA", "Tesla"),
    ("NVDA", "NVIDIA"),
    ("AMZN", "Amazon"),
    ("WMT", "Walmart"),
    ("KO", "Coca-Cola"),
    ("NFLX", "Netflix"),
    ("INTC", "Intel"),
    ("META", "Meta Platforms"),
    ("GOOGL", "Alphabet"),
    ("COST", "Costco"),
    ("NKE", "Nike"),
    ("LMT", "Lockheed Martin"),
    ("GS", "Goldman Sachs"),
)
OUTSIDE_TEMPLATES = (
    "What was {co}'s total revenue in fiscal {year}?",
    "What risk factors did {co} highlight in its fiscal {year} 10-K?",
    "How did {co}'s net income change between fiscal {y0} and fiscal {year}?",
    "Did {co} report any material 8-K events in {year}?",
)
FUTURE_TEMPLATES = (
    ("revenue", "FY", "What was {co}'s total revenue for fiscal {year}?"),
    ("net_income", "Q2", "How much net income did {co} report in Q2 of fiscal {year}?"),
    ("eps_diluted", "FY", "What diluted EPS did {co} report for fiscal year {year}?"),
    ("operating_cash_flow", "FY", "How much operating cash flow did {co} generate in FY{year}?"),
    (None, "FY", "Summarize the results {co} reported in its fiscal {year} annual report."),
)


def _item(
    ctx: GoldContext, key: str, question: str, answer: str, reason: str, company: str | None,
    split: str, evidence: list[GoldEvidence] | None = None, **meta: Any,
) -> EvalItem:  # fmt: skip
    return EvalItem(
        item_id=f"{NAME}:{reason}:{key}",
        dataset=NAME,
        question=question,
        kind="refusal",
        answer=answer,
        mode="corpus",
        evidence=evidence or [],
        companies=[company] if company else [],
        split=split,  # type: ignore[arg-type]
        category=reason,
        meta={"reason": reason, **meta},
    )


def future_periods(ctx: GoldContext) -> list[EvalItem]:
    items = []
    for company in sorted(ctx.universe):
        rng = ctx.rng(NAME, "future", company)
        metric, period, template = rng.choice(FUTURE_TEMPLATES)
        year = rng.choice(FUTURE_YEARS)
        cal = ctx.store.calendar(company)
        latest = max(cal.fy_label(e) for e in cal.fy_ends)
        if metric and ctx.store.get(company, metric, year, period) is not None:  # type: ignore[arg-type]
            continue
        co = ctx.name(company)
        items.append(
            _item(
                ctx,
                f"{company}:FY{year}:{period}",
                template.format(co=co, year=year),
                f"Refuse: {co}'s fiscal {year} has not ended or been reported as of the data "
                f"cutoff ({DATA_CUTOFF.isoformat()}); the latest fiscal year with a 10-K is "
                f"FY{latest}. The answer must not invent figures.",
                "future_period",
                company,
                ctx.split(company),
                metric=metric,
                period=period,
                fiscal_year=year,
                latest_reported_fy=latest,
                data_cutoff=DATA_CUTOFF.isoformat(),
            )
        )
    return items


def concept_rows(ctx: GoldContext, company: str, metric: str) -> int:
    n = 0
    for concept in ctx.store.metrics[metric].concepts:
        taxonomy, name = concept.split(":", 1) if ":" in concept else ("us-gaap", concept)
        n += ctx.store.con.execute(
            "SELECT count(*) FROM facts WHERE company_id = ? AND taxonomy = ? AND concept = ?",
            [company, taxonomy, name],
        ).fetchone()[0]
    return n


def unreported(ctx: GoldContext, metric: str, company: str) -> bool:
    if any(ctx.store.get(company, metric, y) for y in YEARS):
        return False
    return concept_rows(ctx, company, metric) == 0


def unreported_metrics(ctx: GoldContext) -> list[EvalItem]:
    candidates = [
        (metric, company)
        for metric, companies in NOT_PRESENTED.items()
        for company in companies
        if company in ctx.universe and unreported(ctx, metric, company)
    ]
    ctx.rng(NAME, "unreported").shuffle(candidates)
    per_company: dict[str, int] = {}
    chosen = []
    for metric, company in candidates:
        if len(chosen) < MAX_UNREPORTED and per_company.get(company, 0) < 2:
            chosen.append((metric, company))
            per_company[company] = per_company.get(company, 0) + 1
    items = []
    for metric, company in sorted(chosen):
        label = {"rd_expense": "research and development expense"}.get(metric)
        label = label or metric.replace("_", " ")
        rng = ctx.rng(NAME, "unreported", company, metric)
        year = rng.choice(YEARS)
        co = ctx.name(company)
        q = rng.choice(
            (
                "What was {co}'s {label} in fiscal {year}? Answer in USD millions.",
                "How much {label} did {co} report for FY{year}?",
                "By how much did {co}'s {label} change from fiscal {y0} to fiscal {year}?",
            )
        ).format(co=co, label=label, year=year, y0=year - 1)
        concepts = ctx.store.metrics[metric].concepts
        items.append(
            _item(
                ctx,
                f"{company}:{metric}",
                q,
                f"Correct the premise: {co} does not present {label} as a line item in its "
                f"financial statements (no XBRL fact tagged {', '.join(concepts)} in any "
                f"of its filings). Say it is not reported instead of estimating a number; "
                f"a related reported figure may be offered, clearly labelled.",
                "unreported_metric",
                company,
                ctx.split(company),
                metric=metric,
                concepts=concepts,
                fiscal_year=year,
            )
        )
    return items


def invented_events(ctx: GoldContext) -> list[EvalItem]:
    items = []
    for code, n in NO_EVENT_COUNTS.items():
        clean = [c for c in sorted(ctx.universe) if code not in ctx.eight_k_items(c)]
        rng = ctx.rng(NAME, "no_event", code)
        for company in sorted(rng.sample(clean, min(n, len(clean)))):
            year = rng.choice(YEARS)
            co = ctx.name(company)
            filed = sum(
                1 for r in ctx.manifest if r["company_id"] == company and r["form"] == "8-K"
            )
            items.append(
                _item(
                    ctx,
                    f"{company}:{code}",
                    rng.choice(NO_EVENT_TEMPLATES[code]).format(co=co, year=year),
                    f"Correct the premise: none of {co}'s {filed} 8-Ks filed between "
                    f"{WINDOW[0].isoformat()} and {WINDOW[1].isoformat()} reports Item {code} "
                    f"({ITEM_NAMES[code]}). There is no such {year} event to explain.",
                    f"false_premise_{code.replace('.', '_')}",
                    company,
                    ctx.split(company),
                    item_code=code,
                    item_name=ITEM_NAMES[code],
                    eight_ks_checked=filed,
                    window=[WINDOW[0].isoformat(), WINDOW[1].isoformat()],
                    fiscal_year=year,
                )
            )
    return items


def outside_universe(ctx: GoldContext) -> list[EvalItem]:
    items = []
    for ticker, co in OUTSIDE:
        if ticker in ctx.universe:
            continue
        rng = ctx.rng(NAME, "outside", ticker)
        year = rng.choice((2024, 2025))
        split = "dev" if rng.random() < 8 / 25 else "test"
        items.append(
            _item(
                ctx,
                ticker,
                rng.choice(OUTSIDE_TEMPLATES).format(co=co, year=year, y0=year - 1),
                f"Decline: {co} ({ticker}) is not one of the 25 companies covered by the corpus, "
                f"so no cited answer can be given; say it is outside coverage rather than "
                f"answering from memory.",
                "outside_universe",
                None,
                split,
                ticker=ticker,
                company_name=co,
            )
        )
    return items


def wrong_company(ctx: GoldContext) -> list[EvalItem]:
    """A real risk 8-K attributed to another company (from the same split)."""
    items = []
    events = [
        (r, code)
        for r in ctx.manifest
        if r["form"] == "8-K"
        for code in r["items"]
        if code in EVENT_PHRASES
    ]
    events.sort(key=lambda e: (e[0]["filing_date"], e[0]["accession"], e[1]))
    rare = [e for e in events if e[1] in RARE]
    common = [e for e in events if e[1] not in RARE]
    k = max(0, min(len(common), MAX_WRONG_EVENTS - len(rare)))
    sample = ctx.rng(NAME, "wrong_events").sample(common, k)
    events = [e for e in events if e in rare or e in sample]
    for r, code in events:
        right = r["company_id"]
        rng = ctx.rng(NAME, "wrong", r["accession"], code)
        pool = [
            c
            for c in sorted(ctx.universe)
            if c != right and ctx.split(c) == ctx.split(right) and code not in ctx.eight_k_items(c)
        ]
        if not pool:
            continue
        wrong = rng.choice(pool)
        filed = fmt_date(date.fromisoformat(r["filing_date"]))
        q = rng.choice(
            (
                "In its 8-K filed on {d}, {w} disclosed {e}. What did {w} say about it?",
                "What was behind {w}'s 8-K of {d} reporting {e}?",
            )
        ).format(d=filed, w=ctx.name(wrong), e=EVENT_PHRASES[code])
        items.append(
            _item(
                ctx,
                f"{wrong}:{r['accession']}:{code}",
                q,
                f"Correct the attribution: the 8-K filed on {filed} reporting Item {code} "
                f"({ITEM_NAMES[code]}) was filed by {ctx.name(right)} (accession "
                f"{r['accession']}), not {ctx.name(wrong)}; {ctx.name(wrong)} filed no Item "
                f"{code} 8-K between {WINDOW[0].isoformat()} and {WINDOW[1].isoformat()}.",
                "wrong_company_event",
                wrong,
                ctx.split(wrong),
                evidence=[
                    GoldEvidence(
                        doc_id=ctx.doc_id(right, "8-K", r["accession"]),
                        accession=r["accession"],
                        item=code,
                    )
                ],
                item_code=code,
                actual_company=right,
                accession=r["accession"],
                filing_date=r["filing_date"],
                url=r["url"],
            )
        )
    return items


def wrong_numbers(ctx: GoldContext, n: int = 10) -> list[EvalItem]:
    """Another company's real FY revenue stated as this company's (values differ by > 25%)."""
    items = []
    rng = ctx.rng(NAME, "wrong_number")
    companies = sorted(ctx.universe)
    rng.shuffle(companies)
    for wrong in companies:
        if len(items) >= n:
            break
        year = rng.choice(YEARS)
        own = ctx.store.get(wrong, "revenue", year)
        pool = [c for c in sorted(ctx.universe) if c != wrong and ctx.split(c) == ctx.split(wrong)]
        right = rng.choice(pool)
        other = ctx.store.get(right, "revenue", year)
        if own is None or other is None or abs(other.value - own.value) <= 0.25 * abs(own.value):
            continue
        stated = fmt_usd(other.value, "billions")
        co = ctx.name(wrong)
        q = rng.choice(
            (
                "{co} reported {label} of {v} for fiscal {y}. What drove that result?",
                "Given that {co}'s fiscal {y} {label} was {v}, how did it compare with the "
                "prior year?",
            )
        ).format(co=co, label=label_for(own), v=stated, y=year)
        items.append(
            _item(
                ctx,
                f"{wrong}:revenue:FY{year}",
                q,
                f"Correct the premise: {co}'s fiscal {year} {label_for(own)} was "
                f"{fmt_usd(own.value, 'billions')}, not {stated} (that figure is "
                f"{ctx.name(right)}'s). The answer should state the correct value with its "
                f"source before discussing drivers.",
                "false_number",
                wrong,
                ctx.split(wrong),
                evidence=[
                    GoldEvidence(
                        doc_id=ctx.doc_id(wrong, own.form, own.accession), accession=own.accession
                    )
                ],
                metric="revenue",
                fiscal_year=year,
                stated_value=other.value,
                stated_from=right,
                actual_value=own.value,
                actual_accession=own.accession,
                actual_concept=own.concept,
            )
        )
    return items


def build(ctx: GoldContext) -> list[EvalItem]:
    return [
        *future_periods(ctx),
        *unreported_metrics(ctx),
        *invented_events(ctx),
        *outside_universe(ctx),
        *wrong_company(ctx),
        *wrong_numbers(ctx),
    ]
