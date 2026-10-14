"""Source-adapter tests.

Everything here is offline: the edgartools calls need the network, so what is
tested is the pure logic around them — id stability, date parsing, item
splitting, URL construction, risk-item filtering and concept canonicalisation.
Those are the parts that silently corrupt a corpus if they are wrong.
"""

from datetime import date

from loupe.core.schemas import CompanyInfo
from loupe.sources import identity, us


def company() -> CompanyInfo:
    return CompanyInfo(ticker="AMD", name="ADVANCED MICRO DEVICES INC", cik="0000002488")


# --------------------------------------------------------------------------- #
# dates and ids
# --------------------------------------------------------------------------- #


def test_parse_date_accepts_iso_and_rejects_junk():
    assert us._parse_date("2025-02-05") == date(2025, 2, 5)
    assert us._parse_date("2025-02-05T06:00:00") == date(2025, 2, 5)
    assert us._parse_date("") is None
    assert us._parse_date(None) is None
    assert us._parse_date("not a date") is None


def test_stable_id_is_deterministic_and_short():
    a = us._stable_id("0000002488", "0000002488-25-000012")
    b = us._stable_id("0000002488", "0000002488-25-000012")
    assert a == b
    assert len(a) == 16
    assert us._stable_id("x", "y") != a


def test_fiscal_period_by_form():
    annual = {"form": "10-K", "report_date": date(2024, 12, 28)}
    third = {"form": "10-Q", "report_date": date(2024, 9, 28)}
    assert us._fiscal_period(annual) == "FY"
    assert us._fiscal_period(third) == "Q3"
    assert us._fiscal_period({"form": "8-K", "report_date": date(2024, 9, 28)}) is None


# --------------------------------------------------------------------------- #
# 8-K item codes
# --------------------------------------------------------------------------- #


def test_split_items_handles_lists_and_strings():
    assert us._split_items("2.02, 7.01") == ["2.02", "7.01"]
    assert us._split_items(["1.01", "2.04"]) == ["1.01", "2.04"]
    assert us._split_items(None) == []


def test_risk_items_filters_to_the_risk_set():
    filing = {"items": ["2.02", "9.01", "7.01"]}
    assert us.risk_items(filing) == []
    filing = {"items": ["5.02", "2.02", "9.01"]}
    assert us.risk_items(filing) == ["5.02"]


# --------------------------------------------------------------------------- #
# document metadata
# --------------------------------------------------------------------------- #


def test_filing_url_strips_dashes_and_keeps_primary_document():
    filing = {"accession": "0000002488-25-000012", "primary_document": "amd-20241228.htm"}
    url = us._filing_url(company(), filing)
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/2488/000000248825000012/amd-20241228.htm"
    )


def test_build_document_is_stable_across_calls():
    filing = {
        "accession": "0000002488-25-000012",
        "form": "10-K",
        "filing_date": date(2025, 2, 5),
        "report_date": date(2024, 12, 28),
        "primary_document": "a.htm",
        "items": [],
    }
    first = us.build_document(company(), filing, [], "text")
    second = us.build_document(company(), filing, [], "text")
    assert first.doc_id == second.doc_id
    assert first.fiscal_year == 2024
    assert first.fiscal_period == "FY"
    assert first.filed_at.date() == date(2025, 2, 5)


def test_different_accessions_get_different_doc_ids():
    base = {
        "form": "10-K",
        "filing_date": date(2025, 2, 5),
        "report_date": date(2024, 12, 28),
        "primary_document": "a.htm",
        "items": [],
    }
    a = us.build_document(company(), {**base, "accession": "0000002488-25-000012"}, [], "")
    b = us.build_document(company(), {**base, "accession": "0000002488-24-000012"}, [], "")
    assert a.doc_id != b.doc_id


# --------------------------------------------------------------------------- #
# section titles
# --------------------------------------------------------------------------- #


class _FakeSection:
    def __init__(self, title, item, part, text="section body"):
        self.title, self.item, self.part = title, item, part
        self._text = text

    def text(self):
        return self._text


def test_pretty_title_keeps_library_title_for_8k():
    section = _FakeSection("Item 5.02 - Departure of Directors", "502", None)
    assert us._pretty_title(section, "item_502") == "Item 5.02 - Departure of Directors"


def test_pretty_title_builds_from_item_for_10k():
    section = _FakeSection("part_i_item_7", "7", "I")
    assert us._pretty_title(section, "part_i_item_7") == "Part I 7"


def test_pretty_title_does_not_lowercase_roman_numerals():
    section = _FakeSection("part_ii_item_7", "7", "II")
    assert us._pretty_title(section, "part_ii_item_7") == "Part II 7"


def test_pretty_title_handles_8k_with_no_part():
    section = _FakeSection(None, "901", None)
    assert us._pretty_title(section, "item_901") == "Item 901"


def test_pretty_title_falls_back_to_key():
    section = _FakeSection(None, None, None)
    assert us._pretty_title(section, "signatures") == "signatures"


def test_extract_sections_keys_text_by_our_section_id():
    class FakeContainer(dict):
        pass

    class FakeDocument:
        def text(self):
            return "full body"

    class FakeFiling:
        sections = FakeContainer(
            {
                "part_i_item_1a": _FakeSection("part_i_item_1a", "1A", "Part I"),
                "empty": _FakeSection("empty", None, None, text="   "),
            }
        )
        document = FakeDocument()

    sections, texts, full = us.extract_sections("doc1", FakeFiling())
    # The empty section is skipped, and every kept section has its own text.
    assert len(sections) == 1
    assert texts[sections[0].section_id] == "section body"
    assert sections[0].start_char == 0
    assert sections[0].end_char == len("section body")
    assert full == "full body"


