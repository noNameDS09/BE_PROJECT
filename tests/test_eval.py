import json
from types import SimpleNamespace

import pytest

from loupe.core.schemas import Answer, Citation, Claim, TraceStep
from loupe.eval import runner as runner_mod
from loupe.eval.metrics import numeric_correct, plan_scores, retrieval_recall, support_stats
from loupe.eval.report import leaderboard, stages
from loupe.eval.runner import Runner, RunSpec, select
from loupe.eval.schema import EvalItem, GoldEvidence
from loupe.eval.stats import cluster_bootstrap, paired_difference
from loupe.eval.store import ResultStore
from tests.test_orchestrators import FakeTools, ScriptedGateway, reply


def item(**kw):
    base = dict(item_id="t:1", dataset="t", question="q", kind="numeric", answer_value=25_785e6)
    return EvalItem(**{**base, **kw})


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("Revenue was $25.8 billion.", True),
        ("Revenue was 25,785 million.", True),
        ("Revenue was $25,785,000,000.", True),
        ("Revenue was $27 billion.", False),
        ("No numbers here.", False),
    ],
)
def test_numeric_correct_accepts_units_and_rounding_within_tolerance(text, ok):
    assert numeric_correct(text, item()) is ok


def test_numeric_correct_percent_as_fraction():
    assert numeric_correct("Margin was 0.462", item(answer_value=46.2, answer_unit="%"))


def test_support_stats_and_plan_scores():
    a = Answer(text="x", claims=[Claim(text="a", supported=True), Claim(text="b", supported=False),
                                 Claim(text="c", supported=None)])  # fmt: skip
    assert support_stats(a) == (0.5, True)
    a.trace = [
        TraceStep(stage="tool", name="get_financial_metric"),
        TraceStep(stage="tool", name="calculate"),
    ]
    assert plan_scores(a, item(kind="plan", expected_tools=["get_financial_metric"])) == {
        "tool_recall": 1.0, "tool_precision": 0.5}  # fmt: skip


def test_retrieval_recall_by_page_and_by_text():
    cit = {"doc_id": "D", "page": 4}
    ev = {"kind": "chunk", "text": "Total revenue was 3,000", "citation": cit}
    a = Answer(text="x", evidence=[ev])
    assert retrieval_recall(a, item(evidence=[GoldEvidence(doc_id="D", page=4)])) == 1.0
    assert retrieval_recall(a, item(evidence=[GoldEvidence(doc_id="D", page=5)])) == 0.0
    assert retrieval_recall(a, item(evidence=[GoldEvidence(text="Total revenue was 3,000")])) == 1.0


def test_cluster_bootstrap_and_paired_difference():
    est = cluster_bootstrap([1, 1, 0, 1, 0, 0], ["A", "A", "B", "B", "C", "C"])
    assert est.mean == pytest.approx(0.5) and est.lo <= 0.5 <= est.hi and est.n == 6
    assert cluster_bootstrap([None], ["A"]).mean is None
    d = paired_difference(
        {"i1": 1, "i2": 1, "i3": 0}, {"i1": 0, "i2": 1, "i3": 0}, {"i1": "A", "i2": "B", "i3": "C"}
    )
    assert d.mean == pytest.approx(1 / 3)


def test_test_split_needs_final_flag():
    items = [item(split="test")]
    with pytest.raises(PermissionError):
        select(items, RunSpec(dataset="t", arms=["b0"], models=["m"], split="test"))
    assert select(items, RunSpec(dataset="t", arms=["b0"], models=["m"], split="test", final=True))


class FakeEngine:
    def __init__(self, tmp_path, gateway):
        self.settings = SimpleNamespace(data_dir=tmp_path)
        self.gateway = gateway
        self.facts = None
        self.companies = []

    def tools(self, retrieval=None):
        return FakeTools()

    def reranker(self, name):
        return None


def test_runner_scores_stores_resumes_and_reports(tmp_path, monkeypatch):
    items = [
        item(item_id="t:1", companies=["AMD"], split="dev"),
        item(item_id="t:2", kind="refusal", answer="Should refuse", companies=["PEP"], split="dev"),
        item(item_id="t:3", mode="context", context="Revenue was 25,785 million.", split="dev"),
    ]
    (tmp_path / "processed" / "eval").mkdir(parents=True)
    (tmp_path / "processed" / "eval" / "t.jsonl").write_text(
        "\n".join(i.model_dump_json() for i in items)
    )
    monkeypatch.setattr(
        runner_mod, "dataset_path", lambda d, n: d / "processed" / "eval" / f"{n}.jsonl"
    )
    gw = ScriptedGateway(
        reply("AMD revenue was $25.8 billion."),
        reply("That information is not reported."),
        reply("Revenue was 25,785 million [E1]."),
    )
    store = ResultStore(tmp_path / "results.duckdb", tmp_path / "runs")
    r = Runner(FakeEngine(tmp_path, gw), store, log=tmp_path / "log.md")
    spec = RunSpec(dataset="t", arms=["b0"], models=["m"])

    rows = r.run(spec)
    assert [row.correct for row in rows] == [1.0, 1.0, 1.0]
    assert rows[0].hallucinated is True  # number with no citation = unsupported claim
    assert rows[2].hallucinated is False  # cites the preloaded context [E1]
    assert "Context [E1]" in gw.requests[2]["messages"][-1]["content"]
    assert r.run(spec) == []  # resumed: nothing left to do
    assert store.answer(rows[0].run_id).text.startswith("AMD revenue")

    board = leaderboard(store.rows())
    assert board[0]["n"] == 3 and board[0]["metrics"]["accuracy"]["mean"] == 1.0
    assert stages(store.rows())[0]["arm"] == "b0"


def test_runner_records_errors_without_stopping(tmp_path, monkeypatch):
    (tmp_path / "t.jsonl").write_text(item(split="dev").model_dump_json())
    monkeypatch.setattr(runner_mod, "dataset_path", lambda d, n: tmp_path / "t.jsonl")
    store = ResultStore(tmp_path / "r.duckdb", tmp_path / "runs")
    rows = Runner(FakeEngine(tmp_path, ScriptedGateway()), store).run(
        RunSpec(dataset="t", arms=["b0"], models=["m"])
    )
    assert rows[0].error and "IndexError" in rows[0].error
    assert json.loads(store.rows()[0]["meta"])["kind"] == "numeric"
    assert Citation()  # schema import smoke
