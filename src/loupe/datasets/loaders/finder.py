"""FinDER: expert search queries over S&P 500 10-Ks with gold passages.

The parquet has no company field, and 10-k.zip holds one 10-K per ticker (10k/<TICKER>.html).
Each question is linked to its 10-K by checking that its first gold passage occurs in that
10-K's text: candidates are tickers named in the query, then the 10-Ks of neighbouring rows
(the file is grouped by company), then every 10-K (unique match only). Only verified links
are kept; the rest have no document and meta.doc_link == "unresolved".
"""

import html
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pyarrow.parquet as pq

from loupe.datasets.universe import company_split, load_universe
from loupe.eval.schema import EvalDoc, EvalItem, GoldEvidence

NAME = "finder"
ZIP = "10-k.zip"
_TAG = re.compile(r"<[^>]+>")
_HIDDEN = re.compile(r"<ix:header>.*?</ix:header>", re.S | re.I)
_TOKEN = re.compile(r"\$?\b([A-Z][A-Z0-9]{0,4}(?:\.[A-Z])?)\b")
NEEDLE = 60


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def html_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = _HIDDEN.sub(" ", text)
    return html.unescape(_TAG.sub(" ", text))


def needles(passage: str) -> list[str]:
    """Up to three probe strings from a gold passage (start, middle, end)."""
    n = normalise(passage)
    if len(n) < 20:
        return []
    if len(n) <= NEEDLE:
        return [n]
    mid = (len(n) - NEEDLE) // 2
    return [n[:NEEDLE], n[mid : mid + NEEDLE], n[-NEEDLE:]]


class TenKs:
    """Lazily extracted, normalised 10-K texts from 10-k.zip."""

    def __init__(self, path: Path):
        self.zip = zipfile.ZipFile(path)
        self.members = {
            n[len("10k/") : -len(".html")]: n
            for n in self.zip.namelist()
            if n.startswith("10k/") and n.endswith(".html")
        }
        self._text: dict[str, str] = {}

    def text(self, ticker: str) -> str:
        if ticker not in self._text:
            self._text[ticker] = normalise(html_text(self.zip.read(self.members[ticker])))
        return self._text[ticker]

    def contains(self, ticker: str, probes: list[str]) -> bool:
        if ticker not in self.members or not probes:
            return False
        text = self.text(ticker)
        return any(p in text for p in probes)


def _passages(refs) -> list[str]:
    if refs is None:
        return []
    if isinstance(refs, str):
        return [refs]
    return [str(r) for r in refs]


def load(root: Path) -> Iterator[EvalItem]:
    rows = pq.read_table(root / "data" / "train-00000-of-00001.parquet").to_pylist()
    docs = TenKs(root / ZIP)
    tickers = set(docs.members)
    probes = [needles(next((p for p in _passages(r["references"]) if p.strip()), "")) for r in rows]

    linked: list[str | None] = [None] * len(rows)
    how: list[str | None] = [None] * len(rows)
    # pass 1: tickers named in the query
    for i, r in enumerate(rows):
        for t in dict.fromkeys(_TOKEN.findall(r["text"] or "")):
            if t in tickers and docs.contains(t, probes[i]):
                linked[i], how[i] = t, "ticker_in_query"
                break
    # pass 2: neighbours (rows are grouped by company)
    for i in range(len(rows)):
        if linked[i] is None:
            near = [linked[j] for j in (i - 1, i + 1, i - 2, i + 2) if 0 <= j < len(rows)]
            for t in dict.fromkeys(t for t in near if t):
                if docs.contains(t, probes[i]):
                    linked[i], how[i] = t, "neighbour"
                    break
    # pass 3: every 10-K; boilerplate passages match many filings, so only a unique match counts
    for i in range(len(rows)):
        if linked[i] is None and probes[i]:
            matches = [t for t in sorted(tickers) if docs.contains(t, probes[i])]
            if len(matches) == 1:
                linked[i], how[i] = matches[0], "full_scan_unique"

    universe = load_universe()
    seen: dict[str, int] = {}
    for i, r in enumerate(rows):
        native = r["_id"]
        seen[native] = seen.get(native, 0) + 1
        suffix = "" if seen[native] == 1 else f"#{seen[native]}"
        ticker = linked[i]
        documents = []
        if ticker:
            documents = [
                EvalDoc(
                    doc_id=f"{NAME}_10k:{ticker}",
                    title=f"{ticker} 10-K",
                    path=f"raw/public/{NAME}/{ZIP}#{docs.members[ticker]}",
                )
            ]
        doc_id = documents[0].doc_id if documents else None
        evidence = [GoldEvidence(doc_id=doc_id, text=p) for p in _passages(r["references"])]
        yield EvalItem(
            item_id=f"{NAME}:{native}{suffix}",
            dataset=NAME,
            question=r["text"],
            kind="text",
            answer=r["answer"],
            mode="docs",
            documents=documents,
            evidence=evidence,
            companies=[ticker] if ticker in universe else [],
            split=company_split(ticker) if ticker in universe else None,  # type: ignore[arg-type]
            category=r.get("category"),
            meta={
                "reasoning": str(r.get("reasoning")).lower() == "true",
                "reasoning_type": r.get("type"),
                "finder_ticker": ticker,
                "doc_link": how[i] or "unresolved",
                "source_split": "train (FinDER's only split; used as an evaluation set)",
                "retrieval_corpus": f"raw/public/{NAME}/{ZIP}",
            },
        )
