"""The new arms with a scripted model: each one's control flow, not the model's quality."""

import json

from loupe.llm.gateway import Completion, ToolCall
from loupe.orchestrators import ARMS, RunContext
from loupe.orchestrators.base import parse_json
from loupe.orchestrators.plan_execute import substitute
from tests.test_orchestrators import FakeTools, ScriptedGateway, reply


def j(obj) -> Completion:
    return reply(json.dumps(obj))


def run(arm, *replies, **ctx_kw):
    gw = ScriptedGateway(*replies)
    ctx = RunContext(gateway=gw, model="m", tools=FakeTools(), **ctx_kw)
    return ARMS[arm].run("What was AMD's revenue growth in FY2024?", ctx), ctx, gw


def test_parse_json_tolerates_fences_and_chatter():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('plan: [{"step": 1}] done') == [{"step": 1}]
    assert parse_json("no json here") is None


def test_substitute_replaces_step_references_with_numbers():
    args = {"expression": "pct_change(#1, #2)", "keep": "#9"}
    assert substitute(args, {1: 100.0, 2: 125.0}) == {
        "expression": "pct_change(100.0, 125.0)",
        "keep": "#9",
    }


def test_plan_execute_runs_plan_without_the_model_and_substitutes_numbers():
    plan = {"plan": [
        {"step": 1, "tool": "calculate", "args": {"expression": "25785000000"}},
        {"step": 2, "tool": "calculate", "args": {"expression": "#1 / 1e9"}},
    ]}  # fmt: skip
    answer, ctx, gw = run("plan_execute", j(plan), reply("Revenue was $25.785 billion [E1][E2]."))
    assert [c[0] for c in ctx.tools.calls] == ["calculate", "calculate"]
    assert ctx.tools.calls[1][1] == {"expression": "25785000000.0 / 1e9"}
    assert len(gw.requests) == 2  # planner + solver only
    assert answer.claims[0].supported is True


def test_router_sends_question_to_one_specialist_with_restricted_tools():
    answer, _, gw = run("router", j({"intent": "event"}), reply("No events found."))
    offered = [t["function"]["name"] for t in gw.requests[1]["tools"]]
    assert offered == [
        "search_filings"
    ]  # event specialist: list_events + search_filings (fake has search only)
    assert answer.abstained is False or answer.text == "No events found."


def test_router_falls_back_to_open_analysis_on_bad_intent():
    _, _, gw = run("router", j({"intent": "nonsense"}), reply("Answer."))
    assert "Risk analyst" in gw.requests[1]["messages"][0]["content"]


def test_self_refine_revises_when_the_critic_finds_issues():
    answer, _, gw = run(
        "self_refine",
        reply("AMD revenue was $30 billion."),
        j({"ok": False, "issues": ["no citation and the number is unsupported"]}),
        reply("I could not find the number in the evidence."),
    )
    assert "reviewer found these problems" in gw.requests[2]["messages"][-1]["content"]
    assert answer.abstained is True


def test_self_refine_keeps_draft_when_critic_is_happy():
    answer, _, gw = run("self_refine", reply("Draft [E1]."), j({"ok": True, "issues": []}))
    assert answer.text == "Draft [E1]." and len(gw.requests) == 2


def test_loupe_full_path_route_plan_compose_verify_revise():
    route = {"intents": ["calc"], "companies": ["AMD"], "fiscal_years": [2024], "multi_step": True}
    plan = {"plan": [{"step": 1, "tool": "get_financial_metric", "args": {"company": "AMD"}}]}
    answer, _, gw = run(
        "loupe",
        j(route),
        j(plan),
        reply("AMD revenue was $27 billion [E1]. Growth was strong."),  # wrong number
        j({"unsupported": [1], "missing": ""}),
        reply(
            "AMD revenue was $25.8 billion [E1]. It grew $9 billion [E1]."
        ),  # 2nd claim still wrong
    )
    stages = [s.stage for s in answer.trace]
    assert stages[:2] == ["route", "plan"] and "critique" in stages
    assert (
        "$27 billion" in gw.requests[4]["messages"][-1]["content"]
    )  # feedback names the bad claim
    assert answer.text == "AMD revenue was $25.8 billion [E1]."  # unverifiable claim removed
    assert all(c.supported for c in answer.claims)


def test_loupe_abstains_for_companies_outside_the_universe():
    route = {"intents": ["lookup"], "companies": ["Tesla"], "fiscal_years": [], "multi_step": False}
    answer, ctx, gw = run("loupe", j(route))
    assert "not among the companies" in answer.text and answer.abstained is False
    assert len(gw.requests) == 1 and ctx.tools.calls == []


