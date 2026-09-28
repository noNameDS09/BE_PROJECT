"""
Tests for Conversational Memory & Multi-Turn State Tracking (Phase 14).
"""

import pytest

from src.memory.conversation_state import (
    ConversationManager,
    ConversationState,
    ResolvedQuery,
    TurnRecord,
    chat_turn,
    get_default_conversation_manager,
)


@pytest.fixture
def manager():
    mgr = get_default_conversation_manager()
    mgr.reset_session("test_session")
    return mgr


# ---------------------------------------------------------
# Test Multi-Turn Dialogue Context Resolution
# ---------------------------------------------------------

def test_multi_turn_anaphora_and_ellipsis_resolution(manager):
    session = "test_session"

    # Turn 1: Establish company, metric, and fiscal year
    q1 = "What was Abbott's revenue in 2024?"
    res1 = manager.resolve_query(q1, session_id=session)
    assert res1.is_contextual_followup is False
    assert res1.company.entity_name == "ABBOTT LABORATORIES"
    assert res1.metric == "Revenue"
    assert res1.fiscal_year == 2024

    resp1 = manager.process_turn(q1, session_id=session)
    assert "41,950,000,000" in resp1.answer

    # Turn 2: Ellipsis query ("What about 2023?")
    # Must inherit company (Abbott) and metric (Revenue) without repeating
    q2 = "What about 2023?"
    res2 = manager.resolve_query(q2, session_id=session)
    assert res2.is_contextual_followup is True
    assert "company" in res2.inherited_slots
    assert "metric" in res2.inherited_slots
    assert res2.company.entity_name == "ABBOTT LABORATORIES"
    assert res2.metric == "Revenue"
    assert res2.fiscal_year == 2023

    resp2 = manager.process_turn(q2, session_id=session)
    assert "40,109,000,000" in resp2.answer

    # Turn 3: Metric shift ("What about net income?")
    # Must inherit company (Abbott) and year (2023)
    q3 = "What about net income?"
    res3 = manager.resolve_query(q3, session_id=session)
    assert res3.is_contextual_followup is True
    assert "company" in res3.inherited_slots
    assert "fiscal_year" in res3.inherited_slots
    assert res3.metric == "Net Income"
    assert res3.fiscal_year == 2023

    resp3 = manager.process_turn(q3, session_id=session)
    assert "5,723,000,000" in resp3.answer

    # Turn 4: Comparative bridging ("Compare with AMD")
    # Must bridge active company (Abbott) with newly introduced company (AMD)
    q4 = "Compare with AMD"
    res4 = manager.resolve_query(q4, session_id=session)
    assert res4.is_contextual_followup is True
    assert "active_company" in res4.inherited_slots
    assert "Compare" in res4.resolved_query
    assert "ABBOTT LABORATORIES" in res4.resolved_query
    assert "ADVANCED MICRO DEVICES INC" in res4.resolved_query

    resp4 = manager.process_turn(q4, session_id=session)
    assert resp4.intent == "COMPARISON"
    assert "Financial Comparison" in resp4.answer


# ---------------------------------------------------------
# Test Session State Tracking & Turn History
# ---------------------------------------------------------

def test_turn_history_recording(manager):
    session = "history_test"
    manager.reset_session(session)

    manager.process_turn("What was Abbott's revenue in 2024?", session_id=session)
    manager.process_turn("What about 2023?", session_id=session)

    state = manager.get_session(session)
    assert len(state.turns) == 2
    assert state.turns[0].turn_index == 1
    assert state.turns[1].turn_index == 2
    assert state.turns[1].inherited_slots == ["company", "metric"]


# ---------------------------------------------------------
# Test Multi-Session Isolation
# ---------------------------------------------------------

def test_multi_session_isolation(manager):
    # Session A sets Abbott
    manager.process_turn("What was Abbott's revenue in 2024?", session_id="session_a")

    # Session B sets AMD
    manager.process_turn("What was AMD's revenue in 2023?", session_id="session_b")

    # Verify Session A retained Abbott
    res_a = manager.resolve_query("What about 2022?", session_id="session_a")
    assert res_a.company.entity_name == "ABBOTT LABORATORIES"

    # Verify Session B retained AMD
    res_b = manager.resolve_query("What about 2022?", session_id="session_b")
    assert res_b.company.entity_name == "ADVANCED MICRO DEVICES INC"


# ---------------------------------------------------------
# Test Reset Functionality
# ---------------------------------------------------------

def test_reset_session(manager):
    session = "reset_test"
    manager.process_turn("What was Abbott's revenue in 2024?", session_id=session)
    assert manager.get_session(session).active_company is not None

    manager.reset_session(session)
    state = manager.get_session(session)
    assert state.active_company is None
    assert len(state.turns) == 0


# ---------------------------------------------------------
# Test Convenience Function
# ---------------------------------------------------------

def test_convenience_function():
    resp = chat_turn("What was Abbott's revenue in 2024?", session_id="conv_fn_test")
    assert "41,950,000,000" in resp.answer
