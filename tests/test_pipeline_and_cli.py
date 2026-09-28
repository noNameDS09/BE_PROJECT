"""
Tests for Phase 17: Final Pipeline Integration, CLI & Interactive Interface.
"""

import pytest

from Script import create_filename_to_company_mapping
from src.cli.interactive_cli import InteractiveCLI
from src.pipeline.conversational_pipeline import (
    FinancialIntelligencePipeline,
    PipelineResponse,
    get_default_pipeline,
    process_financial_query,
)


@pytest.fixture
def pipeline():
    return get_default_pipeline()


@pytest.fixture
def cli():
    return InteractiveCLI(session_id="test_cli_session")


# -----------------------------------------------------------------------------
# 1. Pipeline Single-Query Execution Tests
# -----------------------------------------------------------------------------

def test_pipeline_single_query_statement_extraction(pipeline):
    resp = pipeline.process_query("What was Abbott's revenue in 2024?", session_id="test_single")
    assert isinstance(resp, PipelineResponse)
    assert resp.status == "SUCCESS"
    assert resp.intent == "STATEMENT_EXTRACTION"
    assert resp.routed_to == "StatementExtractionAgent"
    assert "$41.95B" in resp.answer
    assert resp.is_faithful is True
    assert resp.validation_report is not None
    assert resp.validation_report.is_valid is True
    assert resp.provenance_audit_card is not None
    assert "Financial Provenance & Audit Trail" in resp.provenance_audit_card
    assert "0000001800" in resp.provenance_audit_card


def test_pipeline_investment_analysis(pipeline):
    resp = pipeline.process_query("Analyze Abbott's financial performance from 2022 to 2024", session_id="test_inv")
    assert resp.intent == "INVESTMENT_ANALYSIS"
    assert resp.routed_to == "InvestmentAgent"
    assert resp.validation_report is not None
    assert resp.validation_report.is_valid is True
    assert "Trajectory" in resp.answer or "Performance" in resp.answer


def test_pipeline_scenario_simulation(pipeline):
    resp = pipeline.process_query("Simulate a 10% revenue drop for Abbott in 2024", session_id="test_sim")
    assert resp.intent == "SCENARIO_SIMULATION"
    assert resp.routed_to == "ToneSimulationAgent"
    assert "| Revenue |" in resp.answer


# -----------------------------------------------------------------------------
# 2. Pipeline Multi-Turn Dialogue Context Tests
# -----------------------------------------------------------------------------

def test_pipeline_multi_turn_session(pipeline):
    session = "test_pipe_multi_turn"
    pipeline.conversation_manager.reset_session(session)

    # Turn 1: Establish context
    r1 = pipeline.process_query("What was Abbott's revenue in 2023?", session_id=session)
    assert "$40.11B" in r1.answer
    assert r1.turn_index == 1

    # Turn 2: Temporal Ellipsis ("What about 2022?")
    r2 = pipeline.process_query("What about 2022?", session_id=session)
    assert "$43.65B" in r2.answer
    assert "ABBOTT LABORATORIES" in r2.resolved_query

    # Turn 3: Anaphora and Metric Ellipsis ("What was its net income?")
    r3 = pipeline.process_query("What was its net income?", session_id=session)
    assert r3.intent == "STATEMENT_EXTRACTION"
    assert "ABBOTT LABORATORIES" in r3.resolved_query
    assert "Net Income" in r3.resolved_query


# -----------------------------------------------------------------------------
# 3. Interactive CLI Tests
# -----------------------------------------------------------------------------

def test_cli_slash_commands(cli):
    assert cli.handle_command("/help") is True
    assert cli.handle_command("/companies") is True
    assert cli.handle_command("/audit") is True
    assert cli.show_audit is False
    assert cli.handle_command("/audit") is True
    assert cli.show_audit is True
    assert cli.handle_command("/validation") is True
    assert cli.show_validation is False
    assert cli.handle_command("/reset") is True


def test_cli_process_input(cli):
    output = cli.process_input("What was Abbott's revenue in 2024?")
    assert "$41.95B" in output
    assert "Validation Status" in output
    assert "Financial Provenance & Audit Trail" in output


def test_cli_command_passthrough(cli):
    output = cli.process_input("/help")
    assert output == ""


# -----------------------------------------------------------------------------
# 4. Script.py Preservation
# -----------------------------------------------------------------------------

def test_script_py_mapping_preservation():
    mapping = create_filename_to_company_mapping()
    assert isinstance(mapping, dict)
    assert len(mapping) >= 40
    assert "CIK0000001800.json" in mapping
    assert mapping["CIK0000001800.json"] == "ABBOTT LABORATORIES"
