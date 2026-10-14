"""Risk-event scan ranking. Pure logic, no network."""

from loupe.core.schemas import CompanyInfo
from loupe.sources import scan


def test_profile_counts_only_risk_items():
    profile = scan.RiskProfile(ticker="XYZ")
    profile.total_8k = 10
    for item, n in (("5.02", 3), ("4.01", 1)):
        profile.items[item] = n
        profile.risk_8k += n
    assert profile.risk_8k == 4
    assert profile.as_dict()["items"] == {"4.01": 1, "5.02": 3}


def test_score_ranks_worst_item_first():
    bankruptcy = scan.RiskProfile(ticker="A", items={"1.03": 1})
    resignation = scan.RiskProfile(ticker="B", items={"5.02": 9})
    assert bankruptcy.score > resignation.score


def test_score_prefers_breadth_at_equal_severity():
    narrow = scan.RiskProfile(ticker="A", items={"1.01": 5})
    broad = scan.RiskProfile(ticker="B", items={"1.01": 1, "5.02": 1})
    assert broad.score > narrow.score


def test_score_prefers_recency_at_equal_severity_and_breadth():
    older = scan.RiskProfile(ticker="A", items={"5.02": 1}, latest="2023-06-01")
    newer = scan.RiskProfile(ticker="A", items={"5.02": 1}, latest="2025-06-01")
    assert newer.score > older.score


def test_empty_profile_scores_zero():
    assert scan.RiskProfile(ticker="A").score[0] == 0


def test_scan_ranks_and_filters(monkeypatch):
    def fake_profile(company, window=None):
        if company.ticker == "AAA":
            return scan.RiskProfile(
                ticker="AAA", total_8k=9, risk_8k=4, items={"1.03": 1}, latest="2024-01-01"
            )
        return scan.RiskProfile(ticker=company.ticker, total_8k=3, risk_8k=0)

    monkeypatch.setattr(scan, "profile_company", fake_profile)
    companies = [CompanyInfo(ticker=t, name=t, cik="1") for t in ("AAA", "BBB", "CCC")]
    results = scan.scan(companies, pause=0)
    assert [p.ticker for p in results] == ["AAA"]  # BBB/CCC below min_risk


def test_scan_survives_a_failing_company(monkeypatch):
    def fake_profile(company, window=None):
        if company.ticker == "BAD":
            raise RuntimeError("SEC 403")
        return scan.RiskProfile(ticker=company.ticker, risk_8k=2, items={"5.02": 2})

    monkeypatch.setattr(scan, "profile_company", fake_profile)
    seen: list[str] = []
    companies = [CompanyInfo(ticker=t, name=t, cik="1") for t in ("BAD", "GOOD")]
    results = scan.scan(companies, pause=0, on_progress=lambda c, e=None: seen.append(c.ticker))
    assert [p.ticker for p in results] == ["GOOD"]
    assert "BAD" in seen


def test_to_event_candidates_skips_already_chosen():
    profiles = [
        scan.RiskProfile(ticker=t, items={"1.03": 1}, risk_8k=1) for t in ("AMD", "KO", "MMM", "VZ")
    ]
    entries = scan.to_event_candidates(profiles, existing=["AMD"], count=2)
    assert [e["ticker"] for e in entries] == ["KO", "MMM"]
    assert entries[0]["note"] == "8-K risk-event scan"


def test_to_event_candidates_respects_count():
    profiles = [scan.RiskProfile(ticker=t, items={"5.02": 1}, risk_8k=1) for t in "ABCDEF"]
    assert len(scan.to_event_candidates(profiles, count=3)) == 3


def test_every_risk_item_has_a_severity():
    from loupe.sources.us import RISK_8K_ITEMS

    assert set(RISK_8K_ITEMS) <= set(scan.ITEM_SEVERITY)


def test_severity_is_ordered_banker_to_officer():
    assert (
        scan.ITEM_SEVERITY["1.03"]
        > scan.ITEM_SEVERITY["2.04"]
        > scan.ITEM_SEVERITY["4.01"]
        > scan.ITEM_SEVERITY["5.02"]
    )
