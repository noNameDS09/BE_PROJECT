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

# citation markers: [E1], [E1][E2], [E1, E2], and the full-width 【E1】 some models write
CITE = re.compile(r"[\[【]\s*(E\d+(?:\s*[,;]\s*E\d+)*)\s*[\]】]")


def cited_ids(text: str) -> list[str]:
    return [eid for group in CITE.findall(text) for eid in re.findall(r"E\d+", group)]


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])")
NUMBER = re.compile(
    r"(?<![\w.])-?\$?\(?\d[\d,]*(?:\.\d+)?\)?\s*(?:%|percent|billion|million|thousand|bn|m\b|k\b)?",
    re.I,
)
QUOTE = re.compile(r"[\"“]([^\"”]{12,})[\"”]")
SCALES = {"billion": 1e9, "bn": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
YEARS = range(1990, 2040)
MONTH_BEFORE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s*$",
    re.I,
)
# a negative value may be written as a positive amount of loss, outflow, decline, ...
SIGN_WORDS = re.compile(
    r"\b(?:loss|losses|deficit|negative|declin\w*|decreas\w*|outflows?|used in|drop\w*|fell)\b",
    re.I,
)
BULLET = re.compile(r"^(?:[*•]+|-(?![\d$.]))\s*")


class Num(NamedTuple):
    value: float
    tol: float  # half a unit of the last digit written: "25.8 billion" -> 0.05e9


def parse_numbers(text: str) -> list[Num]:
    out = []
    text = CITE.sub("", text)
    for m in NUMBER.finditer(text):
        raw = m.group(0).strip()
        if re.search(r"\d(?:m|k|bn)$", raw, re.I) and "$" not in raw:
            continue  # a name like 3M, not "3 million"
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
        if value <= 31 and not unit and "%" not in raw and MONTH_BEFORE.search(text[: m.start()]):
            continue  # the day in "June 30"
        out.append(Num(-value if neg else value, tol))
    return out


def _matches(claim: Num, evidence: float) -> bool:
    """The claimed number is the evidence value, possibly rounded or in other units."""
    for scale in (1, 1e3, 1e6, 1e9):  # tables in millions vs raw XBRL dollars
        for ev in (evidence * scale, evidence / scale):
            if abs(claim.value - ev) <= claim.tol + 1e-9 * abs(ev):
                return True
    return False


def _supported(n: Num, pool: list[float], sentence: str) -> bool:
    if any(_matches(n, p) for p in pool):
        return True
    flipped = Num(-n.value, n.tol)
    return bool(SIGN_WORDS.search(sentence)) and any(_matches(flipped, p) for p in pool)


def _pool(evidence) -> list[float]:
    pool = [e.value for e in evidence if e.value is not None]
    return pool + [n.value for e in evidence for n in parse_numbers(e.text)]


def found_in(sentence: str, ledger: Ledger) -> list[str]:
    """Evidence ids that hold every number of a sentence (to repair a wrong citation)."""
    numbers = [n for n in parse_numbers(sentence) if n.value != 0]
    if not numbers:
        return []
    return [
        e.id
        for e in ledger.items.values()
        if all(_supported(n, _pool([e]), sentence) for n in numbers)
    ]


def _units(answer: str) -> list[str]:
    """Claims to check: each line (bullets, table rows) and each sentence within a line."""
    out = []
    for line in answer.splitlines():
        line = BULLET.sub("", line.strip()).strip()
        if line:
            out += [s.strip() for s in SENTENCE.split(line) if s.strip()]
    return out


def verify(answer: str, ledger: Ledger) -> list[Claim]:
    claims = []
    for sentence in _units(answer):
        if not sentence:
            continue
        ids = cited_ids(sentence)
        cited = [e for e in (ledger.get(i) for i in ids) if e is not None]
        numbers = parse_numbers(sentence)
        quotes = QUOTE.findall(sentence)
        if not ids:
            supported = None if not numbers and not quotes else False
        elif not cited:
            supported = False
        else:
            pool = _pool(cited)
            nums_ok = all(_supported(n, pool, sentence) for n in numbers if n.value != 0)
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
