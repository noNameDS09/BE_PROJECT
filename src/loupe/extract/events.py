"""8-K risk-event extraction with verbatim evidence and a second-pass quality score.

Method (Papers 1 and 2, Dolphin et al.):
1. Extract: typed fields plus a verbatim quote for each event, under a fixed schema.
2. Validate: the quote must be found in the filing text (fuzzy match >= 0.9), else rejected.
3. Score: a SEPARATE model call rates each surviving event 1-5. Paper 2 found a separate
   pass is calibrated where inline self-scoring is not; precision by score bin tests that.

Two modes:
- guided: one call per 8-K item section, item code known (builds the events table).
- blind:  the model reads the whole 8-K without item codes and must name the item types;
          compared with SEC's own item codes this gives an exact precision/recall test.
"""

import difflib
import re
from datetime import date

from pydantic import BaseModel, Field

from loupe.core.schemas import Document, Event
from loupe.llm.gateway import Gateway
from loupe.orchestrators.base import parse_json
from loupe.sources.us.events import ITEM_NAMES

PROMPT_VERSION = "events-v1"
EXTRACT_ITEMS = ["1.01", "1.02", "1.03", "1.05", "2.01", "2.03", "2.04", "2.05", "2.06",
                 "3.01", "4.01", "4.02", "5.01", "5.02", "8.01"]  # fmt: skip

FIELDS = {
    "1.01": ["counterparty", "agreement_type", "amount", "term"],
    "1.02": ["counterparty", "agreement_type", "termination_reason"],
    "1.03": ["court", "chapter", "filing_date"],
    "1.05": ["incident_date", "nature", "systems_affected", "material_impact"],
    "2.01": ["asset_or_business", "counterparty", "consideration"],
    "2.03": ["instrument", "amount", "maturity", "rate"],
    "2.04": ["obligation", "amount", "triggering_event"],
    "2.05": ["plan", "estimated_costs", "positions_affected"],
    "2.06": ["asset", "impairment_amount", "reason"],
    "3.01": ["exchange", "rule", "action"],
    "4.01": ["former_auditor", "new_auditor", "dismissed_or_resigned", "disagreements"],
    "4.02": ["periods_affected", "reason", "estimated_effect"],
    "5.01": ["acquirer", "description"],
    "5.02": ["person", "role", "change"],
    "8.01": ["topic"],
}

GUIDED = """You extract a material event from one section of an SEC Form 8-K.
Item {item}: {name}.
Return JSON {{"events": [{{"summary": "<one sentence>", "event_date": "YYYY-MM-DD or null",
"fields": {{{fields}}},
"quote": "<exact sentence(s) copied from the text that state the event>"}}]}}.
The quote must be copied verbatim (no paraphrase). Use null for fields the text does not state.
Return {{"events": []}} if the section reports no event."""

BLIND = """You read an SEC Form 8-K and identify which Form 8-K items it reports.
Item codes: {codes}.
Return JSON {{"events": [{{"item": "<code>", "summary": "<one sentence>",
"quote": "<exact sentence copied from the text>"}}]}}. Ignore item 9.01 (exhibits).
Quotes must be verbatim. Return {{"events": []}} if none apply."""

SCORE = """Rate how well this extracted event is supported by its quote and fits the item type.
5 = quote explicitly states the event and every field; 4 = clear, minor gaps; 3 = plausible but
vague; 2 = weak or partly wrong; 1 = unsupported or wrong item.
Return JSON {"score": 1-5, "reason": "<short>"}."""


class Extracted(BaseModel):
    item: str
    summary: str = ""
    event_date: date | None = None
    fields: dict = Field(default_factory=dict)
    quote: str = ""
    quote_match: float = 0.0
    score: int | None = None
    score_reason: str = ""


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[“”\"']", "", text).lower().split())


