from loupe.agent.evidence import Ledger
from loupe.agent.verify import parse_numbers, verify
from loupe.core.schemas import Citation, Company
from loupe.llm.gateway import Completion, ToolCall
from loupe.orchestrators import ARMS, RunContext


class ScriptedGateway:
    """Returns pre-written completions in order and records every request."""

    def __init__(self, *replies: Completion):
        self.replies = list(replies)
        self.requests = []

    def complete(self, alias, messages, **kw):
        self.requests.append({"messages": [dict(m) for m in messages], **kw})
        return self.replies.pop(0)


class FakeTools:
    def __init__(self):
        self.calls = []
        self.companies = [Company(id="AMD", name="Advanced Micro Devices", country="US")]
        self.metric_names = ["revenue"]

    def specs(self, names=None):
        all_specs = [
            {"type": "function", "function": {"name": n, "description": n,
             "parameters": {"type": "object", "properties": {}, "required": []}}}
            for n in ("get_financial_metric", "search_filings", "calculate")
        ]  # fmt: skip
        return [x for x in all_specs if names is None or x["function"]["name"] in names]

    def call(self, name, args, ledger: Ledger):
        self.calls.append((name, args))
        if name == "calculate":
            from loupe.tools.calc import calculate

            value = calculate(args["expression"])
            ev = ledger.add("calc", f"{args['expression']} = {value}", Citation(), value)
        elif name == "get_financial_metric":
            ev = ledger.add(
                "fact",
                "AMD revenue FY2024: 25785000000 USD",
                Citation(fact_id="a1"),
                25_785_000_000,
            )
        else:
            ev = ledger.add(
                "chunk", "Data center demand drove revenue growth.", Citation(chunk_id="c1")
            )
        return f"[{ev.id}] {ev.text}"


def reply(text=None, *calls):
    return Completion(
        alias="m", model="m", text=text, tool_calls=list(calls), tokens_in=10, tokens_out=5
    )


def ctx(gateway):
    return RunContext(gateway=gateway, model="m", tools=FakeTools())


ARGS = {"company": "AMD", "metric": "revenue", "fiscal_year": 2024}


def test_react_calls_tools_then_answers_with_verified_citations():
    gw = ScriptedGateway(
        reply(None, ToolCall(id="t1", name="get_financial_metric", arguments=ARGS)),
        reply("AMD revenue in fiscal 2024 was $25.8 billion [E1]."),
    )  # fmt: skip
    c = ctx(gw)
    answer = ARMS["react"].run("What was AMD's FY2024 revenue?", c)

    assert c.tools.calls == [
        ("get_financial_metric", {"company": "AMD", "metric": "revenue", "fiscal_year": 2024})
    ]
    tool_msg = gw.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "t1"
    assert [cl.supported for cl in answer.claims] == [True]
    assert answer.tokens == 30 and [s.stage for s in answer.trace] == ["step", "tool", "step"]


def test_wrong_number_with_citation_is_flagged():
    gw = ScriptedGateway(
        reply(None, ToolCall(id="t1", name="get_financial_metric", arguments={})),
        reply("AMD revenue was $27 billion [E1]."),
    )
    answer = ARMS["react"].run("q", ctx(gw))
    assert [cl.supported for cl in answer.claims] == [False]


def test_react_answers_when_step_budget_runs_out():
    loop = [
        reply(None, ToolCall(id=f"t{i}", name="search_filings", arguments={"query": "x"}))
        for i in range(8)
    ]
    gw = ScriptedGateway(*loop, reply("Demand drove growth [E1]."))
    answer = ARMS["react"].run("q", ctx(gw))
    assert answer.text == "Demand drove growth [E1]."
    assert "tools" not in gw.requests[-1]


def test_rag_retrieves_once_and_closed_book_uses_no_tools():
    rag_ctx = ctx(ScriptedGateway(reply("Growth came from data center demand [E1].")))
    rag = ARMS["rag"].run("Why did revenue grow?", rag_ctx)
    assert rag_ctx.tools.calls == [("search_filings", {"query": "Why did revenue grow?"})]
    assert rag.claims[0].supported is True

    b0_ctx = ctx(ScriptedGateway(reply("AMD earned $26.1 billion in 2024.")))
    b0 = ARMS["b0"].run("q", b0_ctx)
    assert b0_ctx.tools.calls == [] and b0.claims[0].supported is False  # number with no evidence


def test_number_parsing_handles_money_units_percent_negatives_and_years():
    nums = [
        n.value
        for n in parse_numbers(
            "In 2024 revenue was $25.8 billion, margin 13.7%, loss of (1,234) and -5."
        )
    ]
    assert nums == [25.8e9, 13.7, -1234, -5]


def test_quotes_must_appear_in_cited_passage():
    ledger = Ledger()
    ledger.add("chunk", "Our supply chain may be disrupted by tariffs.", Citation())
    ok = verify('Management warns "supply chain may be disrupted" [E1].', ledger)
    bad = verify('Management warns "supply chain is collapsing badly" [E1].', ledger)
    missing = verify("Revenue was $5 billion [E9].", ledger)
    assert [ok[0].supported, bad[0].supported, missing[0].supported] == [True, False, False]


def test_bullet_lines_are_separate_claims():
    ledger = Ledger()
    ledger.add("fact", "DBD revenue FY2021: 3905000000 USD", Citation(), 3_905_000_000)
    claims = verify(
        "Revenue was:\n* FY2021: $3.905 billion [E1]\n* FY2022: $9.9 billion [E1]", ledger
    )
    assert [c.supported for c in claims] == [None, True, False]


def test_partial_answer_with_a_missing_value_is_not_an_abstention():
    ctx = RunContext(gateway=ScriptedGateway(), model="m", tools=FakeTools())
    ctx.ledger.add("fact", "AMD revenue FY2024: 25785000000 USD", Citation(), 25_785_000_000)
    partial = ctx.finish("Revenue was $25.8 billion [E1]. FY2023 was not reported.")
    refusal = ctx.finish("That information is not reported in the filings.")
    assert (partial.abstained, refusal.abstained) == (False, True)


def test_citation_formats():
    from loupe.agent.verify import cited_ids

    assert cited_ids("x [E1] y [E2][E3] z") == ["E1", "E2", "E3"]
    assert cited_ids("x [E1, E4] y 【E5】") == ["E1", "E4", "E5"]
    assert cited_ids("see [note] and [1]") == []
