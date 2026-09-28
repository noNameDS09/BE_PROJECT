"""
Tests for Phase 15: Loughran-McDonald Tone Analysis & Deterministic Financial Scenario Simulation.
"""

import pytest

from src.agents.orchestrator import (
    INTENT_SCENARIO_SIMULATION,
    INTENT_TONE_ANALYSIS,
    FinancialOrchestrator,
    get_default_orchestrator,
)
from src.agents.tone_simulation_agent import (
    ToneSimulationAgent,
    ToneSimulationResult,
    get_default_tone_simulation_agent,
)
from src.tools.scenario_simulator import (
    SIMULATION_LIMITATION_NOTICE,
    ScenarioSimulator,
    SimulationResult,
    get_default_simulator,
)
from src.tools.tone_analyzer import (
    TONE_LIMITATION_NOTICE,
    QuantitativeToneProxy,
    ToneAnalyzer,
    ToneScore,
    ToneShift,
    get_default_tone_analyzer,
)


@pytest.fixture
def tone_analyzer():
    return get_default_tone_analyzer()


@pytest.fixture
def simulator():
    return get_default_simulator()


@pytest.fixture
def tone_agent():
    return get_default_tone_simulation_agent()


@pytest.fixture
def orchestrator():
    return get_default_orchestrator()


# -----------------------------------------------------------------------------
# 1. Lexical Tone Scoring Tests
# -----------------------------------------------------------------------------

def test_tone_scoring_positive_and_negative(tone_analyzer):
    pos_text = (
        "We achieved exceptional revenue growth, superior profitability, and outstanding operational efficiency. "
        "Our innovative products created tremendous value, delivering strong profits and solid momentum."
    )
    score_pos = tone_analyzer.analyze_tone(pos_text)
    assert score_pos.dominant_sentiment == "POSITIVE"
    assert score_pos.polarity_score > 0.5
    assert score_pos.positive_count >= 5
    assert score_pos.negative_count == 0

    neg_text = (
        "The company suffered severe losses, adverse market conditions, impairment charges, and restructuring costs. "
        "Disruptions and product recalls significantly harmed our financial health, triggering a sharp decline."
    )
    score_neg = tone_analyzer.analyze_tone(neg_text)
    assert score_neg.dominant_sentiment == "NEGATIVE"
    assert score_neg.polarity_score < -0.5
    assert score_neg.negative_count >= 5


def test_tone_uncertainty_and_litigious(tone_analyzer):
    legal_text = (
        "The plaintiff filed a lawsuit alleging patent infringement and seeking arbitration in federal court. "
        "The defendant denied all allegations regarding covenant violations and regulatory claims."
    )
    score_legal = tone_analyzer.analyze_tone(legal_text)
    assert score_legal.litigious_count >= 4

    uncertain_text = (
        "We anticipate volatile fluctuations and unpredictable contingencies that may depend on preliminary estimates. "
        "It is possible that future forecasts could vary roughly around these uncertain projections."
    )
    score_unc = tone_analyzer.analyze_tone(uncertain_text)
    assert score_unc.uncertainty_count >= 5
    assert score_unc.uncertainty_ratio > 0.10


# -----------------------------------------------------------------------------
# 2. Tone Shift Analysis Tests
# -----------------------------------------------------------------------------

def test_tone_shift_calculation(tone_analyzer):
    passage_a = "We achieved record revenues, strong growth, and superior operational execution with solid margins."
    passage_b = "However, severe cost inflation, supply disruptions, and deteriorating demand caused substantial losses and declining margins."

    shift = tone_analyzer.compare_tone_shift(
        text_a=passage_a,
        text_b=passage_b,
        label_a="Q2 Earnings Presentation",
        label_b="Q3 Earnings Presentation",
    )

    assert isinstance(shift, ToneShift)
    assert shift.score_a.dominant_sentiment == "POSITIVE"
    assert shift.score_b.dominant_sentiment == "NEGATIVE"
    assert shift.delta_polarity < -0.30
    assert shift.shift_category == "STRONG_NEGATIVE_SHIFT"
    assert "deterioration in tone" in shift.interpretation.lower()


# -----------------------------------------------------------------------------
# 3. Quantitative Fundamental Tone Proxy Tests
# -----------------------------------------------------------------------------

def test_quantitative_tone_proxy_from_sec_facts(tone_analyzer):
    proxy = tone_analyzer.derive_quantitative_tone_proxy("Abbott", 2023)
    assert isinstance(proxy, QuantitativeToneProxy)
    assert proxy.company == "ABBOTT LABORATORIES"
    assert proxy.fiscal_year == 2023
    assert proxy.prior_year == 2022
    assert -1.0 <= proxy.proxy_score <= 1.0
    assert proxy.implied_tone in [
        "EXPANSIONARY / OPTIMISTIC",
        "BALANCED / STABLE",
        "CONTRACTING / CAUTIOUS",
    ]
    assert TONE_LIMITATION_NOTICE in proxy.data_limitation_notice


# -----------------------------------------------------------------------------
# 4. Deterministic Scenario & Stress Simulation Tests
# -----------------------------------------------------------------------------

