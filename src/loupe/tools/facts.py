"""Exact financial numbers from XBRL, each with the filing it came from.

Fiscal-year labels differ between companies (Ulta's "fiscal 2024" ends February 2025,
Best Buy calls the same period "fiscal 2025"), and the `fy` field in SEC's company
facts is occasionally wrong (Kroger). So each company's fiscal calendar is rebuilt
from its 10-K period ends, labelled with the offset its latest 10-K uses, and
quarters are numbered by position inside the fiscal year.
"""

from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import duckdb
import yaml
from pydantic import BaseModel

Period = Literal["FY", "Q1", "Q2", "Q3", "Q4"]
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/"
# quarters up to 16 weeks (Kroger Q1); nine months from 36 weeks (PepsiCo) to 40 weeks (Kroger)
DAYS = {"FY": (350, 380), "Q": (80, 115), "9M": (245, 290)}
TOLERANCE = timedelta(days=7)


class MetricSpec(BaseModel):
    kind: Literal["duration", "instant"]
    unit: str
    concepts: list[str]


class FactResult(BaseModel):
    company_id: str
    metric: str
    fiscal_year: int
    fiscal_period: Period
    value: float
    unit: str
    concept: str
    period_start: date | None
    period_end: date
    accession: str
    form: str | None
    filed: date | None
    url: str
    derived: str | None = None  # e.g. "FY - 9M YTD" for a Q4 value nobody reports directly


def load_metrics(path: Path) -> dict[str, MetricSpec]:
    return {k: MetricSpec(**v) for k, v in yaml.safe_load(path.read_text())["metrics"].items()}


def _split(concept: str) -> tuple[str, str]:
    return tuple(concept.split(":", 1)) if ":" in concept else ("us-gaap", concept)  # type: ignore[return-value]


def _adj_year(d: date) -> int:
    # 52/53-week years ending in the first days of January belong to the previous year
    return (d - TOLERANCE).year


class FiscalCalendar:
    def __init__(self, fy_ends: list[date], offset: int, quarter_ends: list[date] | None = None):
        self.fy_ends = sorted(fy_ends)
        self.offset = offset
        self.quarter_ends = sorted(quarter_ends or [])  # actual 10-Q period ends

    def fy_label(self, fy_end: date) -> int:
        return _adj_year(fy_end) + self.offset

    def fy_end_for(self, fiscal_year: int) -> date | None:
        for end in self.fy_ends:
            if self.fy_label(end) == fiscal_year:
                return end
        if self.fy_ends:  # extrapolate one year past the last 10-K
            last = self.fy_ends[-1]
            if fiscal_year == self.fy_label(last) + 1:
                return last + timedelta(days=364)
        return None

    def quarter_end(self, fiscal_year: int, q: int) -> date | None:
        """End of fiscal quarter q: the q-th 10-Q period end inside the fiscal year when known
        (quarters can be 12 or 16 weeks), else an estimate of 13 weeks per quarter."""
        end = self.fy_end_for(fiscal_year)
        if end is None:
            return None
        if q == 4:
            return end
        start = self.fy_end_for(fiscal_year - 1) or end - timedelta(days=364)
        inside = [
            d
            for d in self.quarter_ends
            if start + timedelta(days=20) < d < end - timedelta(days=20)
        ]
        if len(inside) == 3:
            return inside[q - 1]
        return end - timedelta(days=91 * (4 - q))

    def label(self, period_end: date) -> tuple[int, Period] | None:
        """Fiscal year and quarter of a quarter-end (or year-end) date."""
        ends = self.fy_ends + ([self.fy_ends[-1] + timedelta(days=364)] if self.fy_ends else [])
        for end in ends:
            if period_end <= end + TOLERANCE:
                q = 4 - round((end - period_end).days / 91)
                if 1 <= q <= 4:
                    return self.fy_label(end), ("FY" if q == 4 else f"Q{q}")  # type: ignore[return-value]
                return None
        return None


