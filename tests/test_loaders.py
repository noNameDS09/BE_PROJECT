"""Public-dataset loaders on tiny inline fixtures that mimic each raw format (no data dir)."""

import csv
import json
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from loupe.datasets.loaders import LOADERS
from loupe.datasets.loaders.common import (
    flatten_markdown_tables,
    flatten_table,
    numeric_fields,
    parse_number,
)


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _parquet(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def _load(name: str, root: Path):
    items = list(LOADERS[name](root))
    assert len({i.item_id for i in items}) == len(items)
    assert all(i.item_id.startswith(f"{name}:") and i.dataset == name for i in items)
    return items


# --- number parsing ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("$1,577.00", 1577.0, "USD"),
        ("(2.5)%", -2.5, "%"),
        ("24.3 billion", 24.3e9, None),
        ("1577", 1577.0, None),
        ("-0.02", -0.02, None),
        ("$3.25 Billion", 3.25e9, "USD"),
        ("($1,234)", -1234.0, "USD"),
        ("$(9.8) million", -9.8e6, "USD"),
        ("6.49x", 6.49, "x"),
        ("12%", 12.0, "%"),
        ("₹4,045.8 million", 4045.8e6, "INR"),
        ("1,80,077.92 Lakhs", 180077.92e5, None),
        ("₹91 crores", 91e7, "INR"),
        ("\u22123.7", -3.7, None),  # unicode minus sign
        ("$5m", 5e6, "USD"),
    ],
)
def test_parse_number(text, value, unit):
    p = parse_number(text)
    assert p is not None
    assert p.value == pytest.approx(value)
    assert p.unit == unit


@pytest.mark.parametrize(
    "text",
    ["N/A", "", "Yes", "$400,000,000 increase.", "1.5 - 2.0", "5m", "((2))", "$(5", "Q4 2023"],
)
def test_parse_number_rejects(text):
    assert parse_number(text) is None


def test_numeric_fields_scale_from_question():
    f = numeric_fields("$1577.00", "What is the FY2018 capex (in USD millions) for 3M?")
    assert f["answer_value"] == 1577e6 and f["answer_unit"] == "USD"
    f = numeric_fields("$0.40", "How much (in USD billions) did it pay?")
    assert f["answer_value"] == pytest.approx(0.4e9)
    assert f["tolerance"] == pytest.approx(0.0125)  # widened to the 2-decimal rounding
    f = numeric_fields("2.8", "Answer in units of percents and round to one decimal place.")
    assert f["answer_unit"] == "%"


def test_numeric_fields_rejects_years_and_text():
    assert numeric_fields("2019") is None
    assert numeric_fields("Data Center") is None


def test_flatten_tables():
    assert flatten_table([["", "2019"], ["Sales", "$ 1,496.5"], ["", ""]]) == (
        " | 2019\nSales | $ 1,496.5"
    )
    md = "Intro\n|    | a    | b |\n|---:|:-----|--:|\n|  0 | x    | 1 |"
    assert flatten_markdown_tables(md) == "Intro\na | b\n0 | x | 1"


# --- loaders ------------------------------------------------------------------------------


def test_financebench(tmp_path):
    _jsonl(
        tmp_path / "data" / "financebench_open_source.jsonl",
        [
            {
                "financebench_id": "financebench_id_03029",
                "company": "3M",
                "doc_name": "3M_2018_10K",
                "question_type": "metrics-generated",
                "question_reasoning": "Information extraction",
                "domain_question_num": None,
                "question": "What is the FY2018 capital expenditure (in USD millions) for 3M?",
                "answer": "$1577.00",
                "justification": "Extracted.",
                "dataset_subset_label": "OPEN_SOURCE",
                "evidence": [
                    {
                        "evidence_text": "Purchases of PP&E (1,577)",
                        "doc_name": "3M_2018_10K",
                        "evidence_page_num": "59",
                        "evidence_text_full_page": "...",
                    }
                ],
            },
            {
                "financebench_id": "financebench_id_1",
                "company": "Nike",
                "doc_name": "NIKE_2023_10K",
                "question_type": "domain-relevant",
                "question_reasoning": None,
                "domain_question_num": "dg01",
                "question": "Is Nike capital intensive?",
                "answer": "No, it is not.",
                "justification": "",
                "dataset_subset_label": "OPEN_SOURCE",
                "evidence": [],
            },
        ],
    )
    _jsonl(
        tmp_path / "data" / "financebench_document_information.jsonl",
        [
            {"doc_name": "3M_2018_10K", "company": "3M", "doc_type": "10k", "doc_period": 2018},
            {"doc_name": "NIKE_2023_10K", "company": "Nike", "doc_type": "10k", "doc_period": 2023},
        ],
    )
    num, text = _load("financebench", tmp_path)
    assert num.kind == "numeric" and num.answer_value == 1577e6 and num.answer_unit == "USD"
    assert num.mode == "docs"
    assert num.documents[0].path == "raw/public/financebench/pdfs/3M_2018_10K.pdf"
    assert num.evidence[0].page == 59 and num.companies == ["MMM"] and num.fiscal_year == 2018
    assert num.split == "dev"  # MMM is a dev company
    assert text.kind == "text" and text.companies == [] and text.meta["company_name"] == "Nike"
    assert text.split is None