def test_scenario_simulator_revenue_shock(simulator):
    res = simulator.simulate_revenue_shock("Abbott", 2024, -10.0)
    assert isinstance(res, SimulationResult)
    assert res.status == "SUCCESS"
    assert res.fiscal_year == 2024

    # Baseline revenue for Abbott 2024 is $41.95B
    rev_item = res.line_items["Revenue"]
    assert rev_item.baseline == pytest.approx(41950000000.0, rel=1e-3)
    assert rev_item.stressed == pytest.approx(41950000000.0 * 0.90, rel=1e-3)
    assert rev_item.delta_absolute == pytest.approx(-4195000000.0, rel=1e-3)
    assert rev_item.delta_percent == -10.0

    # Stressed operating income should be strictly lower than baseline
    opinc_item = res.line_items["Operating Income"]
    assert opinc_item.stressed < opinc_item.baseline

    # Output table renders cleanly
    md_table = res.to_markdown_table()
    assert "| Revenue |" in md_table
    assert "| Operating Income |" in md_table
    assert SIMULATION_LIMITATION_NOTICE in md_table


def test_scenario_simulator_cost_inflation(simulator):
    res = simulator.simulate_cost_inflation("AMD", 2023, cogs_inflation_pct=5.0, sga_inflation_pct=2.5)
    assert res.status == "SUCCESS"
    cogs_item = res.line_items["Cost of Goods Sold"]
    assert cogs_item.stressed == pytest.approx(cogs_item.baseline * 1.05, rel=1e-3)
    assert res.line_items["Operating Margin"].stressed < res.line_items["Operating Margin"].baseline


def test_scenario_simulator_interest_rate_shock(simulator):
    res = simulator.simulate_interest_rate_shock("Abbott", 2023, rate_shock_bps=150.0)
    assert res.status == "SUCCESS"
    assert "Additional Pre-Tax Interest Burden" in res.line_items
    burden_item = res.line_items["Additional Pre-Tax Interest Burden"]
    assert burden_item.stressed > 0


def test_scenario_simulator_operating_breakeven(simulator):
    be = simulator.calculate_operating_breakeven("Abbott", 2024)
    assert be["status"] == "SUCCESS"
    assert be["breakeven_revenue_decline_pct"] is not None
    assert -100.0 <= be["breakeven_revenue_decline_pct"] < 0.0


# -----------------------------------------------------------------------------
# 5. ToneSimulationAgent Query Answering Tests
# -----------------------------------------------------------------------------

def test_tone_simulation_agent_query_simulation(tone_agent):
    res = tone_agent.answer_query("Simulate a 10% revenue drop for Abbott in 2024")
    assert isinstance(res, ToneSimulationResult)
    assert res.mode == "SCENARIO_SIMULATION"
    assert res.company == "ABBOTT LABORATORIES"
    assert res.fiscal_year == 2024
    assert res.simulation_result is not None
    assert "| Revenue |" in res.summary


def test_tone_simulation_agent_query_tone_with_text(tone_agent):
    sample_text = "We achieved record operating profits and outstanding customer adoption."
    res = tone_agent.answer_query("Analyze management tone", text_a=sample_text, label_a="Management Remarks")
    assert res.mode == "TONE_ANALYSIS"
    assert res.tone_score is not None
    assert res.tone_score.dominant_sentiment == "POSITIVE"


def test_tone_simulation_agent_query_tone_shift_with_text(tone_agent):
    t_a = "Our business delivered record growth and excellent margins."
    t_b = "However, severe cost inflation and declining demand eroded our profits."
    res = tone_agent.answer_query(
        "Evaluate tone shift",
        text_a=t_a,
        text_b=t_b,
        label_a="Q1 Earnings Call",
        label_b="Q2 Earnings Call",
    )
    assert res.mode == "TONE_SHIFT"
    assert res.tone_shift is not None
    assert res.tone_shift.shift_category == "STRONG_NEGATIVE_SHIFT"


def test_tone_simulation_agent_query_quantitative_proxy(tone_agent):
    res = tone_agent.answer_query("What was the management tone for Abbott in 2023?")
    assert res.mode == "QUANTITATIVE_TONE_PROXY"
    assert res.tone_proxy is not None
    assert TONE_LIMITATION_NOTICE in res.data_limitation_notice


# -----------------------------------------------------------------------------
# 6. Central Orchestrator Routing Tests
# -----------------------------------------------------------------------------

def test_orchestrator_routing_simulation(orchestrator):
    res = orchestrator.route_query("Simulate a 10% revenue drop for Abbott in 2024")
    assert res.intent == INTENT_SCENARIO_SIMULATION
    assert res.routed_to == "ToneSimulationAgent"
    assert "| Revenue |" in res.answer


def test_orchestrator_routing_tone(orchestrator):
    res = orchestrator.route_query("Analyze management tone for Abbott in 2023")
    assert res.intent == INTENT_TONE_ANALYSIS
    assert res.routed_to == "ToneSimulationAgent"
    assert "Quantitative Tone Proxy" in res.answer
