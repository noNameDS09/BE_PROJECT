import json

from loupe.core.schemas import Document
from loupe.extract.events import EventExtractor, blind_scores, quote_match, to_event
from tests.test_orchestrators import ScriptedGateway, reply

TEXT = (
    "Item 4.01 Changes in Registrant's Certifying Accountant. On March 3, 2024, the Audit "
    "Committee dismissed KPMG LLP as the Company's independent registered public accounting "
    "firm. There were no disagreements with KPMG on any matter of accounting principles."
)


def test_quote_match_exact_fuzzy_and_unrelated():
    assert quote_match("the Audit Committee dismissed KPMG LLP", TEXT) == 1.0
    assert 0.9 <= quote_match("the Audit Committee dismised KPMG LLP as the Company's", TEXT) < 1.0
    assert quote_match("Revenue grew by twelve percent in the quarter", TEXT) < 0.7


def test_guided_extraction_validates_quotes_and_scores_in_a_separate_pass():
    gw = ScriptedGateway(
        reply(
            json.dumps(
                {
                    "events": [
                        {
                            "summary": "KPMG dismissed",
                            "event_date": "2024-03-03",
                            "fields": {"former_auditor": "KPMG LLP"},
                            "quote": "the Audit Committee dismissed KPMG LLP",
                        },
                        {
                            "summary": "invented",
                            "quote": "The CEO resigned to pursue other interests.",
                        },
                    ]
                }
            )
        ),
        reply('{"score": 5, "reason": "explicit"}'),
    )
    events = EventExtractor(gw, "m").guided("4.01", TEXT)
    assert len(events) == 1  # the invented quote is rejected before scoring
    ev = events[0]
    assert (ev.item, ev.score, ev.quote_match, str(ev.event_date)) == ("4.01", 5, 1.0, "2024-03-03")
    assert "Rate how well" in gw.requests[1]["messages"][0]["content"]

    doc = Document(
        doc_id="X_8-K_a", company_id="X", source="t", form="8-K", url="u", content_hash="h"
    )
    out = to_event(doc, ev, "m")
    assert out.event_type == "4.01" and out.quality_score == 5 and out.label_source == "llm"


def test_blind_mode_drops_unknown_items_and_exhibits():
    gw = ScriptedGateway(
        reply(
            json.dumps(
                {
                    "events": [
                        {
                            "item": "4.01",
                            "quote": "dismissed KPMG LLP as the Company's independent",
                        },
                        {"item": "9.01", "quote": "dismissed KPMG LLP"},
                        {"item": "7.77", "quote": "dismissed KPMG LLP"},
                    ]
                }
            )
        ),
        reply('{"score": 4}'),
    )
    events = EventExtractor(gw, "m").blind(TEXT)
    assert [e.item for e in events] == ["4.01"]


def test_blind_scores_against_sec_item_codes():
    assert blind_scores({"4.01"}, {"4.01", "9.01"}) == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    s = blind_scores({"4.01", "8.01"}, {"4.01", "5.02"})
    assert (s["precision"], s["recall"]) == (0.5, 0.5)
