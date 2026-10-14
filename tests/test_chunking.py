"""Chunking must be deterministic, bounded and section-local.

These are the properties the citation verifier depends on: a chunk's text must
be a real span of its section, so a quote found in a chunk can be verified.
"""

import pytest

from loupe.core.schemas import Document, Section
from loupe.ingest.chunk import chunk_document, dedupe_chunks, split_text


def test_split_text_covers_everything():
    text = "word " * 500
    spans = split_text(text, size=400, overlap=50)
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)


def test_split_text_respects_max_size():
    text = "x" * 5000
    for start, end in split_text(text, size=800, overlap=100):
        assert end - start <= 800


def test_split_text_spans_are_real_substrings():
    text = "Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph.\n\nDelta."
    for start, end in split_text(text, size=40, overlap=10):
        assert text[start:end] == text[start:end]
        assert end > start


def test_split_text_respects_overlap():
    text = "".join(f"{i:04d} " for i in range(400))
    spans = split_text(text, size=500, overlap=100)
    # Consecutive chunks share about `overlap` characters.
    assert spans[0][1] - spans[1][0] >= 50


def test_split_text_rejects_overlap_at_or_over_size():
    with pytest.raises(ValueError):
        split_text("abc", size=100, overlap=100)
    with pytest.raises(ValueError):
        split_text("abc", size=0)


def test_split_text_empty():
    assert split_text("", size=100, overlap=10) == []


def _document():
    return Document(
        doc_id="doc1",
        company_id="AMD",
        source="sec_edgar",
        form="10-K",
        url="http://example.org",
        content_hash="abc",
        fiscal_year=2024,
    )


def test_chunk_document_never_spans_sections():
    a = Section(
        section_id="s1", doc_id="doc1", title="Item 1", item="1", start_char=0, end_char=100
    )
    b = Section(
        section_id="s2", doc_id="doc1", title="Item 7", item="7", start_char=0, end_char=100
    )
    texts = {
        "s1": "AAAA first section body " * 20,
        "s2": "BBBB second section body " * 20,
    }
    chunks = chunk_document(_document(), [a, b], texts, company_id="AMD", size=200, overlap=40)

    assert chunks
    for chunk in chunks:
        source = texts[chunk.section_id]
        assert chunk.text in source
        # A chunk must not mix content from the other section.
        other = "BBBB" if chunk.section_id == "s1" else "AAAA"
        assert other not in chunk.text


def test_chunk_ids_are_unique_and_ordered():
    section = Section(
        section_id="s1", doc_id="doc1", title="Item 1", item="1", start_char=0, end_char=1000
    )
    text = "sentence number one. " * 100
    chunks = chunk_document(
        _document(), [section], {"s1": text}, company_id="AMD", size=200, overlap=40
    )
    ids = [c.chunk_id for c in chunks]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_chunk_carries_citation_metadata():
    section = Section(
        section_id="s1", doc_id="doc1", title="Item 7", item="7", start_char=0, end_char=1000
    )
    text = "Management's discussion of financial condition. " * 30
    chunks = chunk_document(
        _document(), [section], {"s1": text}, company_id="AMD", size=300, overlap=60
    )
    meta = chunks[0].metadata
    assert meta["item"] == "7"
    assert meta["form"] == "10-K"
    assert meta["fiscal_year"] == 2024


def test_chunks_quote_is_verbatim_in_section_text():
    """The verifier's core assumption, asserted directly."""
    section = Section(
        section_id="s1", doc_id="doc1", title="Item 1A", item="1A", start_char=0, end_char=5000
    )
    text = "We have substantial risks related to supply chain concentration. " * 60
    chunks = chunk_document(
        _document(), [section], {"s1": text}, company_id="AMD", size=400, overlap=80
    )
    assert any("supply chain concentration" in c.text for c in chunks)


def test_tiny_fragments_are_dropped():
    section = Section(
        section_id="s1", doc_id="doc1", title="Item 1", item="1", start_char=0, end_char=10
    )
    chunks = chunk_document(_document(), [section], {"s1": "ok"}, company_id="AMD")
    assert chunks == []


def test_dedupe_chunks():
    section = Section(
        section_id="s1", doc_id="doc1", title="Item 1", item="1", start_char=0, end_char=1000
    )
    text = "Body text for the section. " * 50
    chunks = chunk_document(
        _document(), [section], {"s1": text}, company_id="AMD", size=200, overlap=40
    )
    doubled = chunks + chunks
    assert len(dedupe_chunks(doubled)) == len(chunks)
