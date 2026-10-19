"""Small, transparent forecasting for annual or quarterly metrics (NumPy only).

Four candidate methods are backtested on the last points of the series (rolling
origin, one step ahead); the one with the lowest error is used, and its error is
always reported next to the naive baseline's, so a forecast never looks more
certain than its track record. Intervals come from the chosen method's backtest
errors, widening with the horizon.
"""

import math

import numpy as np
from pydantic import BaseModel

Z80 = 1.2816  # two-sided 80% interval


class Forecast(BaseModel):
    method: str
    horizon: int
    points: list[float]
    lower: list[float]
    upper: list[float]
    backtest_mape: float | None  # chosen method, %
    naive_mape: float | None  # naive baseline, %
    n_history: int
    note: str = ""


def _naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.repeat(y[-1], h)


def _drift(y: np.ndarray, h: int) -> np.ndarray:
    slope = (y[-1] - y[0]) / max(len(y) - 1, 1)
    return y[-1] + slope * np.arange(1, h + 1)


def _linear(y: np.ndarray, h: int) -> np.ndarray:
    x = np.arange(len(y))
    b, a = np.polyfit(x, y, 1)
    return a + b * np.arange(len(y), len(y) + h)


def _holt_damped(y: np.ndarray, h: int, alpha: float = 0.6, beta: float = 0.2, phi: float = 0.9):
    level, trend = y[0], (y[1] - y[0]) if len(y) > 1 else 0.0
    for v in y[1:]:
        prev = level
        level = alpha * v + (1 - alpha) * (level + phi * trend)
        trend = beta * (level - prev) + (1 - beta) * phi * trend
    damp = np.cumsum(phi ** np.arange(1, h + 1))
    return level + damp * trend


METHODS = {"naive": _naive, "drift": _drift, "linear_trend": _linear, "holt_damped": _holt_damped}
MIN_TRAIN = {"naive": 1, "drift": 2, "linear_trend": 3, "holt_damped": 3}


def _backtest(y: np.ndarray, method: str, folds: int) -> list[float]:
    """One-step-ahead percentage errors over the last `folds` points."""
    errs = []
    for t in range(len(y) - folds, len(y)):
        if t < MIN_TRAIN[method]:
            continue
        pred = METHODS[method](y[:t], 1)[0]
        if y[t] != 0:
            errs.append((pred - y[t]) / abs(y[t]) * 100)
    return errs


def forecast(history: list[float], horizon: int = 1) -> Forecast:
    y = np.asarray(history, dtype=float)
    if len(y) < 2:
        raise ValueError("need at least 2 historical points")
    folds = min(3, len(y) - 1)
    results = {}
    for name in METHODS:
        errs = _backtest(y, name, folds)
        if errs:
            results[name] = errs
    mape = {k: float(np.mean(np.abs(v))) for k, v in results.items()}
    best = min(mape, key=mape.get) if mape else "naive"
    points = METHODS[best](y, horizon)
    errs = np.asarray(results.get(best, [0.0]))
    sigma = float(np.sqrt(np.mean(errs**2))) / 100  # relative error scale
    widths = [abs(p) * sigma * Z80 * math.sqrt(i + 1) for i, p in enumerate(points)]
    note = "" if len(y) >= 5 else "Short history: treat this as indicative only."
    return Forecast(
        method=best,
        horizon=horizon,
        points=[float(p) for p in points],
        lower=[float(p - w) for p, w in zip(points, widths, strict=True)],
        upper=[float(p + w) for p, w in zip(points, widths, strict=True)],
        backtest_mape=mape.get(best),
        naive_mape=mape.get("naive"),
        n_history=len(y),
        note=note,
    )
