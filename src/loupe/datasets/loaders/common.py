"""Helpers shared by the public-dataset loaders: number parsing, table flattening, file reading."""

import json
import math
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SCALES = {
    "thousand": 1e3,
    "thousands": 1e3,
    "k": 1e3,
    "million": 1e6,
    "millions": 1e6,
    "mn": 1e6,
    "mm": 1e6,
    "m": 1e6,
    "billion": 1e9,
    "billions": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "trillion": 1e12,
    "trillions": 1e12,
    "tn": 1e12,
    "lakh": 1e5,
    "lakhs": 1e5,
    "crore": 1e7,
    "crores": 1e7,
    "cr": 1e7,
}
CURRENCIES = {"$": "USD", "us$": "USD", "usd": "USD", "dollars": "USD", "€": "EUR", "£": "GBP"}
CURRENCIES |= {"₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR"}

_NEG = "[-\u2212\u2013]"  # hyphen, minus sign, en dash
_NUMBER = re.compile(
    rf"""^\s*
    (?P<neg1>{_NEG})?\s*
    (?P<open>\()?\s*
    (?P<neg2>{_NEG})?\s*
    (?P<cur>US\$|\$|USD|€|£|₹|Rs\.?|INR)?\s*
    (?P<open2>\()?\s*
    (?P<neg3>{_NEG})?\s*
    (?P<num>\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?   # 1,234,567.89
          |\d{{1,2}}(?:,\d{{2}})+,\d{{3}}(?:\.\d+)?  # Indian grouping 1,80,077.92
          |\d+(?:\.\d+)?|\.\d+)\s*
    (?P<close1>\))?\s*
    (?P<pct>%|percent\b|per\s*cent\b)?\s*
    (?:(?P<scale>thousands?|millions?|billions?|trillions?|lakhs?|crores?|cr
                 |mn|mm|bn|tn|[kmb])\b\.?)?\s*
    (?P<cur2>USD|dollars)?\s*
    (?P<times>x|times)?\s*
    (?P<close2>\))?\s*
    (?P<pct2>%)?\s*
    \.?\s*$""",
    re.X | re.I,
)
_QUESTION_SCALE = re.compile(
    r"(?:USD|US\$|\$)\s*(thousands|millions|billions)"
    r"|in\s+(thousands|millions|billions)\s+of\s+(?:US\s+)?dollars"
    r"|in\s+(thousands|millions|billions)\b",
    re.I,
)
_QUESTION_PERCENT = re.compile(r"in\s+units\s+of\s+percent|as\s+a\s+%|\(%\)|in\s+percent", re.I)


class ParsedNumber(BaseModel):
    value: float  # in base units (scale applied)
    unit: str | None  # "USD", "%", "x", other currency code, or None for a bare number
    half_ulp: float  # half of the last displayed digit, in base units (rounding uncertainty)
    scaled: bool = False  # an explicit scale word (million, bn...) was present


def parse_number(text: str | None) -> ParsedNumber | None:
    """Parse an answer that is exactly one number ("$1,577.00", "(2.5)%", "24.3 billion").

    Returns None for anything else (words, ranges, several numbers, "N/A").
    """
    if text is None:
        return None
    m = _NUMBER.match(str(text).replace("\u00a0", " "))
    if not m:
        return None
    g = m.groupdict()
    opened = bool(g["open"]) + bool(g["open2"])
    parens = opened + bool(g["close1"] or g["close2"])
    if opened > 1 or parens == 1:  # unbalanced bracket
        return None
    num = g["num"].replace(",", "")
    decimals = len(num.split(".")[1]) if "." in num else 0
    value = float(num)
    scale = SCALES[g["scale"].lower()] if g["scale"] else 1.0
    if g["scale"] and len(g["scale"]) == 1 and not g["cur"]:
        return None  # "5m" / "3b" without a currency is too ambiguous (metres, bytes...)
    sign = -1.0 if (g["neg1"] or g["neg2"] or g["neg3"] or parens == 2) else 1.0
    if g["pct"] or g["pct2"]:
        unit = "%"
    elif g["times"]:
        unit = "x"
    else:
        cur = (g["cur"] or g["cur2"] or "").lower()
        unit = CURRENCIES.get(cur) if cur else None
    return ParsedNumber(
        value=sign * value * scale,
        unit=unit,
        half_ulp=0.5 * 10.0 ** (-decimals) * scale,
        scaled=bool(g["scale"]),
    )


def is_year(parsed: ParsedNumber | None, text: str | None) -> bool:
    """A bare year ("2019") is a label, not a quantity: a 1% tolerance would accept 2000-2039."""
    return (
        parsed is not None
        and parsed.unit is None
        and not parsed.scaled
        and re.fullmatch(r"\s*(19|20)\d\d\s*\.?\s*", str(text)) is not None
    )


def tolerance_for(parsed: ParsedNumber, value: float | None = None) -> float:
    """Relative tolerance: 1%, widened to the rounding of the displayed answer."""
    v = parsed.value if value is None else value
    if v == 0 or not math.isfinite(v):
        return 0.01
    return max(0.01, parsed.half_ulp / abs(v))


def numeric_fields(
    answer: str | None, question: str | None = None, value: float | None = None
) -> dict[str, Any] | None:
    """EvalItem fields for a single-number answer, or None if the answer is not one number.

    A scale stated only in the question ("in USD millions") is applied to an unscaled
    answer; `value` overrides the parsed number (e.g. FinQA's unrounded program result).
    """
    parsed = parse_number(answer)
    if parsed is None or is_year(parsed, answer):
        return None
    if question and not parsed.scaled and parsed.unit in (None, "USD"):
        sm = _QUESTION_SCALE.search(question)
        if sm:
            word = next(w for w in sm.groups() if w)
            factor = SCALES[word.lower()]
            parsed = parsed.model_copy(
                update={
                    "value": parsed.value * factor,
                    "half_ulp": parsed.half_ulp * factor,
                    "unit": "USD",
                    "scaled": True,
                }
            )
        elif parsed.unit is None and _QUESTION_PERCENT.search(question):
            parsed = parsed.model_copy(update={"unit": "%"})
    v = parsed.value if value is None else value
    return {
        "kind": "numeric",
        "answer_value": v,
        "answer_unit": parsed.unit,
        "tolerance": tolerance_for(parsed, v),
        "abs_tolerance": max(parsed.half_ulp, 0.0),
    }


def apply_numeric(fields: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Split numeric_fields() output into EvalItem kwargs, moving abs_tolerance into meta."""
    out = dict(fields)
    meta["abs_tolerance"] = out.pop("abs_tolerance")
    return out


def flatten_table(rows: Iterable[Iterable[Any]]) -> str:
    """One line per table row, cells joined by ' | '; empty rows dropped."""
    lines = []
    for row in rows:
        cells = [re.sub(r"\s+", " ", str(c)).strip() for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def flatten_markdown_tables(text: str) -> str:
    """Compact padded markdown tables into ' | ' rows; drop separator and empty cells."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-*:?", c) for c in cells):
                continue  # header separator
            cells = [c for c in cells if c and c != "nan"]
            if not cells:
                continue
            out.append(" | ".join(cells))
        else:
            out.append(line)
    return "\n".join(out)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def unique_fy(question: str) -> int | None:
    """The fiscal year a question names, when it names exactly one (FY2018, FY 2018, FY18)."""
    years = set()
    for m in re.finditer(r"\bFY\s?'?(\d{4}|\d{2})\b", question, re.I):
        y = int(m.group(1))
        years.add(y if y > 999 else 2000 + y)
    return years.pop() if len(years) == 1 else None
