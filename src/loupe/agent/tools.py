"""The tools every orchestration arm shares.

Each call returns plain text for the model and records evidence in the run's ledger
([E#] ids), so whatever the model cites can be traced and checked. Numbers always come
from XBRL facts or code (calculator, forecast, distress score), never from the model.
"""

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from loupe.agent.evidence import Ledger
from loupe.core.schemas import Citation, Company
from loupe.index.retriever import Retriever
from loupe.index.search import SearchFilter
from loupe.tools import charts
from loupe.tools.calc import CalcError, calculate
from loupe.tools.distress import altman_z2
from loupe.tools.facts import FactResult, FactsStore
from loupe.tools.forecast import forecast


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


STR = {"type": "string"}
INT = {"type": "integer"}
TICKERS = {"type": "array", "items": STR, "description": "Tickers, e.g. ['AMD','PEP']"}
PERIOD = {"type": "string", "enum": ["FY", "Q1", "Q2", "Q3", "Q4"]}
YEARS = {"type": "array", "items": INT, "description": "Fiscal years, e.g. [2022, 2023, 2024]"}

TOOL_SPECS: list[dict[str, Any]] = [
    _fn(
        "search_filings",
        "Search SEC filings (10-K, 10-Q, 8-K, press releases) for passages. Use for narrative "
        "questions: risks, reasons, events, guidance, management commentary.",
        {
            "query": STR,
            "companies": TICKERS,
            "forms": {"type": "array", "items": STR, "description": "10-K, 10-Q, 8-K, EX-99.1"},
            "items": {
                "type": "array",
                "items": STR,
                "description": "Sections, e.g. 1A, 7, I-2, 2.02",
            },
            "period_from": {"type": "string", "description": "YYYY-MM-DD"},
            "period_to": {"type": "string", "description": "YYYY-MM-DD"},
        },
        ["query"],
    ),
    _fn(
        "get_financial_metric",
        "Exact reported value of one metric (XBRL) for a company's fiscal year or quarter. "
        "Always use this for numbers instead of reading them from text.",
        {"company": STR, "metric": STR, "fiscal_year": INT, "period": PERIOD},
        ["company", "metric", "fiscal_year"],
    ),
    _fn(
        "compare_companies",
        "The same metric for several companies and one fiscal year, as a table.",
        {"companies": TICKERS, "metric": STR, "fiscal_year": INT, "period": PERIOD},
        ["companies", "metric", "fiscal_year"],
    ),
    _fn(
        "make_chart",
        "Chart a metric over fiscal years for one or more companies (line or bar). The chart is "
        "built from exact XBRL values and shown to the user with the answer.",
        {
            "companies": TICKERS,
            "metric": STR,
            "years": YEARS,
            "kind": {"type": "string", "enum": ["line", "bar"]},
            "period": PERIOD,
        },
        ["companies", "metric", "years"],
    ),
    _fn(
        "forecast_metric",
        "Project a metric forward 1-3 fiscal years from its reported history. Reports the method, "
        "an 80% range and its backtest error next to a naive baseline. Statistical projection "
        "only, not investment advice.",
        {
            "company": STR,
            "metric": STR,
            "horizon": {"type": "integer", "minimum": 1, "maximum": 3},
            "history_from": INT,
        },
        ["company", "metric"],
    ),
    _fn(
        "distress_score",
        "Altman Z'' financial-distress score for a company and fiscal year, from reported book "
        "values, with its inputs; plus the company's 8-K risk events. Not applicable to banks.",
        {"company": STR, "fiscal_year": INT},
        ["company", "fiscal_year"],
    ),
    _fn(
        "list_events",
        "Material events a company reported on Form 8-K (item codes such as 1.05 cyber incident, "
        "4.02 restatement, 2.06 impairment, 5.02 officer change), with dates.",
        {
            "company": STR,
            "items": {"type": "array", "items": STR, "description": "8-K item codes to keep"},
            "risk_only": {"type": "boolean"},
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
        },
        ["company"],
    ),
    _fn(
        "calculate",
        "Evaluate an arithmetic expression exactly. Helpers: pct_change(old, new), "
        "cagr(start, end, years), ratio(a, b), round, min, max, abs, sqrt.",
        {"expression": STR},
        ["expression"],
    ),
    _fn("list_companies", "List the companies in the corpus with tickers and sectors.", {}, []),
]