def test_finder(tmp_path):
    passage = "Total revenues 3,773.5 3,958.5 3,494.8 for the years ended December 31"
    _parquet(
        tmp_path / "data" / "train-00000-of-00001.parquet",
        [
            {
                "_id": "b33fcee7",
                "text": "Delta in CBOE revenue from 2021-23.",
                "reasoning": True,
                "category": "Financials",
                "references": [passage],
                "answer": "Up $278.7 million.",
                "type": "Subtract",
            },
            {
                "_id": "c1",
                "text": "Cboe headcount by country.",  # no ticker: linked through its neighbour
                "reasoning": False,
                "category": "Company overview",
                "references": ["As of December 31, 2023, we employed 1,647 individuals"],
                "answer": "1,647.",
                "type": None,
            },
            {
                "_id": "c2",
                "text": "Something unrelated.",
                "reasoning": False,
                "category": "Risk",
                "references": ["This passage appears in no filing at all, anywhere, ever."],
                "answer": "n/a",
                "type": None,
            },
        ],
    )
    html = (
        "<html><body><div style='display:none'><ix:header>hidden</ix:header></div>"
        "<table><tr><td>Total revenues</td><td>3,773.5</td><td>3,958.5</td><td>3,494.8</td></tr>"
        "</table><p>for the years ended December&nbsp;31</p>"
        "<p>As of December 31, 2023, we employed 1,647 individuals</p></body></html>"
    )
    with zipfile.ZipFile(tmp_path / "10-k.zip", "w") as z:
        z.writestr("10k/CBOE.html", html)
        z.writestr("10k/A.html", "<html>Agilent</html>")
        z.writestr("__MACOSX/10k/._CBOE.html", b"junk")
    a, b, c = _load("finder", tmp_path)
    assert a.meta["doc_link"] == "ticker_in_query" and a.documents[0].doc_id == "finder_10k:CBOE"
    assert a.documents[0].path == "raw/public/finder/10-k.zip#10k/CBOE.html"
    assert a.kind == "text" and a.evidence[0].text == passage and a.category == "Financials"
    assert b.meta["doc_link"] == "neighbour" and b.meta["finder_ticker"] == "CBOE"
    assert c.meta["doc_link"] == "unresolved" and c.documents == []


def test_failsafeqa(tmp_path):
    _json(
        tmp_path / "FAILSAFEQA_benchmark_data-FINAL.jsonl",
        [
            {
                "idx": 0,
                "tokens": 100,
                "query": "What was the market value on July 29, 2017?",
                "answer": "About $607.4 million.",
                "context": "10-K ... market value ... $607.4 million",
                "citations": "market value ... $607.4 million",
                "citations_tokens": 5,
                "error_query": "Waht was the markt value on Juli 29, 2017?",
                "incomplete_query": "market value, July 29, 2017?",
                "out-of-domain_query": "What were outside shares worth on July 29, 2017?",
                "out-of-scope_query": "What does the Ilo smelter deal with?",
                "ocr_context": "10-K ... rnarket va1ue ... $6O7.4 mi11ion",
            }
        ],
    )
    _json(tmp_path / "query_to_class.json", {"What was the market value on July 29, 2017?": "A"})
    items = {i.category: i for i in _load("failsafeqa", tmp_path)}
    assert len(items) == 7
    assert items["baseline"].kind == "text" and items["baseline"].meta["query_class"] == "A"
    assert items["misspelled_query"].question.startswith("Waht")
    assert items["ocr_context"].context.endswith("mi11ion")
    assert items["missing_context"].kind == "refusal" and items["missing_context"].context == ""
    irrelevant = items["irrelevant_context"]
    assert irrelevant.kind == "refusal" and "Ilo" in irrelevant.question
    assert all(i.mode == "context" for i in items.values())


