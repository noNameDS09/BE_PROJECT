from loupe.ingest import sections
from loupe.ingest.html_text import html_to_text

HTML = """<html><body>
<div style="display:none"><ix:header>hidden xbrl</ix:header></div>
<p>Table of Contents</p>
<table><tr><td>Item 1A.</td><td>Risk Factors</td><td>12</td></tr>
<tr><td>Item 7.</td><td>Management's Discussion and Analysis</td><td>30</td></tr></table>
<p>PART I</p>
<p>Item 1A. Risk Factors.</p><p>Our supply chain may be disrupted.</p>
<p>Item 7. Management's Discussion and Analysis.</p>
<table><tr><td>Net revenue</td><td>$</td><td>91,854</td></tr></table>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk.</p>
<p>Included in Item 7.</p>
</body></html>"""


def test_html_to_text_drops_hidden_xbrl_and_keeps_table_rows():
    text = html_to_text(HTML)
    assert "hidden xbrl" not in text
    assert "Net revenue | 91,854" in text


def test_10k_sections_skip_toc_rows_and_keep_short_real_items():
    text = html_to_text(HTML)
    spans = sections.split("10-K", text)
    assert [s.item for s in spans] == ["1A", "7", "7A"]
    body = text[spans[0].start : spans[0].end]
    assert body.startswith("Item 1A. Risk Factors.") and "supply chain" in body
    assert "Included in Item 7." in text[spans[2].start : spans[2].end]


def test_10q_items_are_prefixed_with_their_part():
    text = "PART I\nItem 1. Financial Statements\nx\nItem 2. MD&A\ny\nPART II\nItem 1. Legal\nz\n"
    assert [s.item for s in sections.split("10-Q", text)] == ["I-1", "I-2", "II-1"]


def test_8k_items_are_found():
    text = (
        "Item 2.02 Results of Operations and Financial Condition.\nOn May 1...\n"
        "Item 9.01 Financial Statements and Exhibits.\n(d) Exhibits\n"
    )
    assert [s.item for s in sections.split("8-K", text)] == ["2.02", "9.01"]
