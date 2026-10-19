import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from loupe.api import app as api
from loupe.core.schemas import Company, Document, Section
from loupe.eval.schema import EvalItem
from loupe.eval.store import ResultStore
from loupe.llm.registry import ModelRegistry, ModelSpec
from loupe.orchestrators import RunContext
from tests.test_orchestrators import FakeTools, ScriptedGateway, reply


class FakeEngine:
    def __init__(self, data_dir, gateway):
        self.settings = SimpleNamespace(data_dir=data_dir)
        self.gateway = gateway
        self.gateway.registry = ModelRegistry(
            {"m": ModelSpec(alias="m", model="ollama_chat/x", provider="ollama")}
        )
        self.index_path = data_dir / "processed" / "index" / "c1200o150-bge-small"
        self.companies = [
            Company(
                id="AMD", name="AMD", country="US", sector="IT", group="financebench", split="dev"
            )
        ]
        self.facts = None

    def context(self, model, retrieval=None, tools_enabled=True, max_steps=8):
        return RunContext(gateway=self.gateway, model=model, tools=FakeTools())

    def tools(self, retrieval=None):
        return FakeTools()

    def reranker(self, name):
        return None


@pytest.fixture
def client(tmp_path, monkeypatch):
    gw = ScriptedGateway()
    eng = FakeEngine(tmp_path, gw)
    (tmp_path / "processed" / "eval").mkdir(parents=True)
    item = EvalItem(
        item_id="demo:1",
        dataset="demo",
        question="AMD revenue FY2024?",
        kind="numeric",
        answer="$25,785 million",
        answer_value=25_785e6,
        split="dev",
        companies=["AMD"],
    )
    (tmp_path / "processed" / "eval" / "demo.jsonl").write_text(item.model_dump_json())
    sec = tmp_path / "processed" / "sec"
    (sec / "text").mkdir(parents=True)
    text = "Item 7. MD&A\nRevenue was $25.8 billion, driven by data center demand.\n"
    doc = Document(
        doc_id="AMD_10-K_a",
        company_id="AMD",
        source="t",
        form="10-K",
        url="https://sec/x",
        content_hash="h",
        sections=[
            Section(
                section_id="s", doc_id="d", title="MD&A", item="7", start_char=0, end_char=len(text)
            )
        ],
    )
    (sec / "documents.jsonl").write_text(doc.model_dump_json())
    (sec / "text" / "AMD_10-K_a.txt").write_text(text)
    for fn in (api.engine, api.store, api.runner, api._items, api._documents):
        fn.cache_clear()
    monkeypatch.setattr(api, "engine", lambda: eng)
    st = ResultStore(tmp_path / "results.duckdb", tmp_path / "runs")
    monkeypatch.setattr(api, "store", lambda: st)
    monkeypatch.setattr(
        api, "_dataset_files", lambda: {"demo": tmp_path / "processed" / "eval" / "demo.jsonl"}
    )
    c = TestClient(api.app)
    c.gateway = gw
    return c


def test_health_and_config(client):
    assert client.get("/api/health").json()["ok"] is True
    cfg = client.get("/api/config").json()
    assert {a["name"] for a in cfg["arms"]} >= {
        "b0",
        "rag",
        "react",
        "plan_execute",
        "router",
        "self_refine",
        "loupe",
    }
    assert cfg["models"] == [{"alias": "m", "provider": "ollama", "available": True}]
    assert cfg["datasets"] == [{"name": "demo", "items": 1, "kinds": ["numeric"]}]
    assert cfg["companies"][0]["group"] == "financebench"


def test_compare_runs_each_config_and_scores_dataset_items(client):
    client.gateway.replies += [reply("AMD revenue was $25.8 billion."), reply("I don't know.")]
    body = {
        "item_id": "demo:1",
        "configs": [{"arm": "b0", "model": "m"}, {"arm": "b0", "model": "m"}],
    }
    res = client.post("/api/compare", json=body).json()["results"]
    assert [r["gold"]["correct"] for r in res] == [1.0, 0.0]
    assert res[0]["answer"]["claims"][0]["supported"] is False  # number with no citation


def test_run_errors_are_returned_in_the_result(client):
    res = client.post("/api/runs", json={"question": "q", "arm": "b0", "model": "m"}).json()
    assert res["error"].startswith("IndexError") and res["answer"] is None  # scripted model ran out
    assert (
        client.post("/api/runs", json={"question": "q", "arm": "nope", "model": "m"}).status_code
        == 400
    )


def test_chat_uses_history(client):
    client.gateway.replies += (
        [reply("route-json-missing")] + [reply("DONE")] * 3 + [reply("Answer.")] * 3
    )
    res = client.post(
        "/api/chat",
        json={
            "model": "m",
            "messages": [
                {"role": "user", "content": "Tell me about AMD"},
                {"role": "assistant", "content": "AMD makes chips."},
                {"role": "user", "content": "And its revenue?"},
            ],
        },
    ).json()
    assert "Conversation so far" in res["question"] and res["arm"] == "loupe"


def test_dataset_items_and_documents(client):
    items = client.get("/api/datasets/demo/items", params={"q": "amd"}).json()
    assert items["total"] == 1 and items["items"][0]["item_id"] == "demo:1"
    assert client.get("/api/datasets/nope/items").status_code == 404
    doc = client.get(
        "/api/documents/AMD_10-K_a", params={"start": 13, "end": 40, "context": 5}
    ).json()
    assert doc["highlight"] == [5, 32] and doc["text"][5:32] == "Revenue was $25.8 billion, "[:27]
    assert client.get("/api/documents/missing").status_code == 404


def test_results_endpoints_reflect_stored_runs(client, tmp_path):
    from datetime import UTC, datetime

    from loupe.eval.schema import ResultRow

    st = api.store()
    for i, ok in enumerate([1.0, 0.0]):
        st.add(
            ResultRow(
                run_id=f"r{i}",
                item_id=f"demo:{i}",
                dataset="demo",
                arm="b0",
                model="m",
                config_hash="h",
                answer="a",
                correct=ok,
                created_at=datetime.now(UTC),
                meta={"companies": ["AMD"], "split": "dev"},
            ),
            None,
        )
    board = client.get(
        "/api/results/leaderboard", params={"dataset": "demo", "split": "dev"}
    ).json()
    assert board["rows"][0]["metrics"]["accuracy"]["mean"] == 0.5
    assert client.get("/api/results/stages").json()["steps"][0]["arm"] == "b0"
    wrong = client.get("/api/results/runs", params={"correct": False}).json()["rows"]
    assert [r["run_id"] for r in wrong] == ["r1"]
    assert json.dumps(wrong)  # serialisable
