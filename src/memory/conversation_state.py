"""
Conversational State & Multi-Turn Context Tracking Module.

Enables conversational intelligence across multi-turn user dialogues:
- Anaphora and ellipsis resolution (e.g. "What about 2023?" -> "Abbott revenue in 2023")
- Active entity, metric, and fiscal period persistence
- Comparative entity bridging (e.g. "Compare with AMD" -> "Compare Abbott and AMD in 2023")
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from src.agents.orchestrator import (
    FinancialOrchestrator,
    OrchestratorResponse,
    get_default_orchestrator,
)
from src.data.company_registry import CompanyMetadata, CompanyRegistry, get_registry
from src.retrieval.metric_mapper import MetricMapper, get_default_mapper

logger = logging.getLogger(__name__)

# Common ticker / abbreviation overrides
COMPANY_ABBREVIATIONS: Dict[str, str] = {
    "amd": "ADVANCED MICRO DEVICES INC",
    "aar": "AAR CORP.",
    "spire": "Spire Inc.",
    "akorn": "AKORN INC",
    "cheniere": "Cheniere Energy, Inc.",
    "hess": "HESS CORPORATION",
    "u-haul": "U-Haul Holding Company",
    "uhaul": "U-Haul Holding Company",
    "aflac": "Aflac Incorporated",
    "acme": "ACME UNITED CORP",
}


@dataclass
class TurnRecord:
    """
    Representation of an individual conversational dialogue turn.
    """
    turn_index: int
    user_query: str
    resolved_query: str
    assistant_answer: str
    intent: str
    company: Optional[str]
    metric: Optional[str]
    fiscal_year: Optional[int]
    fiscal_period: Optional[str]
    inherited_slots: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationState:
    """
    State container tracking active conversational context.
    """
    session_id: str = "default"
    active_company: Optional[CompanyMetadata] = None
    active_metric: Optional[str] = None
    active_fiscal_year: Optional[int] = None
    active_fiscal_period: Optional[str] = None
    recent_companies: List[CompanyMetadata] = field(default_factory=list)
    turns: List[TurnRecord] = field(default_factory=list)

    def reset(self) -> None:
        """Clears all session context."""
        self.active_company = None
        self.active_metric = None
        self.active_fiscal_year = None
        self.active_fiscal_period = None
        self.recent_companies.clear()
        self.turns.clear()


@dataclass
class ResolvedQuery:
    """
    Result of contextual query resolution.
    """
    original_query: str
    resolved_query: str
    company: Optional[CompanyMetadata]
    metric: Optional[str]
    fiscal_year: Optional[int]
    fiscal_period: str
    inherited_slots: List[str] = field(default_factory=list)
    is_contextual_followup: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query,
            "resolved_query": self.resolved_query,
            "company": self.company.entity_name if self.company else None,
            "metric": self.metric,
            "fiscal_year": self.fiscal_year,
            "fiscal_period": self.fiscal_period,
            "inherited_slots": self.inherited_slots,
            "is_contextual_followup": self.is_contextual_followup,
        }


class ConversationManager:
    """
    Manages conversational memory, tracks multi-turn state,
    and resolves ellipses and pronouns using dialogue history.
    """

    def __init__(
        self,
        registry: Optional[CompanyRegistry] = None,
        mapper: Optional[MetricMapper] = None,
        orchestrator: Optional[FinancialOrchestrator] = None
    ):
        self.registry = registry or get_registry()
        self.mapper = mapper or get_default_mapper()
        self.orchestrator = orchestrator or get_default_orchestrator()
        self._sessions: Dict[str, ConversationState] = {}

    def get_session(self, session_id: str = "default") -> ConversationState:
        """Returns or creates ConversationState for a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState(session_id=session_id)
        return self._sessions[session_id]

    def reset_session(self, session_id: str = "default") -> None:
        """Resets conversational memory for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].reset()

    # -------------------------------------------------------------------------
    # Contextual Resolution Logic
    # -------------------------------------------------------------------------

    def resolve_query(self, query: str, session_id: str = "default") -> ResolvedQuery:
        """
        Resolves follow-up queries using conversational memory.
        Examples:
        - "What was Abbott's revenue in 2024?" (Turn 1: establishes Abbott, Revenue, 2024)
        - "What about 2023?" -> inherits Abbott & Revenue -> "What was Abbott's Revenue in 2023?"
        - "What about net income?" -> inherits Abbott & 2023 -> "What was Abbott's Net Income in 2023?"
        - "Compare with AMD" -> inherits Abbott & 2023 -> "Compare Abbott and AMD in 2023"
        """
        state = self.get_session(session_id)
        cleaned_query = query.strip()
        q_low = cleaned_query.lower()

        # 1. Parse current turn query components
        extracted_company = self._extract_company(cleaned_query)
        extracted_metric = self._extract_metric(cleaned_query)
        extracted_year = self._extract_year(cleaned_query)
        extracted_period = self._extract_period(cleaned_query)

        inherited_slots: List[str] = []
        resolved_company = extracted_company
        resolved_metric = extracted_metric
        resolved_year = extracted_year
        resolved_period = extracted_period or state.active_fiscal_period or "FY"

        # Check for comparison follow-up: e.g. "compare with AMD", "compare it with AMD", "vs AMD", "how does AMD compare?"
        is_compare_followup = any(kw in q_low for kw in [
            "compare with", "compare it with", "compare them with", "compare to",
            "compare it to", "vs", "versus", "how about vs"
        ]) or (
            any(w in q_low for w in ["compare", "versus", "vs"])
            and extracted_company is not None
            and state.active_company is not None
            and extracted_company.cik != state.active_company.cik
            and not any(tok in q_low for tok in state.active_company.entity_name.lower().split() if len(tok) > 3)
        )
        if is_compare_followup and extracted_company and state.active_company:
            inherited_year = resolved_year or state.active_fiscal_year or 2023
            inherited_metric = resolved_metric or state.active_metric or "Comparison"
            c1 = state.active_company.entity_name
            c2 = extracted_company.entity_name
            if inherited_metric and inherited_metric != "Comparison":
                rewritten = f"Compare {c1} and {c2} on {inherited_metric} in {inherited_year}"
            else:
                rewritten = f"Compare {c1} and {c2} in {inherited_year}"
            return ResolvedQuery(
                original_query=query,
                resolved_query=rewritten,
                company=extracted_company,
                metric=inherited_metric,
                fiscal_year=inherited_year,
                fiscal_period="FY",
                inherited_slots=["active_company", "fiscal_year"] + (["active_metric"] if inherited_metric != "Comparison" else []),
                is_contextual_followup=True
            )

        # 2. Inherit missing slots if active context exists
        if not resolved_company and state.active_company:
            resolved_company = state.active_company
            inherited_slots.append("company")

        if not resolved_metric and state.active_metric:
            # Check if query is asking for a metric follow-up or general follow-up
            if any(term in q_low for term in ["what about", "how about", "in 20", "for 20", "and 20"]):
                resolved_metric = state.active_metric
                inherited_slots.append("metric")

        if not resolved_year and state.active_fiscal_year:
            # If user asks for a new metric without specifying a year (e.g. "What about net income?")
            if extracted_metric and not extracted_year:
                resolved_year = state.active_fiscal_year
                inherited_slots.append("fiscal_year")

        is_followup = len(inherited_slots) > 0

        # 3. Formulate resolved rewritten query
        if is_followup and resolved_company:
            c_name = resolved_company.entity_name
            m_name = resolved_metric or "Revenue"
            y_name = resolved_year or 2023
            rewritten_query = f"What was {c_name}'s {m_name} in FY{y_name}?"
        else:
            rewritten_query = query

        return ResolvedQuery(
            original_query=query,
            resolved_query=rewritten_query,
            company=resolved_company,
            metric=resolved_metric,
            fiscal_year=resolved_year,
            fiscal_period=resolved_period,
            inherited_slots=inherited_slots,
            is_contextual_followup=is_followup
        )

    # -------------------------------------------------------------------------
    # Conversational Turn Processing & Orchestration
    # -------------------------------------------------------------------------

    def process_turn(self, query: str, session_id: str = "default") -> OrchestratorResponse:
        """
        Executes a full conversational turn:
        1. Contextual Query Resolution (Ellipsis/Anaphora)
        2. Routes through Financial Orchestrator
        3. Updates Conversational State & Dialogue Memory
        """
        state = self.get_session(session_id)
        resolved = self.resolve_query(query, session_id=session_id)

        logger.info(
            f"Conversational Memory resolved '{query}' -> '{resolved.resolved_query}' "
            f"(Inherited: {resolved.inherited_slots})"
        )

        # Route through orchestrator using resolved query
        response = self.orchestrator.route_query(resolved.resolved_query)

        # Update state based on resolved / current turn
        if resolved.company:
            state.active_company = resolved.company
            if resolved.company not in state.recent_companies:
                state.recent_companies.append(resolved.company)

        if resolved.metric and resolved.metric != "Unknown" and resolved.metric != "Comparison":
            state.active_metric = resolved.metric

        if resolved.fiscal_year:
            state.active_fiscal_year = resolved.fiscal_year

        if resolved.fiscal_period:
            state.active_fiscal_period = resolved.fiscal_period

        # Record turn in history
        turn_rec = TurnRecord(
            turn_index=len(state.turns) + 1,
            user_query=query,
            resolved_query=resolved.resolved_query,
            assistant_answer=response.answer,
            intent=response.intent,
            company=state.active_company.entity_name if state.active_company else None,
            metric=state.active_metric,
            fiscal_year=state.active_fiscal_year,
            fiscal_period=state.active_fiscal_period,
            inherited_slots=resolved.inherited_slots
        )
        state.turns.append(turn_rec)

        return response

    # -------------------------------------------------------------------------
    # Slot Extraction Helpers
    # -------------------------------------------------------------------------

    def _extract_company(self, query: str) -> Optional[CompanyMetadata]:
        """Extracts company metadata from query string."""
        cleaned = query.strip()
        words = re.findall(r"\b\w+(?:'\w+)?\b", cleaned.lower())
        for w in words:
            clean_word = w.replace("'s", "").strip()
            if clean_word in COMPANY_ABBREVIATIONS:
                try:
                    return self.registry.get_company(COMPANY_ABBREVIATIONS[clean_word])
                except Exception:
                    pass

        for comp in self.registry.list_companies(include_empty=False):
            name_clean = comp.entity_name.lower().replace(",", "").replace(".", "").replace(" inc", "").replace(" corp", "")
            tokens = [t for t in name_clean.split() if len(t) > 3]
            if name_clean in cleaned.lower():
                return comp
            for tok in tokens:
                if re.search(rf"\b{re.escape(tok)}\b", cleaned, re.IGNORECASE):
                    return comp

        return None

    def _extract_metric(self, query: str) -> Optional[str]:
        """Extracts canonical metric from query string."""
        candidate_terms = []
        for canonical, spec in self.mapper.ontology.items():
            candidate_terms.append((canonical, canonical))
            for alias in spec.get("aliases", []):
                candidate_terms.append((alias, canonical))

        candidate_terms.sort(key=lambda x: len(x[0]), reverse=True)
        for term, canonical in candidate_terms:
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, query, re.IGNORECASE):
                return canonical
        return None

    def _extract_year(self, query: str) -> Optional[int]:
        """Extracts 4-digit fiscal year."""
        m = re.search(r"(?:FY\s*|fiscal\s*year\s*)?(\b(?:19|20)\d{2}\b)|(?:FY)(\d{4})", query, re.IGNORECASE)
        if m:
            val = m.group(1) or m.group(2)
            return int(val)
        return None

    def _extract_period(self, query: str) -> Optional[str]:
        """Extracts fiscal period identifier (FY, Q1-Q4)."""
        m = re.search(r"\b(Q[1-4]|first\s*quarter|second\s*quarter|third\s*quarter|fourth\s*quarter)\b", query, re.IGNORECASE)
        if m:
            val = m.group(1).upper()
            if "FIRST" in val or val == "Q1":
                return "Q1"
            elif "SECOND" in val or val == "Q2":
                return "Q2"
            elif "THIRD" in val or val == "Q3":
                return "Q3"
            elif "FOURTH" in val or val == "Q4":
                return "Q4"
        return None


# Singleton instance and convenience function
_DEFAULT_CONVERSATION_MANAGER: Optional[ConversationManager] = None


def get_default_conversation_manager() -> ConversationManager:
    global _DEFAULT_CONVERSATION_MANAGER
    if _DEFAULT_CONVERSATION_MANAGER is None:
        _DEFAULT_CONVERSATION_MANAGER = ConversationManager()
    return _DEFAULT_CONVERSATION_MANAGER


get_conversation_manager = get_default_conversation_manager


def chat_turn(query: str, session_id: str = "default") -> OrchestratorResponse:
    """Convenience function to run a multi-turn conversational turn."""
    return get_default_conversation_manager().process_turn(query, session_id=session_id)