def test_extract_sections_without_a_document_returns_empty_text():
    sections, texts, full = us.extract_sections("doc1", object())
    assert sections == [] and texts == {} and full == ""


# --------------------------------------------------------------------------- #
# XBRL concepts
# --------------------------------------------------------------------------- #


def test_bare_strips_taxonomy_prefix():
    assert us._bare("us-gaap:Revenues") == "Revenues"
    assert us._bare("Revenues") == "Revenues"


def test_canonical_concept_maps_synonyms():
    assert us.canonical_concept("us-gaap:Revenues") == "Revenue"
    assert (
        us.canonical_concept("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax")
        == "Revenue"
    )
    assert us.canonical_concept("us-gaap:NetIncomeLoss") == "NetIncome"
    assert us.canonical_concept("us-gaap:Assets") == "Assets"


def test_canonical_concept_ignores_untracked_tags():
    assert us.canonical_concept("us-gaap:SomeObscureTag") is None


def test_core_concepts_cover_every_synonym():
    assert set(us.CORE_CONCEPTS) == {tag for group in us.CONCEPT_SYNONYMS.values() for tag in group}


# --------------------------------------------------------------------------- #
# identity resolution
# --------------------------------------------------------------------------- #


def test_candidate_tickers_handles_strings_and_maps(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text(
        "companies:\n"
        "financebench_candidates:\n"
        "  - AMD\n"
        "  - {ticker: KO, cik: '0000021344'}\n"
        "event_candidates:\n"
        "  - {ticker: XYZ}\n"
    )
    assert identity.candidate_tickers(config) == [
        ("AMD", "financebench"),
        ("KO", "financebench"),
        ("XYZ", "event_scan"),
    ]


def test_configured_ciks_reads_both_sections(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text(
        "companies:\n"
        "financebench_candidates:\n"
        "  - {ticker: amd, cik: 2488}\n"
        "event_candidates:\n"
        "  - {ticker: KO, cik: '0000021344'}\n"
    )
    assert identity.configured_ciks(config) == {"AMD": "0000002488", "KO": "0000021344"}


def test_config_with_no_selectable_companies_raises(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("version: 1\ncompanies: []\nfinancebench_candidates: []\n")
    try:
        identity.load_config(config)
    except identity.UniverseError as exc:
        assert "no companies" in str(exc)
    else:
        raise AssertionError("expected UniverseError")


def test_config_with_candidates_loads(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("version: 1\ncompanies: []\nfinancebench_candidates:\n  - AMD\n")
    assert identity.load_config(config)["version"] == 1


def test_resolve_universe_uses_live_map(tmp_path, monkeypatch):
    config = tmp_path / "c.yaml"
    config.write_text(
        "companies:\nfinancebench_candidates:\n  - {ticker: AMD, cik: '0000002488'}\n"
    )
    monkeypatch.setattr(
        identity,
        "fetch_ticker_map",
        lambda *a, **k: {"AMD": {"cik": "0000002488", "title": "ADVANCED MICRO DEVICES"}},
    )
    resolved = identity.resolve_universe(config)
    assert resolved[0].cik == "0000002488"
    assert resolved[0].source == "financebench"


def test_resolve_universe_raises_on_bad_cik(tmp_path, monkeypatch):
    config = tmp_path / "c.yaml"
    config.write_text(
        "companies:\nfinancebench_candidates:\n  - {ticker: AMD, cik: '0000000001'}\n"
    )
    monkeypatch.setattr(
        identity,
        "fetch_ticker_map",
        lambda *a, **k: {"AMD": {"cik": "0000002488", "title": "AMD"}},
    )
    try:
        identity.resolve_universe(config)
    except identity.UniverseError as exc:
        assert "mismatch" in str(exc).lower()
    else:
        raise AssertionError("expected a CIK mismatch error")


def test_resolve_universe_raises_on_unknown_ticker(tmp_path, monkeypatch):
    config = tmp_path / "c.yaml"
    config.write_text("companies:\nfinancebench_candidates:\n  - ZZZZ\n")
    monkeypatch.setattr(identity, "fetch_ticker_map", lambda *a, **k: {})
    try:
        identity.resolve_universe(config)
    except identity.UniverseError as exc:
        assert "ZZZZ" in str(exc)
    else:
        raise AssertionError("expected an unknown-ticker error")


# --------------------------------------------------------------------------- #
# prices
# --------------------------------------------------------------------------- #


def test_price_unavailable_is_its_own_type():
    assert issubclass(us.PriceUnavailable, RuntimeError)


def test_unknown_price_provider_raises():
    try:
        us.fetch_daily_prices("AMD", provider="nope")
    except us.PriceUnavailable as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected PriceUnavailable")


def test_html_challenge_is_reported_not_parsed(monkeypatch):
    class Response:
        text = "<!DOCTYPE html> challenge"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(us.httpx, "get", lambda *a, **k: Response())
    try:
        us.fetch_daily_prices("AMD", provider="stooq")
    except us.PriceUnavailable as exc:
        assert "challenge" in str(exc)
    else:
        raise AssertionError("expected PriceUnavailable")