def test_loupe_abstains_when_nothing_survives_verification():
    route = {
        "intents": ["lookup"],
        "companies": ["AMD"],
        "fiscal_years": [2024],
        "multi_step": False,
    }
    answer, *_ = run(
        "loupe",
        j(route),
        reply("DONE"),  # gather loop: no tools called
        reply("Revenue was $9 billion [E7]."),  # cites evidence that doesn't exist
        j({"unsupported": [], "missing": ""}),
        reply("Revenue was $9 billion [E7]."),
    )
    assert "could not find evidence" in answer.text and answer.abstained


def test_ablation_without_critic_skips_that_stage():
    route = {
        "intents": ["lookup"],
        "companies": ["AMD"],
        "fiscal_years": [2024],
        "multi_step": False,
    }
    wrong = "Revenue was $9 billion [E7]."
    answer, *_ = run("loupe-no-critic", j(route), reply("DONE"), reply(wrong), reply(wrong))
    assert "critique" not in [s.stage for s in answer.trace]


def test_tools_off_ablation_hides_number_tools():
    gw = ScriptedGateway(reply("x"))
    ctx = RunContext(gateway=gw, model="m", tools=FakeTools(), tools_enabled=False)
    assert [s["function"]["name"] for s in ctx.specs()] == ["search_filings"]
    assert "not available" in ctx.tool("calculate", {"expression": "1+1"})


def test_query_rewrite_adds_extra_queries_to_search():
    gw = ScriptedGateway(j({"queries": ["net revenue fiscal 2024", "AMD sales"]}))
    ctx = RunContext(gateway=gw, model="m", tools=FakeTools(), query_rewrite=True)
    ctx.tool("search_filings", {"query": "AMD revenue"})
    assert ctx.tools.calls[0][1]["extra_queries"] == ["net revenue fiscal 2024", "AMD sales"]


def test_tool_calls_reach_the_trace():
    answer, *_ = run(
        "react",
        reply(None, ToolCall(id="a", name="calculate", arguments={"expression": "2+2"})),
        reply("Four [E1]."),
    )
    assert [s.name for s in answer.trace if s.stage == "tool"] == ["calculate"]


def test_plan_execute_cannot_plan_harness_tools():
    plan = {"plan": [{"step": 1, "tool": "get_financial_metric", "args": {"company": "AMD"}}]}
    _, ctx, gw = run("plan_execute", j(plan), reply("Not found."))
    catalogue = gw.requests[0]["messages"][0]["content"]
    assert "get_financial_metric" not in catalogue and "Metrics:" not in catalogue
    assert ctx.tools.calls == []


def test_loupe_keeps_the_harness_and_its_generic_ablation_does_not():
    from loupe.orchestrators.base import GENERIC_TOOLS

    full = RunContext(gateway=ScriptedGateway(), model="m", tools=FakeTools())
    full.use_toolset(ARMS["loupe"].toolset)
    assert full.allows("get_financial_metric")
    generic = RunContext(gateway=ScriptedGateway(), model="m", tools=FakeTools())
    generic.use_toolset(ARMS["loupe-generic-tools"].toolset)
    assert not generic.allows("get_financial_metric") and generic.allowed_tools == GENERIC_TOOLS
    assert {ARMS[a].toolset for a in ("react", "plan_execute", "router", "self_refine")} == {
        "generic"
    }


def test_toolset_is_part_of_the_config_hash():
    from loupe.eval.runner import RunSpec, config_for

    spec = RunSpec(dataset="gold_num", arms=["react", "loupe"], models=["m"])
    react, loupe = config_for(spec, "react", "m"), config_for(spec, "loupe", "m")
    assert (react.toolset, loupe.toolset) == ("generic", "harness")
    assert react.model_copy(update={"toolset": "harness"}).config_hash() != react.config_hash()


def test_loupe_reports_claims_the_verifier_removed():
    route = {"intents": ["lookup"], "companies": ["AMD"], "fiscal_years": [2024]}
    answer, *_ = run(
        "loupe",
        j(route),
        reply(None, ToolCall(id="a", name="calculate", arguments={"expression": "25.785e9"})),
        reply("DONE"),
        reply("Revenue was $25.8 billion [E1]. Margin was 99% [E1]."),
        j({"unsupported": [], "missing": ""}),
        reply("Revenue was $25.8 billion [E1]. Margin was 99% [E1]."),
    )
    assert answer.text == "Revenue was $25.8 billion [E1]."
    assert answer.removed_claims == ["Margin was 99% [E1]."]