class FactsStore:
    def __init__(self, db_path: Path, metrics: dict[str, MetricSpec], ciks: dict[str, str]):
        self.con = duckdb.connect(str(db_path), read_only=True)
        self.metrics = metrics
        self.ciks = ciks
        self._calendars: dict[str, FiscalCalendar] = {}

    def calendar(self, company_id: str) -> FiscalCalendar:
        if company_id not in self._calendars:
            rows = self.con.execute(
                """
                SELECT accession, any_value(fiscal_year), max(period_end), max(filed)
                FROM facts
                WHERE company_id = ? AND form = '10-K' AND fiscal_period = 'FY'
                  AND fiscal_year IS NOT NULL AND period_start IS NOT NULL
                  AND datediff('day', period_start, period_end) BETWEEN 350 AND 380
                GROUP BY accession
                """,
                [company_id],
            ).fetchall()
            ends = sorted({r[2] for r in rows})
            latest = max(rows, key=lambda r: r[3]) if rows else None
            offset = latest[1] - _adj_year(latest[2]) if latest else 0
            # if the latest filing disagrees with most filings, trust the majority
            votes = Counter(r[1] - _adj_year(r[2]) for r in rows)
            if votes and votes.most_common(1)[0][1] > len(rows) / 2:
                offset = votes.most_common(1)[0][0]
            quarters = self.con.execute(
                """
                SELECT max(period_end) FROM facts
                WHERE company_id = ? AND form = '10-Q' AND period_start IS NOT NULL
                  AND datediff('day', period_start, period_end) BETWEEN 80 AND 115
                GROUP BY accession
                """,
                [company_id],
            ).fetchall()
            self._calendars[company_id] = FiscalCalendar(ends, offset, [q[0] for q in quarters])
        return self._calendars[company_id]

    def _rows(
        self,
        company_id: str,
        concept: str,
        unit: str,
        end: date,
        kind: str,
        days: tuple[int, int] | None,
    ):
        taxonomy, name = _split(concept)
        sql = """
            SELECT value, period_start, period_end, accession, form, filed
            FROM facts_latest
            WHERE company_id = ? AND taxonomy = ? AND concept = ? AND unit = ?
              AND period_end BETWEEN ? AND ?
        """
        params = [company_id, taxonomy, name, unit, end - TOLERANCE, end + TOLERANCE]
        if kind == "instant":
            sql += " AND period_start IS NULL"
        else:
            sql += (
                " AND period_start IS NOT NULL"
                " AND datediff('day', period_start, period_end) BETWEEN ? AND ?"
            )
            params += list(days)  # type: ignore[arg-type]
        return self.con.execute(sql + " ORDER BY filed DESC LIMIT 1", params).fetchall()

    def _result(self, company_id, metric, fy, fp, spec, concept, row, derived=None) -> FactResult:
        value, start, end, accession, form, filed = row
        return FactResult(
            company_id=company_id,
            metric=metric,
            fiscal_year=fy,
            fiscal_period=fp,
            value=value,
            unit=spec.unit,
            concept=concept,
            period_start=start,
            period_end=end,
            accession=accession,
            form=form,
            filed=filed,
            url=ARCHIVE.format(cik=int(self.ciks[company_id]), folder=accession.replace("-", "")),
            derived=derived,
        )

    def get(
        self, company_id: str, metric: str, fiscal_year: int, period: Period = "FY"
    ) -> FactResult | None:
        spec = self.metrics[metric]
        cal = self.calendar(company_id)
        end = (
            cal.fy_end_for(fiscal_year)
            if period in ("FY", "Q4")
            else cal.quarter_end(fiscal_year, int(period[1]))
        )
        if end is None:
            return None
        for concept in spec.concepts:
            if spec.kind == "instant":
                rows = self._rows(company_id, concept, spec.unit, end, "instant", None)
            elif period == "FY":
                rows = self._rows(company_id, concept, spec.unit, end, "duration", DAYS["FY"])
            else:
                rows = self._rows(company_id, concept, spec.unit, end, "duration", DAYS["Q"])
                if not rows and period == "Q4" and "/" not in spec.unit:
                    # Q4 is rarely reported on its own: full year minus nine-month YTD.
                    # Not for per-share values (EPS), which don't add up across periods.
                    fy_rows = self._rows(
                        company_id, concept, spec.unit, end, "duration", DAYS["FY"]
                    )
                    q3_end = cal.quarter_end(fiscal_year, 3)
                    ytd = self._rows(company_id, concept, spec.unit, q3_end, "duration", DAYS["9M"])
                    if fy_rows and ytd:
                        v = fy_rows[0][0] - ytd[0][0]
                        row = (v, ytd[0][2] + timedelta(days=1), fy_rows[0][2], *fy_rows[0][3:])
                        return self._result(
                            company_id,
                            metric,
                            fiscal_year,
                            period,
                            spec,
                            concept,
                            row,
                            "FY - 9M YTD",
                        )
            if rows:
                return self._result(company_id, metric, fiscal_year, period, spec, concept, rows[0])
        return None

    def series(
        self, company_id: str, metric: str, years: list[int], period: Period = "FY"
    ) -> list[FactResult]:
        out = [self.get(company_id, metric, y, period) for y in years]
        return [r for r in out if r is not None]
