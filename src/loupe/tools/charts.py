"""Plotly figure specs built only from verified numbers (FactResults and forecasts)."""

from typing import Any

from loupe.tools.facts import FactResult
from loupe.tools.forecast import Forecast

PALETTE = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"]


def _scale(values: list[float], unit: str) -> tuple[list[float], str]:
    if unit != "USD":
        return values, unit
    top = max((abs(v) for v in values), default=0)
    if top >= 1e9:
        return [v / 1e9 for v in values], "USD billions"
    if top >= 1e6:
        return [v / 1e6 for v in values], "USD millions"
    return values, "USD"


def series_figure(
    title: str,
    series: dict[str, list[FactResult]],
    kind: str = "line",
    forecast: dict[str, Forecast] | None = None,
) -> dict[str, Any]:
    """series: label -> FactResults in period order. Optional forecast per label."""
    unit = next((r.unit for rs in series.values() for r in rs), "")
    all_vals = [r.value for rs in series.values() for r in rs]
    _, axis_unit = _scale(all_vals, unit)
    div = {"USD billions": 1e9, "USD millions": 1e6}.get(axis_unit, 1)
    data = []
    for i, (label, rows) in enumerate(series.items()):
        x = [
            f"FY{r.fiscal_year}"
            if r.fiscal_period == "FY"
            else f"{r.fiscal_year} {r.fiscal_period}"
            for r in rows
        ]
        y = [r.value / div for r in rows]
        color = PALETTE[i % len(PALETTE)]
        trace = {"name": label, "x": x, "y": y}
        if kind == "bar":
            data.append({**trace, "type": "bar", "marker": {"color": color}})
        else:
            data.append(
                {**trace, "type": "scatter", "mode": "lines+markers", "line": {"color": color}}
            )
        fc = (forecast or {}).get(label)
        if fc and rows:
            last = rows[-1]
            fx = [x[-1]] + [f"FY{last.fiscal_year + h}" for h in range(1, fc.horizon + 1)]
            fy = [y[-1]] + [p / div for p in fc.points]
            data.append(
                {"name": f"{label} forecast ({fc.method})", "x": fx, "y": fy, "type": "scatter",
                 "mode": "lines+markers", "line": {"color": color, "dash": "dash"}}
            )  # fmt: skip
            data.append(
                {"name": "80% range", "x": fx[1:] + fx[1:][::-1],
                 "y": [v / div for v in fc.upper] + [v / div for v in fc.lower][::-1],
                 "type": "scatter", "fill": "toself", "line": {"width": 0},
                 "fillcolor": "rgba(37,99,235,0.12)", "hoverinfo": "skip", "showlegend": True}
            )  # fmt: skip
    layout = {
        "title": {"text": title},
        "yaxis": {"title": {"text": axis_unit}},
        "barmode": "group",
        "margin": {"l": 60, "r": 20, "t": 50, "b": 40},
        "legend": {"orientation": "h"},
    }
    return {"data": data, "layout": layout}
