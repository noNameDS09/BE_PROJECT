"""The tools every orchestration arm shares: search, facts, calculator, company list.

Each call returns plain text for the model and records evidence in the run's ledger,
so whatever the model cites can be traced and checked.
"""

import json
from collections.abc import Callable
from datetime import date
from typing import Any

from loupe.agent.evidence import Ledger
from loupe.core.schemas import Citation, Company
from loupe.index.search import SearchFilter, SearchIndex
from loupe.tools.calc import CalcError, calculate
from loupe.tools.facts import FactsStore

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_filings",
            "description": (
                "Search SEC filings (10-K, 10-Q, 8-K, press releases) for passages. "
                "Use for narrative questions: risks, reasons, events, management commentary."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "companies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tickers",
                    },
                    "forms": {"type": "array", "items": {"type": "string"}},
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "e.g. 1A, 7, 2.02",
                    },
                    "period_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "period_to": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_metric",
            "description": (
                "Exact reported value of a financial metric from XBRL for a company's fiscal year "
                "or quarter. Always use this for numbers instead of reading them from text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Ticker"},
                    "metric": {"type": "string"},
                    "fiscal_year": {"type": "integer"},
                    "period": {"type": "string", "enum": ["FY", "Q1", "Q2", "Q3", "Q4"]},
                },
                "required": ["company", "metric", "fiscal_year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate an arithmetic expression exactly. Helpers: pct_change(old, new), "
                "cagr(start, end, years), ratio(a, b), round, min, max, abs, sqrt."
            ),
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_companies",
            "description": "List the companies in the corpus with tickers and sectors.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _fmt(value: float, unit: str) -> str:
    if unit == "USD" and abs(value) >= 1e6:
        return f"${value / 1e6:,.1f} million"
    if unit == "USD":
        return f"${value:,.2f}"
    return f"{value:,.4g} {unit}"


class ToolBox:
    def __init__(
        self,
        index: SearchIndex,
        facts: FactsStore,
        companies: list[Company],
        k: int = 8,
        snippet_chars: int = 1200,
    ):
        self.index = index
        self.facts = facts
        self.companies = companies
        self.k = k
        self.snippet_chars = snippet_chars
        self._dispatch: dict[str, Callable[..., str]] = {
            "search_filings": self.search_filings,
            "get_financial_metric": self.get_financial_metric,
            "calculate": self.calculate,
            "list_companies": self.list_companies,
        }

    @property
    def metric_names(self) -> list[str]:
        return sorted(self.facts.metrics)

    def specs(self) -> list[dict[str, Any]]:
        specs = json.loads(json.dumps(TOOL_SPECS))
        specs[1]["function"]["parameters"]["properties"]["metric"]["enum"] = self.metric_names
        return specs

    def call(self, name: str, args: dict[str, Any], ledger: Ledger) -> str:
        fn = self._dispatch.get(name)
        if fn is None:
            return f"ERROR: unknown tool {name}"
        try:
            return fn(ledger=ledger, **args)
        except TypeError as exc:
            return f"ERROR: bad arguments for {name}: {exc}"

    def search_filings(
        self,
        ledger: Ledger,
        query: str,
        companies: list[str] | None = None,
        forms: list[str] | None = None,
        items: list[str] | None = None,
        period_from: str | None = None,
        period_to: str | None = None,
    ) -> str:
        f = SearchFilter(
            companies=[c.upper() for c in companies] if companies else None,
            forms=forms or None,
            items=items or None,
            period_from=date.fromisoformat(period_from) if period_from else None,
            period_to=date.fromisoformat(period_to) if period_to else None,
        )
        hits = self.index.search(query, k=self.k, filter=f)
        if not hits:
            return "No passages found for this query and filter."
        out = []
        for h in hits:
            c, m = h.chunk, h.chunk.metadata
            text = c.text[: self.snippet_chars]
            ev = ledger.add(
                "chunk",
                text,
                Citation(
                    doc_id=c.doc_id,
                    chunk_id=c.chunk_id,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    url=m.get("url"),
                ),
            )
            items_s = ",".join(m.get("items") or []) or "cover"
            out.append(
                f"[{ev.id}] {c.company_id} {m.get('form')} period {m.get('period_end')} "
                f"item {items_s}\n{text}"
            )
        return "\n\n".join(out)

    def get_financial_metric(
        self, ledger: Ledger, company: str, metric: str, fiscal_year: int, period: str = "FY"
    ) -> str:
        if metric not in self.facts.metrics:
            return f"ERROR: unknown metric {metric}. Known: {', '.join(self.metric_names)}"
        r = self.facts.get(company.upper(), metric, int(fiscal_year), period)  # type: ignore[arg-type]
        if r is None:
            return (
                f"NOT REPORTED: no {metric} found for {company.upper()} fiscal {fiscal_year} "
                f"{period} in XBRL. Do not estimate it."
            )
        text = (
            f"{r.company_id} {metric} fiscal {r.fiscal_year} {r.fiscal_period}: "
            f"{_fmt(r.value, r.unit)} "
            f"(exact {r.value:,.6g} {r.unit}; concept {r.concept}; period {r.period_start} to "
            f"{r.period_end}; {r.form} accession {r.accession}"
            + (f"; derived as {r.derived}" if r.derived else "")
            + ")"
        )
        ev = ledger.add("fact", text, Citation(fact_id=r.accession, url=r.url), value=r.value)
        return f"[{ev.id}] {text}"

    def calculate(self, ledger: Ledger, expression: str) -> str:
        try:
            value = calculate(expression)
        except CalcError as exc:
            return f"ERROR: {exc}"
        ev = ledger.add("calc", f"{expression} = {value:,.6g}", Citation(), value=value)
        return f"[{ev.id}] {expression} = {value:,.6g}"

    def list_companies(self, ledger: Ledger) -> str:
        return "\n".join(f"{c.id}: {c.name} ({c.sector})" for c in self.companies)