def test_secque(tmp_path):
    context = (
        "AMERICAN EXPRESS CO 10-K form for the fiscal year ended 2023-12-31, page 43: \n"
        "|    | Metric   | 2023   |\n|---:|:---------|:-------|\n|  0 | Revenue  | 60,515 |"
    )
    _jsonl(
        tmp_path / "SECQUE_benchmark_Ratio.jsonl",
        [
            {
                "QID": "q_Ra001",
                "Question": "How did AmEx's ratio evolve?",
                "ground_truth_answer": "It rose.",
                "question_type": "Ratio",
                "page_number": "43, 45",
                "accession_number": "0000004962-24-000013",
                "item": "Item 7. MD&A",
                "context_markdown_with_headers": context,
            }
        ],
    )
    (item,) = _load("secque", tmp_path)
    assert item.mode == "context" and item.kind == "text" and item.category == "Ratio"
    assert "nan" not in item.context and "| Revenue | 60,515" in item.context
    assert "---" not in item.context
    assert item.companies == ["AXP"] and item.fiscal_year == 2023 and item.split == "test"
    assert item.evidence[0].accession == "0000004962-24-000013"
    assert item.meta["pages"] == ["43", "45"]


def test_finance_agent(tmp_path):
    rubric = "[{'operator': 'correctness', 'criteria': 'States $3.25B'}]"
    _csv(
        tmp_path / "finance_agent_benchmark.csv",
        [
            {
                "Question": "How much was the facility?",
                "Answer": "$3.25 Billion",
                "Question Type": "Quantitative Retrieval",
                "Expert time (mins)": "5",
                "Rubric": rubric,
            },
            {
                "Question": "Why did the merger fail?",
                "Answer": "It was blocked.",
                "Question Type": "Market Analysis",
                "Expert time (mins)": "30",
                "Rubric": "[]",
            },
        ],
    )
    num, text = _load("finance_agent_v1", tmp_path)
    assert num.kind == "numeric" and num.answer_value == 3.25e9 and num.mode == "corpus"
    assert num.meta["rubric"][0]["criteria"] == "States $3.25B"
    assert num.meta["expert_time_mins"] == 5
    assert text.kind == "text" and text.item_id == "finance_agent_v1:002"
    v2 = tmp_path / "v2"
    _csv(
        v2 / "data" / "public.csv",
        [
            {
                "Question": "For CRWD, how is AI a tailwind?",
                "Question Type": "General Qualitative Analysis",
                "Expert time (mins)": "60",
                "Rubric": json.dumps([{"operator": "op", "criteria": "Falcon"}]),
            }
        ],
    )
    (q,) = _load("finance_agent_v2", v2)
    assert q.answer is None and q.kind == "text" and q.meta["rubric"][0]["criteria"] == "Falcon"


def _finqa_record(rid: str, answer: str, exe):
    return {
        "pre_text": ["net revenue rose ."],
        "post_text": ["end ."],
        "filename": "ETR/2016/page_23.pdf",
        "table_ori": [["", "Amount"], ["2014 net revenue", "$5,735"], ["2015", "$5,829"]],
        "table": [["", "amount"], ["2014 net revenue", "$ 5735"]],
        "id": rid,
        "qa": {
            "question": "what is the change?",
            "answer": answer,
            "exe_ans": exe,
            "program": "subtract(5829, 5735)",
            "gold_inds": {"table_1": "the 2014 net revenue is $ 5735 ;"},
        },
    }


def test_finqa(tmp_path):
    _json(
        tmp_path / "dataset" / "test.json",
        [
            _finqa_record("a-1", "94", 94.0),
            _finqa_record("a-2", "14%", 0.14464),
            _finqa_record("a-3", "yes", "yes"),
        ],
    )
    _json(tmp_path / "dataset" / "train.json", [_finqa_record("train-1", "1", 1.0)])
    a, b, c = _load("finqa", tmp_path)  # train.json is never read
    assert a.answer_value == 94.0 and a.answer_unit is None and a.split == "test"
    assert "2014 net revenue | $5,735" in a.context
    assert b.answer_value == pytest.approx(14.464) and b.answer_unit == "%"
    assert b.tolerance == pytest.approx(0.5 / 14.464)  # "14%" is rounded to the unit
    assert c.kind == "text" and c.answer == "yes"
    assert a.evidence[0].text.startswith("the 2014")