def quote_match(quote: str, text: str) -> float:
    """1.0 if the quote appears verbatim (ignoring case, spacing, quote marks), else the best
    similarity against same-length windows of the text."""
    q, t = _norm(quote), _norm(text)
    if not q:
        return 0.0
    if q in t:
        return 1.0
    words, n = t.split(), len(q.split())
    best = 0.0
    for size in (n - 1, n, n + 1):  # allow one dropped or extra word
        if size < 1:
            continue
        for i in range(0, max(1, len(words) - size + 1)):
            window = " ".join(words[i : i + size])
            best = max(best, difflib.SequenceMatcher(None, q, window).ratio())
            if best > 0.98:
                return round(best, 3)
    return round(best, 3)


def _date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


class EventExtractor:
    def __init__(
        self, gateway: Gateway, model: str, scorer_model: str | None = None, min_match: float = 0.9
    ):
        self.gateway = gateway
        self.model = model
        self.scorer_model = scorer_model or model
        self.min_match = min_match

    def _json(self, model: str, system: str, user: str, max_tokens: int = 900):
        c = self.gateway.complete(
            model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
            json_mode=True, max_tokens=max_tokens,
        )  # fmt: skip
        out = parse_json(c.text)
        return out if isinstance(out, dict) else {}

    def _score(self, ev: Extracted) -> Extracted:
        out = self._json(
            self.scorer_model, SCORE,
            f"Item {ev.item} ({ITEM_NAMES.get(ev.item, '?')})\nSummary: {ev.summary}\n"
            f"Fields: {ev.fields}\nQuote: {ev.quote}", 120,
        )  # fmt: skip
        try:
            ev.score = max(1, min(5, int(out.get("score"))))
        except (TypeError, ValueError):
            ev.score = None
        ev.score_reason = str(out.get("reason", ""))[:300]
        return ev

    def guided(self, item: str, section_text: str, max_chars: int = 8000) -> list[Extracted]:
        system = GUIDED.format(
            item=item, name=ITEM_NAMES.get(item, "?"),
            fields=", ".join(f'"{f}": ...' for f in FIELDS.get(item, ["topic"])),
        )  # fmt: skip
        out = self._json(self.model, system, section_text[:max_chars])
        raw = [{**e, "item": item} for e in out.get("events", []) if isinstance(e, dict)]
        return self._validate(raw, section_text)

    def blind(self, text: str, max_chars: int = 12000) -> list[Extracted]:
        codes = "; ".join(f"{c} {ITEM_NAMES[c]}" for c in EXTRACT_ITEMS)
        out = self._json(self.model, BLIND.format(codes=codes), text[:max_chars])
        return self._validate([e for e in out.get("events", []) if isinstance(e, dict)], text)

    def _validate(self, raw: list[dict], text: str) -> list[Extracted]:
        kept = []
        for e in raw:
            item = str(e.get("item", "")).strip()
            if item not in ITEM_NAMES or item == "9.01":
                continue
            ev = Extracted(
                item=item,
                summary=str(e.get("summary", ""))[:500],
                event_date=_date(e.get("event_date")),
                fields=e.get("fields") if isinstance(e.get("fields"), dict) else {},
                quote=str(e.get("quote", ""))[:1500],
            )
            ev.quote_match = quote_match(ev.quote, text)
            if ev.quote_match >= self.min_match:
                kept.append(self._score(ev))
        return kept


def to_event(doc: Document, ev: Extracted, model: str) -> Event:
    return Event(
        event_id=f"{doc.doc_id}#{ev.item}#{abs(hash(ev.quote)) % 10**8}",
        company_id=doc.company_id,
        event_type=ev.item,
        label_source="llm",
        doc_id=doc.doc_id,
        quote=ev.quote,
        occurred_on=ev.event_date,
        quote_match_score=ev.quote_match,
        fields={
            **ev.fields,
            "summary": ev.summary,
            "model": model,
            "prompt": PROMPT_VERSION,
            "score_reason": ev.score_reason,
        },
        quality_score=ev.score,
    )


def blind_scores(predicted: set[str], gold: set[str]) -> dict[str, float]:
    gold = gold - {"9.01"}
    tp = len(predicted & gold)
    p = tp / len(predicted) if predicted else (1.0 if not gold else 0.0)
    r = tp / len(gold) if gold else 1.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}
