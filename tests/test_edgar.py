import json
from datetime import date

import httpx
import pytest

from loupe.sources.us import edgar
from loupe.sources.us.sec_client import SecClient
from loupe.sources.us.universe import eligibility, latest_annual_revenue

UA = "Loupe test test@example.edu"


def columns(rows):
    keys = ["accessionNumber", "filingDate", "reportDate", "form", "items", "primaryDocument"]
    out = {k: [r[i] for r in rows] for i, k in enumerate(keys)}
    out["size"] = [100] * len(rows)
    return out


RECENT = columns(
    [
        ("0001-25-000003", "2025-02-01", "2024-12-31", "10-K", "", "k24.htm"),
        ("0001-24-000009", "2024-08-01", "2024-07-31", "8-K", "2.02,9.01", "e.htm"),
        ("0001-24-000008", "2024-05-01", "2024-03-31", "10-Q", "", "q1.htm"),
        ("0001-24-000007", "2024-03-01", "2023-12-31", "10-K/A", "", "ka.htm"),
    ]
)
OLDER = columns([("0001-22-000001", "2022-02-01", "2021-12-31", "10-K", "", "k21.htm")])


def make_client(tmp_path, routes, calls=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        assert request.headers["user-agent"] == UA
        body = routes.get(str(request.url))
        if body is None:
            return httpx.Response(404)
        if isinstance(body, httpx.Response):
            return body
        return httpx.Response(200, content=body if isinstance(body, bytes) else json.dumps(body))

    return SecClient(
        UA, tmp_path / "sec", transport=httpx.MockTransport(handler), sleep=lambda s: None
    )


def test_user_agent_must_name_a_contact(tmp_path):
    with pytest.raises(ValueError):
        SecClient("Loupe", tmp_path)


def test_responses_are_cached_on_disk(tmp_path):
    calls = []
    url = "https://data.sec.gov/x.json"
    client = make_client(tmp_path, {url: {"a": 1}}, calls)

    assert client.get_json(url) == {"a": 1}
    assert client.get_json(url) == {"a": 1}
    assert len(calls) == 1
    assert (tmp_path / "sec" / "data.sec.gov" / "x.json").exists()


def test_rate_limited_responses_are_retried(tmp_path):
    url = "https://data.sec.gov/y.json"
    replies = iter([httpx.Response(429), httpx.Response(200, content=b"{}")])
    client = SecClient(
        UA,
        tmp_path,
        transport=httpx.MockTransport(lambda r: next(replies)),
        sleep=lambda s: None,
    )
    assert client.get_json(url) == {}


def test_submissions_merges_older_pages_and_window_excludes_amendments(tmp_path):
    meta = {
        "name": "ACME",
        "filings": {
            "recent": RECENT,
            "files": [{"name": "CIK0000000001-submissions-001.json", "filingTo": "2022-12-31"}],
        },
    }
    routes = {
        "https://data.sec.gov/submissions/CIK0000000001.json": meta,
        "https://data.sec.gov/submissions/CIK0000000001-submissions-001.json": OLDER,
    }
    client = make_client(tmp_path, routes)

    subs = edgar.submissions(client, "1")
    assert len(subs["filings"]) == 5
    assert len(edgar.submissions(client, "1", since=date(2023, 1, 1))["filings"]) == 4

    window = edgar.select_window(
        subs["filings"], date(2023, 1, 1), date(2025, 12, 31), ("10-K", "10-Q", "8-K")
    )
    assert [f.form for f in window] == ["10-Q", "8-K", "10-K"]
    assert window[1].items == ["2.02", "9.01"]
    assert window[2].url == "https://www.sec.gov/Archives/edgar/data/1/000125000003/k24.htm"


INDEX_PAGE = """
<table class="tableFile" summary="Document Format Files">
<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr><td>1</td><td>8-K</td><td><a href="/x/e.htm">e.htm</a> &nbsp;&nbsp;iXBRL</td>
<td>8-K</td><td>31546</td></tr>
<tr class="evenRow"><td>2</td><td>PRESS RELEASE</td><td><a href="/x/ex991.htm">ex991.htm</a></td>
<td>EX-99.1</td><td>90000</td></tr>
<tr><td>&nbsp;</td><td>Complete submission text file</td><td><a href="/x/a.txt">a.txt</a></td>
<td>&nbsp;</td><td>204943</td></tr>
</table>
"""


def test_index_page_is_parsed_into_typed_documents():
    docs = edgar.parse_index(INDEX_PAGE)
    assert [(d.name, d.type) for d in docs] == [
        ("e.htm", "8-K"),
        ("ex991.htm", "EX-99.1"),
        ("a.txt", ""),
    ]


def test_download_filing_fetches_primary_and_requested_exhibits(tmp_path):
    ref = edgar.FilingRef(
        cik="0000000001",
        accession="0001-24-000009",
        form="8-K",
        filing_date=date(2024, 8, 1),
        report_date=None,
        items=["2.02"],
        primary_document="e.htm",
    )
    base = "https://www.sec.gov/Archives/edgar/data/1/000124000009/"
    routes = {
        base + "0001-24-000009-index.htm": INDEX_PAGE.encode(),
        base + "e.htm": b"<html>8-K</html>",
        base + "ex991.htm": b"<html>release</html>",
    }
    client = make_client(tmp_path, routes)

    paths = edgar.download_filing(client, ref, ("EX-99.1",))
    assert [p.name for p in paths] == ["e.htm", "ex991.htm"]
    assert paths[1].read_bytes() == b"<html>release</html>"


def test_eligibility_counts_window_filings_and_risk_items():
    filings = [
        edgar.FilingRef(
            cik="1",
            accession=f"a{i}",
            form=form,
            filing_date=date(2024, 1, i + 1),
            report_date=date(2023, 12, 31),
            items=items,
            primary_document="x.htm",
        )
        for i, (form, items) in enumerate(
            [("10-K", []), ("10-Q", []), ("8-K", ["4.02", "9.01"]), ("8-K", ["5.02"])]
        )
    ]
    e = eligibility(filings, date(2023, 1, 1), date(2025, 12, 31))
    assert (e.n_10k, e.n_10q, e.n_8k) == (1, 1, 2)
    assert e.risk_items == {"4.02": 1}
    assert not e.eligible()


def test_latest_annual_revenue_ignores_quarters_and_takes_latest_year():
    usd = [
        {"start": "2023-01-01", "end": "2023-12-31", "val": 10, "form": "10-K"},
        {"start": "2024-01-01", "end": "2024-12-31", "val": 12, "form": "10-K"},
        {"start": "2024-10-01", "end": "2024-12-31", "val": 4, "form": "10-K"},
        {"start": "2025-01-01", "end": "2025-03-31", "val": 3, "form": "10-Q"},
    ]
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": usd}}}}}
    assert latest_annual_revenue(facts) == (12.0, "2024-12-31")


def test_stratified_split_is_reproducible_and_spreads_dev_across_sectors():
    from loupe.sources.us.universe import stratified_split

    sectors = {f"C{i}": s for i, s in enumerate("AAAAABBBBCCCDDDEEFF")}
    a = stratified_split(sectors, n_dev=6, seed=7)
    b = stratified_split(sectors, n_dev=6, seed=7)

    assert a == b
    dev = [k for k, v in a.items() if v == "dev"]
    assert len(dev) == 6
    assert len({sectors[k] for k in dev}) == 6  # one per sector at this size
