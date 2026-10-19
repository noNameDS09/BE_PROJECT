from datetime import date

import numpy as np
import pytest

from loupe.core.schemas import Chunk
from loupe.index.retriever import RetrievalConfig, Retriever
from loupe.index.search import Hit
from loupe.tools.charts import series_figure
from loupe.tools.distress import zone
from loupe.tools.facts import FactResult
from loupe.tools.forecast import forecast


def test_forecast_picks_a_trend_method_for_a_steady_trend_and_reports_baseline():
    fc = forecast([100, 110, 120, 130, 140, 150], horizon=2)
    assert fc.method in {"drift", "linear_trend", "holt_damped"}
    assert fc.points[0] == pytest.approx(160, rel=0.02)
    assert fc.backtest_mape < fc.naive_mape
    assert all(lo <= p <= hi for p, lo, hi in zip(fc.points, fc.lower, fc.upper, strict=True))


def test_forecast_flat_series_and_short_history_note():
    fc = forecast([50, 50, 50])
    assert fc.points == [pytest.approx(50)] and "Short history" in fc.note
    with pytest.raises(ValueError):
        forecast([1])


def test_distress_zones():
    assert [zone(3.0), zone(2.0), zone(0.5)] == ["safe", "grey", "distress"]


def fact(year, value):
    return FactResult(
        company_id="AMD", metric="revenue", fiscal_year=year, fiscal_period="FY", value=value,
        unit="USD", concept="Revenues", period_start=None, period_end=date(year, 12, 31),
        accession="a", form="10-K", filed=None, url="u",
    )  # fmt: skip


def test_chart_figure_scales_units_and_adds_forecast_band():
    fc = forecast([20e9, 22e9, 24e9, 26e9])
    fig = series_figure(
        "Revenue",
        {
            "AMD": [
                fact(y, v) for y, v in zip(range(2021, 2025), [20e9, 22e9, 24e9, 26e9], strict=True)
            ]
        },
        forecast={"AMD": fc},
    )
    assert fig["layout"]["yaxis"]["title"]["text"] == "USD billions"
    assert fig["data"][0]["y"] == [20, 22, 24, 26]
    assert [d["name"] for d in fig["data"]][1].startswith("AMD forecast")


class FakeIndex:
    def __init__(self, ranked):
        self.ranked = ranked  # query -> list of chunk ids in rank order

    def search(self, q, k, filter=None, mode="hybrid"):
        return [Hit(chunk=chunk(c), score=1.0) for c in self.ranked.get(q, [])[:k]]


def chunk(cid):
    return Chunk(
        chunk_id=cid, doc_id="d", company_id="AMD", text=f"text {cid}", start_char=0, end_char=1
    )


class ReverseReranker:
    def scores(self, query, passages):
        return np.arange(len(passages), dtype=np.float32)  # prefers the last candidate


def test_retriever_fuses_query_variants_and_reranks():
    index = FakeIndex({"q": ["a", "b", "c"], "q2": ["c", "d"]})
    plain = Retriever(index, RetrievalConfig(k=2, rerank=None))
    assert [h.chunk.chunk_id for h in plain.retrieve("q", extra_queries=["q2"])] == ["c", "a"]
    reranked = Retriever(index, RetrievalConfig(k=2, rerank="minilm-l12"), ReverseReranker())
    assert [h.chunk.chunk_id for h in reranked.retrieve("q")] == ["c", "b"]