def test_convfinqa(tmp_path):
    record = {
        "pre_text": ["stock options ."],
        "post_text": ["."],
        "filename": "MRO/2007/page_134.pdf",
        "table_ori": [["", "2007", "2005"], ["price", "$60.94", "$25.14"]],
        "table": [],
        "id": "Single_MRO/2007/page_134.pdf-1",
        "qa": {
            "question": "by how much did the price increase?",
            "answer": "142.4%",
            "exe_ans": 1.42403,
            "gold_inds": {"table_1": "price ..."},
        },
        "annotation": {
            "dialogue_break": ["price in 2007?", "and in 2005?", "change?", "relative change?"],
            "turn_program": ["60.94", "25.14", "subtract(60.94, 25.14)", "divide(#0, 25.14)"],
            "exe_ans_list": [60.94, 25.14, 35.8, 1.42403],
            "qa_split": [0, 0, 0, 0],
        },
    }
    zpath = tmp_path / "data.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("data/dev.json", json.dumps([record]))
        z.writestr("data/train.json", json.dumps([record | {"id": "train"}]))
    (item,) = _load("convfinqa", tmp_path)
    assert item.question == "relative change?"
    assert item.turns == ["price in 2007?", "and in 2005?", "change?"]
    assert item.answer_value == pytest.approx(142.403) and item.answer_unit == "%"
    assert item.meta["turn_answers"] == [60.94, 25.14, 35.8, 1.42403]
    assert item.category == "single" and item.split == "dev"
    assert not (tmp_path / "data").exists()  # read straight from the zip


def test_tatqa(tmp_path):
    doc = {
        "table": {
            "uid": "t1",
            "table": [["", "2019", "2018"], ["Total sales", "$1,496.5", "$1,202.9"]],
        },
        "paragraphs": [{"uid": "p1", "order": 1, "text": "Sales by contract type (in millions)."}],
        "questions": [
            {"uid": "q1", "question": "Sales 2019?", "answer": ["$1,496.5"],
             "answer_type": "span", "scale": "million", "derivation": ""},
            {"uid": "q2", "question": "Change %?", "answer": -22.22,
             "answer_type": "arithmetic", "scale": "percent", "derivation": "(44.1-56.7)/56.7"},
            {"uid": "q3", "question": "Largest year?", "answer": ["2019"],
             "answer_type": "span", "scale": ""},
            {"uid": "q4", "question": "Types?", "answer": ["fixed", "cost-plus"],
             "answer_type": "multi-span", "scale": ""},
        ],
    }  # fmt: skip
    _json(tmp_path / "dataset_raw" / "tatqa_dataset_dev.json", [doc])
    test_doc = json.loads(json.dumps(doc))
    for q in test_doc["questions"]:
        q["uid"] += "t"
    _json(tmp_path / "dataset_raw" / "tatqa_dataset_test_gold.json", [test_doc])
    items = _load("tatqa", tmp_path)
    assert [i.split for i in items] == ["dev"] * 4 + ["test"] * 4
    span, pct, year, multi = items[:4]
    assert span.answer_value == pytest.approx(1496.5e6) and span.answer_unit == "USD"
    assert pct.answer_value == pytest.approx(-22.22) and pct.answer_unit == "%"
    assert year.kind == "text" and multi.kind == "text" and multi.answer == "fixed; cost-plus"
    assert span.context.startswith(" | 2019 | 2018\nTotal sales | $1,496.5")


def test_indfin_bench(tmp_path):
    _csv(
        tmp_path / "IndFin-Bench.csv",
        [
            {"Question_Num": "1", "Question": "ROU assets?", "Complexity_Category": "Single",
             "Atomic_Fact": "₹4,045.8 million"},
            {"Question_Num": "2", "Question": "Who is CFO?", "Complexity_Category": "Single",
             "Atomic_Fact": "Ms. Rao is the CFO."},
        ],
    )  # fmt: skip
    a, b = _load("indfin_bench", tmp_path)
    assert a.item_id == "indfin_bench:001" and a.kind == "numeric" and a.answer_unit == "INR"
    assert b.kind == "text" and b.mode == "corpus"


def test_indiafinbench(tmp_path):
    row = {
        "id": "indiafinbench_REG_062",
        "task_type": "regulatory_interpretation",
        "difficulty": "easy",
        "source": "SEBI",
        "context": "within twenty one days",
        "question": "Within how many days?",
        "reference_answer": "Twenty one days",
        "source_document": "SEBI_2015.txt",
    }
    _parquet(tmp_path / "data" / "dev-00000-of-00001.parquet", [row])
    _parquet(
        tmp_path / "data" / "test-00000-of-00001.parquet",
        [row | {"id": "indiafinbench_NUM_001", "reference_answer": "11.5%"}],
    )
    dev, test = _load("indiafinbench", tmp_path)
    assert dev.item_id == "indiafinbench:REG_062" and dev.split == "dev" and dev.kind == "text"
    assert dev.mode == "context" and dev.context == "within twenty one days"
    assert test.kind == "numeric" and test.answer_value == 11.5 and test.split == "test"


def test_registry_covers_configured_datasets():
    import yaml

    from loupe.datasets.universe import REPO_ROOT

    configured = yaml.safe_load((REPO_ROOT / "configs" / "datasets.yaml").read_text())["datasets"]
    expected = {n for n, cfg in configured.items() if not cfg.get("defer")}
    assert expected == set(LOADERS)
