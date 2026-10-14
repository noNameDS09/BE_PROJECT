"""Retrieval tests. No network: the index is built from fixture chunks."""

import pytest

from loupe.index.search import BM25Index, HybridIndex, tokenize

AMD = "AMD"
MSFT = "MSFT"

DOCS = [
    ("a0:000", f"{AMD} gross margin declined because data centre revenue grew slower."),
    ("a0:001", f"{AMD} revenue for fiscal 2024 was 25.8 billion US dollars."),
    ("a0:002", f"{MSFT} reported record cloud revenue and higher operating margin."),
    ("a0:003", f"{MSFT} gross margin expanded to 68 percent in the third quarter."),
    ("b0:000", "Cybersecurity risk factors include ransomware and supply chain attacks."),
    ("b0:001", "The company operates in 52 weeks ending on the last Saturday of December."),
]

COMPANIES = {
    "a0:000": AMD,
    "a0:001": AMD,
    "a0:002": MSFT,
    "a0:003": MSFT,
    "b0:000": AMD,
    "b0:001": MSFT,
}


def make_index(dense=None):
    return HybridIndex(DOCS, dense_model=dense, companies=COMPANIES)


def test_tokenize_lowercases_and_splits():
    assert tokenize("Gross Margin, FY2024!") == ["gross", "margin", "fy2024"]


def test_bm25_ranks_lexical_match_first():
    index = BM25Index(DOCS)
    results = index.search("gross margin declined", top_k=3)
    assert results[0][0] == "a0:000"


def test_bm25_ignores_punctuation():
    index = BM25Index(DOCS)
    assert index.search("gros-margin", top_k=3)


def test_bm25_finds_numeric_token():
    index = BM25Index(DOCS)
    assert index.search("cybersecurity ransomware", top_k=1)[0][0] == "b0:000"


def test_search_returns_hits_with_citations():
    hits = make_index().search("gross margin", top_k=2)
    assert len(hits) == 2
    for hit in hits:
        assert hit.citation.chunk_id == hit.chunk_id
        assert hit.citation.quote
        assert hit.citation.verified is False  # only the verifier may set this


def test_company_filter_excludes_other_company():
    hits = make_index().search("revenue", top_k=10, company_id=MSFT)
    assert hits
    assert all(h.company_id == MSFT for h in hits)
    assert all("AMD" not in h.text for h in hits)


def test_company_filter_narrows_candidate_pool():
    """Filtering must change ranking, not just truncate the final list.

    `b0:001` mentions '52 weeks' and would outrank AMD's revenue chunk on a
    bare 'revenue' query if scoring were global.
    """
    unfiltered = make_index().search("revenue", top_k=10)
    filtered = make_index().search("revenue", top_k=10, company_id=AMD)
    assert len(unfiltered) > len(filtered)
    assert all(h.company_id == AMD for h in filtered)


def test_search_unknown_company_returns_empty():
    assert make_index().search("revenue", top_k=5, company_id="NOPE") == []


def test_search_respects_top_k():
    assert len(make_index().search("margin", top_k=2)) == 2


def test_top_k_larger_than_corpus():
    assert len(make_index().search("margin", top_k=99)) <= len(DOCS)


def test_search_with_no_match():
    assert make_index().search("zzzzznotpresent", top_k=3) == []


def test_rrf_scores_present():
    hits = make_index().search("gross margin", top_k=3)
    assert all("bm25" in hit.scores for hit in hits)


def test_dense_stage_absent_by_default():
    assert make_index().dense is None


@pytest.mark.parametrize("allowed_none", [True, False])
def test_bm25_allowed_mask_restricts_scoring(allowed_none):
    index = BM25Index(DOCS)
    if allowed_none:
        assert index.search("revenue", top_k=5)
    else:
        allowed = {0, 1}
        results = index.search("revenue", top_k=5, allowed=allowed)
        assert {r[0] for r in results} <= {"a0:000", "a0:001"}


def test_empty_index_returns_nothing():
    assert HybridIndex([], companies={}).search("anything", top_k=5) == []


def test_hit_carries_the_real_doc_id_not_the_section_id():
    """A chunk_id is '<section_id>:<index>'; splitting it gives a section id,
    which cannot be resolved to a filing URL. doc_id must come from metadata."""
    metadata = {
        "a0:000": {"doc_id": "DOCX", "item": "7", "form": "10-K"},
        "a0:001": {"doc_id": "DOCY", "item": "1A", "form": "10-Q"},
        "a0:002": {"doc_id": "DOCZ", "item": "8", "form": "10-K"},
        "a0:003": {"doc_id": "DOCW", "item": "2", "form": "10-Q"},
        "b0:000": {"doc_id": "DOCV", "item": "1A", "form": "10-K"},
        "b0:001": {"doc_id": "DOCU", "item": "7", "form": "10-K"},
    }
    index = HybridIndex(DOCS, companies=COMPANIES, metadata=metadata)
    hits = index.search("gross margin", top_k=3)
    assert all(hit.doc_id.startswith("DOC") for hit in hits)
    assert all(hit.doc_id != hit.chunk_id.split(":")[0] for hit in hits)


def test_hit_metadata_carries_citation_context():
    metadata = {cid: {"doc_id": "D", "item": "1A", "form": "10-K"} for cid, _ in DOCS}
    index = HybridIndex(DOCS, companies=COMPANIES, metadata=metadata)
    hit = index.search("cybersecurity", top_k=1)[0]
    assert hit.metadata["item"] == "1A"
    assert hit.metadata["form"] == "10-K"