def fmt_value(value: float, unit: str) -> str:
    if unit == "USD" and abs(value) >= 1e9:
        return f"${value / 1e9:,.3f} billion"
    if unit == "USD" and abs(value) >= 1e6:
        return f"${value / 1e6:,.1f} million"
    if unit == "USD":
        return f"${value:,.2f}"
    if unit == "USD/shares":
        return f"${value:,.2f} per share"
    return f"{value:,.4g} {unit}"


class ToolBox:
    def __init__(
        self,
        retriever: Retriever,
        facts: FactsStore,
        companies: list[Company],
        snippet_chars: int = 1200,
    ):
        self.retriever = retriever
        self.facts = facts
        self.companies = companies
        self.sectors = {c.id: c.sector for c in companies}
        self.snippet_chars = snippet_chars
        self._dispatch: dict[str, Callable[..., str]] = {
            spec["function"]["name"]: getattr(self, spec["function"]["name"]) for spec in TOOL_SPECS
        }

    @property
    def metric_names(self) -> list[str]:
        return sorted(self.facts.metrics)

    def specs(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        specs = json.loads(json.dumps(TOOL_SPECS))
        for spec in specs:
            props = spec["function"]["parameters"]["properties"]
            if "metric" in props:
                props["metric"] = {"type": "string", "enum": self.metric_names}
        return [s for s in specs if names is None or s["function"]["name"] in names]

    def call(self, name: str, args: dict[str, Any], ledger: Ledger) -> str:
        fn = self._dispatch.get(name)
        if fn is None:
            return f"ERROR: unknown tool {name}. Available: {', '.join(self._dispatch)}"
        try:
            return fn(ledger=ledger, **args)
        except (TypeError, ValueError, KeyError) as exc:
            return f"ERROR: bad arguments for {name}: {exc}"

    # --- evidence helpers -------------------------------------------------------------

    def _fact_text(self, r: FactResult) -> str:
        return (
            f"{r.company_id} {r.metric} fiscal {r.fiscal_year} {r.fiscal_period}: "
            f"{fmt_value(r.value, r.unit)} (exact {r.value:,.6g} {r.unit}; concept {r.concept}; "
            f"period {r.period_start} to {r.period_end}; {r.form} accession {r.accession}"
            + (f"; derived as {r.derived}" if r.derived else "")
            + ")"
        )

    def _add_fact(self, ledger: Ledger, r: FactResult) -> str:
        ev = ledger.add(
            "fact", self._fact_text(r), Citation(fact_id=r.accession, url=r.url), r.value
        )
        return ev.id

    def _check_metric(self, metric: str) -> str | None:
        if metric not in self.facts.metrics:
            return f"ERROR: unknown metric {metric}. Known: {', '.join(self.metric_names)}"
        return None

    # --- tools ------------------------------------------------------------------------

    def search_filings(
        self,
        ledger: Ledger,
        query: str,
        companies: list[str] | None = None,
        forms: list[str] | None = None,
        items: list[str] | None = None,
        period_from: str | None = None,
        period_to: str | None = None,
        extra_queries: list[str] | None = None,
    ) -> str:
        f = SearchFilter(
            companies=[c.upper() for c in companies] if companies else None,
            forms=forms or None,
            items=items or None,
            period_from=date.fromisoformat(period_from) if period_from else None,
            period_to=date.fromisoformat(period_to) if period_to else None,
        )
        hits = self.retriever.retrieve(query, filter=f, extra_queries=extra_queries)
        if not hits:
            return "No passages found for this query and filter."
        out = []
        for h in hits:
            c, m = h.chunk, h.chunk.metadata
            text = c.text[: self.snippet_chars]
            citation = Citation(
                doc_id=c.doc_id,
                chunk_id=c.chunk_id,
                start_char=c.start_char,
                end_char=c.end_char,
                url=m.get("url"),
            )
            ev = ledger.add("chunk", text, citation)
            items_s = ",".join(m.get("items") or []) or "cover"
            out.append(
                f"[{ev.id}] {c.company_id} {m.get('form')} period {m.get('period_end')} "
                f"item {items_s}\n{text}"
            )
        return "\n\n".join(out)

    def get_financial_metric(
        self, ledger: Ledger, company: str, metric: str, fiscal_year: int, period: str = "FY"
    ) -> str:
        if err := self._check_metric(metric):
            return err
        r = self.facts.get(company.upper(), metric, int(fiscal_year), period)  # type: ignore[arg-type]
        if r is None:
            return (
                f"NOT REPORTED: no {metric} found for {company.upper()} fiscal {fiscal_year} "
                f"{period} in XBRL. Do not estimate it."
            )
        eid = self._add_fact(ledger, r)
        return f"[{eid}] {self._fact_text(r)}"

    def compare_companies(
        self,
        ledger: Ledger,
        companies: list[str],
        metric: str,
        fiscal_year: int,
        period: str = "FY",
    ) -> str:
        if err := self._check_metric(metric):
            return err
        lines = [f"{metric}, fiscal {fiscal_year} {period}:"]
        for c in companies:
            r = self.facts.get(c.upper(), metric, int(fiscal_year), period)  # type: ignore[arg-type]
            if r is None:
                lines.append(f"- {c.upper()}: not reported")
            else:
                lines.append(
                    f"- [{self._add_fact(ledger, r)}] {c.upper()}: {fmt_value(r.value, r.unit)}"
                )
        return "\n".join(lines)

    def make_chart(
        self,
        ledger: Ledger,
        companies: list[str],
        metric: str,
        years: list[int],
        kind: str = "line",
        period: str = "FY",
    ) -> str:
        if err := self._check_metric(metric):
            return err
        series, ids = {}, []
        for c in companies:
            rows = self.facts.series(c.upper(), metric, [int(y) for y in years], period)  # type: ignore[arg-type]
            if rows:
                series[c.upper()] = rows
                ids += [self._add_fact(ledger, r) for r in rows]
        if not series:
            return f"NOT REPORTED: no {metric} values for {companies} in {years}."
        title = f"{metric.replace('_', ' ').title()} ({', '.join(series)})"
        ledger.charts.append(
            {
                "title": title,
                "figure": charts.series_figure(title, series, kind),
                "evidence_ids": ids,
            }
        )
        points = "; ".join(
            f"{c} " + ", ".join(f"FY{r.fiscal_year} {fmt_value(r.value, r.unit)}" for r in rows)
            for c, rows in series.items()
        )
        return f"Chart created from {', '.join(f'[{i}]' for i in ids)}: {points}"

    def forecast_metric(
        self, ledger: Ledger, company: str, metric: str, horizon: int = 1, history_from: int = 2016
    ) -> str:
        if err := self._check_metric(metric):
            return err
        cal = self.facts.calendar(company.upper())
        if not cal.fy_ends:
            return f"NOT REPORTED: no annual history for {company.upper()}."
        last_fy = cal.fy_label(cal.fy_ends[-1])
        rows = self.facts.series(
            company.upper(), metric, list(range(int(history_from), last_fy + 1))
        )
        if len(rows) < 3:
            n = len(rows)
            return f"NOT ENOUGH HISTORY: only {n} annual values of {metric} for {company.upper()}."
        fc = forecast([r.value for r in rows], int(max(1, min(3, horizon))))
        ids = [self._add_fact(ledger, r) for r in rows]
        unit = rows[0].unit
        proj = "; ".join(
            f"FY{rows[-1].fiscal_year + i + 1}: {fmt_value(p, unit)} "
            f"(80% range {fmt_value(lo, unit)} to {fmt_value(hi, unit)})"
            for i, (p, lo, hi) in enumerate(zip(fc.points, fc.lower, fc.upper, strict=True))
        )
        text = (
            f"Forecast of {company.upper()} {metric} using {fc.method} on {fc.n_history} "
            f"annual values "
            f"(FY{rows[0].fiscal_year}-FY{rows[-1].fiscal_year}): {proj}. Backtest error (MAPE): "
            f"{fc.backtest_mape:.1f}% vs naive {fc.naive_mape:.1f}%. {fc.note}".strip()
        )
        ev = ledger.add("calc", text, Citation(), fc.points[0])
        title = f"{company.upper()} {metric.replace('_', ' ')}: history and {fc.method} forecast"
        ledger.charts.append(
            {
                "title": title,
                "figure": charts.series_figure(
                    title, {company.upper(): rows}, "line", {company.upper(): fc}
                ),
                "evidence_ids": [*ids, ev.id],
            }
        )
        return f"[{ev.id}] {text} History: {', '.join(f'[{i}]' for i in ids)}"

    def distress_score(self, ledger: Ledger, company: str, fiscal_year: int) -> str:
        cid = company.upper()
        res = altman_z2(self.facts, cid, int(fiscal_year), self.sectors.get(cid))
        ids = [self._add_fact(ledger, r) for r in res.inputs]
        events = (
            self.facts.con.execute(
                "SELECT item, item_name, count(*) FROM filing_events WHERE company_id = ? AND risk "
                "GROUP BY 1, 2 ORDER BY 1",
                [cid],
            ).fetchall()
            if self._has_events()
            else []
        )
        ev_text = "; ".join(f"{i} {n} x{k}" for i, n, k in events) or "none in the corpus window"
        if res.z_score is None:
            reason = res.note or f"missing inputs: {', '.join(res.missing)}"
            return (
                f"Z'' not computed for {cid} FY{fiscal_year} ({reason}). "
                f"8-K risk events: {ev_text}."
            )
        text = (
            f"{cid} FY{fiscal_year} Altman Z'' = {res.z_score:.2f} ({res.zone} zone; >2.6 safe, "
            f"1.1-2.6 grey, <1.1 distress). Components {res.components}. "
            f"8-K risk events: {ev_text}."
        )
        ev = ledger.add("calc", text, Citation(), res.z_score)
        return f"[{ev.id}] {text} Inputs: {', '.join(f'[{i}]' for i in ids)}"

    def _has_events(self) -> bool:
        return bool(
            self.facts.con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name = 'filing_events'"
            ).fetchone()[0]
        )

    def list_events(
        self,
        ledger: Ledger,
        company: str,
        items: list[str] | None = None,
        risk_only: bool = False,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        if not self._has_events():
            return "ERROR: events table not built (run `loupe sec events`)."
        sql = (
            "SELECT filing_date, item, item_name, accession, url FROM filing_events "
            "WHERE company_id = ?"
        )
        params: list[Any] = [company.upper()]
        if items:
            sql += f" AND item IN ({', '.join('?' * len(items))})"
            params += items
        if risk_only:
            sql += " AND risk"
        if date_from:
            sql += " AND filing_date >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND filing_date <= ?"
            params.append(date_to)
        rows = self.facts.con.execute(
            sql + " AND item <> '9.01' ORDER BY filing_date", params
        ).fetchall()
        if not rows:
            return f"No matching 8-K events for {company.upper()}."
        lines = []
        for filed, item, name, accession, url in rows[:60]:
            text = (
                f"{company.upper()} 8-K filed {filed}: Item {item} {name} (accession {accession})"
            )
            ev = ledger.add(
                "chunk", text, Citation(doc_id=f"{company.upper()}_8-K_{accession}", url=url)
            )
            lines.append(f"[{ev.id}] {text}")
        more = f"\n... {len(rows) - 60} more" if len(rows) > 60 else ""
        return "\n".join(lines) + more

    def calculate(self, ledger: Ledger, expression: str) -> str:
        try:
            value = calculate(expression)
        except CalcError as exc:
            return f"ERROR: {exc}"
        ev = ledger.add("calc", f"{expression} = {value:,.6g}", Citation(), value=value)
        return f"[{ev.id}] {expression} = {value:,.6g}"

    def list_companies(self, ledger: Ledger) -> str:
        return "\n".join(f"{c.id}: {c.name} ({c.sector})" for c in self.companies)
