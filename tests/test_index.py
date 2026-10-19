import hashlib
import itertools
from datetime import date

import numpy as np
import pytest

from loupe.core.schemas import Document, Section
from loupe.index.chunk import chunk_document, split_region
from loupe.index.search import SearchFilter, SearchIndex, build_index

TEXT = (
    "ACME CORP FORM 10-K cover page with the company name and address.\n"
    "Item 1A. Risk Factors\n"
    + "Supply chain disruption could reduce our margins. " * 30
    + "\nItem 7. Management's Discussion and Analysis\n"
    + "Net revenue grew 12 percent to 4.2 billion dollars driven by data center demand. " * 30
)


def doc(company="ACME", period=date(2024, 12, 31), form="10-K", text=TEXT):
    a = text.index("Item 1A.")
    b = text.index("Item 7.")
    return Document(
        doc_id=f"{company}_{form}_x",
        company_id=company,
        source="test",
        form=form,
        url="https://example.org",
        content_hash="h",
        period_end=period,
        sections=[
            Section(
                section_id="s1",
                doc_id="d",
                title="Risk Factors",
                item="1A",
                start_char=a,
                end_char=b,
            ),
            Section(
                section_id="s2",
                doc_id="d",
                title="MD&A",
                item="7",
                start_char=b,
                end_char=len(text),
            ),
        ],
    )


def test_split_region_offsets_are_exact_bounded_and_overlapping():
    spans = split_region(TEXT, 0, len(TEXT), size=300, overlap=60)
    assert all(e - s <= 300 for s, e in spans)
    assert all(not TEXT[s].isspace() and not TEXT[e - 1].isspace() for s, e in spans)
    assert all(b[0] < a[1] for a, b in itertools.pairwise(spans))  # overlap
    assert spans[-1][1] == len(TEXT.rstrip())


def test_chunks_stay_inside_sections_and_carry_metadata():
    d = doc()
    chunks = chunk_document(d, TEXT, size=300, overlap=60)
    b = TEXT.index("Item 7.")
    for c in chunks:
        assert TEXT[c.start_char : c.end_char] == c.text
        assert not (c.start_char < b < c.end_char)  # never crosses Item 1A -> Item 7
    assert chunks[0].metadata["items"] == []  # cover page
    assert {tuple(c.metadata["items"]) for c in chunks[1:]} == {("1A",), ("7",)}


class HashEmbedder:
    """Deterministic bag-of-words vectors: enough to test ranking and filters offline."""

    name = "hash"

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(64, np.float32)
        for w in text.lower().split():
            v[int(hashlib.md5(w.strip(".,").encode()).hexdigest(), 16) % 64] += 1
        return v / max(np.linalg.norm(v), 1e-9)

    def passages(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def query(self, text):
        return self._vec(text)


@pytest.fixture
def index(tmp_path):
    chunks = chunk_document(doc("ACME"), TEXT, 300, 60) + chunk_document(
        doc("BETA", date(2023, 12, 31)), TEXT, 300, 60
    )
    build_index(chunks, tmp_path / "idx", HashEmbedder())
    return SearchIndex.load(tmp_path / "idx", HashEmbedder())


@pytest.mark.parametrize("mode", ["hybrid", "dense", "bm25"])
def test_search_finds_the_relevant_section(index, mode):
    hits = index.search("supply chain disruption margins", k=3, mode=mode)
    assert hits and all("1A" in h.chunk.metadata["items"] for h in hits)


def test_filters_restrict_company_item_and_period(index):
    f = SearchFilter(companies=["BETA"], items=["7"], period_to=date(2023, 12, 31))
    hits = index.search("net revenue grew", k=5, filter=f)
    assert hits
    assert {h.chunk.company_id for h in hits} == {"BETA"}
    assert all(h.chunk.metadata["items"] == ["7"] for h in hits)
    assert index.search("net revenue", filter=SearchFilter(companies=["NONE"])) == []
