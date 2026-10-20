import json
from types import SimpleNamespace

import pytest

from loupe.core.schemas import Answer, Citation, Claim, TraceStep
from loupe.eval import runner as runner_mod
from loupe.eval.metrics import numeric_correct, plan_scores, retrieval_recall, support_stats
from loupe.eval.report import leaderboard, stages
from loupe.eval.runner import Runner, RunSpec, select
from loupe.eval.schema import EvalItem, GoldEvidence, ResultRow
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


def test_limited_runs_sample_across_companies_reproducibly():
    items = [
        item(item_id=f"t:{c}{i}", companies=[c], split="dev") for c in "ABCD" for i in range(5)
    ]
    spec = RunSpec(dataset="t", arms=["b0"], models=["m"], limit=8)
    first = select(items, spec)
    assert len(first) == 8 and {i.companies[0] for i in first} == set("ABCD")
    assert [i.item_id for i in select(items, spec)] == [i.item_id for i in first]


def test_docs_index_reads_html_inside_a_zip(tmp_path):
    import zipfile

    from loupe.eval.docs_index import collect_chunks

    with zipfile.ZipFile(tmp_path / "docs.zip", "w") as zf:
        zf.writestr(
            "10k/ACME.html",
            "<html><body><p>" + "Revenue rose because demand grew. " * 60 + "</p></body></html>",
        )
    it = item(
        mode="docs", documents=[{"doc_id": "finder_10k:ACME", "path": "docs.zip#10k/ACME.html"}]
    )
    chunks = collect_chunks([it], tmp_path, size=400, overlap=50)
    assert chunks and all(c.doc_id == "finder_10k:ACME" for c in chunks)
    assert "Revenue rose" in chunks[0].text and "<p>" not in chunks[0].text


def test_retrieval_matching_and_scores():
    from loupe.core.schemas import Chunk
    from loupe.eval.retrieval import evaluate, matches
    from loupe.index.search import Hit

    gold_page = GoldEvidence(doc_id="D", page=3)
    gold_text = GoldEvidence(
        text="net revenue increased by twelve percent driven by data center demand this year"
    )
    c1 = Chunk(
        chunk_id="a",
        doc_id="D",
        company_id="X",
        text="unrelated text about leases",
        start_char=0,
        end_char=1,
        page=1,
    )
    c2 = Chunk(
        chunk_id="b",
        doc_id="D",
        company_id="X",
        start_char=0,
        end_char=1,
        page=3,
        text="In 2024 net revenue increased by twelve percent driven by data center demand "
        "this year.",
    )
    assert not matches(c1, gold_page) and matches(c2, gold_page) and matches(c2, gold_text)

    class R:
        def retrieve(self, q, filter=None):
            return [Hit(chunk=c1, score=1), Hit(chunk=c2, score=0.5)]

    it = item(mode="docs", documents=[{"doc_id": "D"}], evidence=[gold_page])
    s = evaluate([it, item(item_id="t:none")], R())  # second item has no evidence: skipped
    assert s.n == 1 and s.recall_at[1] == 0.0 and s.recall_at[3] == 1.0 and s.mrr == 0.5


def test_export_import_round_trip(tmp_path):
    from datetime import UTC, datetime

    from loupe.eval.store import export_results, import_results

    a = ResultStore(tmp_path / "a.duckdb", tmp_path / "ra")
    a.add(
        ResultRow(
            run_id="r1",
            item_id="t:1",
            dataset="t",
            arm="b0",
            model="m",
            config_hash="h",
            answer="x",
            correct=1.0,
            created_at=datetime.now(UTC),
            meta={"split": "dev"},
        ),
        Answer(text="x"),
    )
    assert export_results(a, tmp_path / "out.zip") == 1
    b = ResultStore(tmp_path / "b.duckdb", tmp_path / "rb")
    assert import_results(b, tmp_path / "out.zip") == 1
    assert import_results(b, tmp_path / "out.zip") == 1  # idempotent (keyed by run_id)
    assert len(b.rows()) == 1 and b.answer("r1").text == "x"
