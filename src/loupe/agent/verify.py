"""Code verifier: split an answer into cited claims and check them against the ledger.

A claim is a sentence. Its citations are the [E#] markers in it. It is supported when
  - it cites at least one evidence item that exists,
  - every number in it matches a number in its cited evidence (allowing for the way
    people write money: 25,785 million = 25.8 billion = 25785000000), and
  - every quoted span appears in a cited passage.
Sentences with no number and no quote only need a valid citation.
"""

import re
from typing import NamedTuple

from loupe.agent.evidence import Ledger
from loupe.core.schemas import Citation, Claim

CITE = re.compile(r"\[(E\d+)\]")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])")
NUMBER = re.compile(
    r"(?<![\w.])-?\$?\(?\d[\d,]*(?:\.\d+)?\)?\s*(?:%|percent|billion|million|thousand|bn|m\b|k\b)?",
    re.I,
)
QUOTE = re.compile(r"[\"“]([^\"”]{12,})[\"”]")
SCALES = {"billion": 1e9, "bn": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
YEARS = range(1990, 2040)


class Num(NamedTuple):
    value: float
    tol: float  # half a unit of the last digit written: "25.8 billion" -> 0.05e9


def parse_numbers(text: str) -> list[Num]:
    out = []
    for m in NUMBER.finditer(CITE.sub("", text)):
        raw = m.group(0).strip()
        neg = raw.startswith("-") or (raw.startswith("(") and raw.rstrip("%").endswith(")"))
        digits = re.search(r"\d[\d,]*(?:\.(\d+))?", raw)
        if not digits:
            continue
        value = float(digits.group(0).replace(",", ""))
        decimals = len(digits.group(1) or "")
        tol = 0.5 * 10**-decimals
        unit = re.search(r"(billion|million|thousand|bn|m|k)\s*$", raw, re.I)
        if unit:
            value *= SCALES[unit.group(1).lower()]
            tol *= SCALES[unit.group(1).lower()]
        if value in YEARS and not unit and "$" not in raw and "%" not in raw:
            continue  # 2024 is a year, not a value to check
        out.append(Num(-value if neg else value, tol))
    return out


def _matches(claim: Num, evidence: float) -> bool:
    """The claimed number is the evidence value, possibly rounded or in other units."""
    for scale in (1, 1e3, 1e6, 1e9):  # tables in millions vs raw XBRL dollars
        for ev in (evidence * scale, evidence / scale):
            if abs(claim.value - ev) <= claim.tol + 1e-9 * abs(ev):
                return True
    return False


def verify(answer: str, ledger: Ledger) -> list[Claim]:
    claims = []
    for sentence in (s.strip() for s in SENTENCE.split(answer.strip())):
        if not sentence:
            continue
        ids = CITE.findall(sentence)
        cited = [e for e in (ledger.get(i) for i in ids) if e is not None]
        numbers = parse_numbers(sentence)
        quotes = QUOTE.findall(sentence)
        if not ids:
            supported = None if not numbers and not quotes else False
        elif not cited:
            supported = False
        else:
            pool = [e.value for e in cited if e.value is not None]
            pool += [n.value for e in cited for n in parse_numbers(e.text)]
            nums_ok = all(any(_matches(n, p) for p in pool) for n in numbers if n.value != 0)
            texts = " ".join(e.text for e in cited).lower()
            quotes_ok = all(" ".join(q.lower().split()) in " ".join(texts.split()) for q in quotes)
            supported = nums_ok and quotes_ok
        claims.append(
            Claim(
                text=sentence,
                citations=[e.citation for e in cited] or [Citation() for _ in ids],
                supported=supported,
            )
        )
    return claims
