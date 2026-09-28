"""
End-to-End Financial Intelligence Pipeline.

Orchestrates multi-turn conversation memory, intent routing, agent execution,
pre-generation validation, and explainability provenance tracking.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from src.agents.orchestrator import (
    FinancialOrchestrator,
    OrchestratorResponse,
    get_default_orchestrator,
)
from src.agents.statement_extraction_agent import StatementExtractionResult
from src.explainability.provenance import (
    ProvenanceEngine,
    TraceabilityChain,
    build_provenance_chain,
    get_default_provenance_engine,
)
from src.memory.conversation_state import (
    ConversationManager,
    ResolvedQuery,
    get_default_conversation_manager,
)
from src.tools.validation import (
    FinancialValidator,
    ValidationReport,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResponse:
    """
    Consolidated response from the Financial Intelligence Pipeline.
    """
    session_id: str
    turn_index: int
    raw_query: str
    resolved_query: str
    intent: str
    routed_to: str
    answer: str
    agent_result: Any
    validation_report: Optional[ValidationReport] = None
    provenance_audit_card: Optional[str] = None
    is_faithful: bool = True
    status: str = "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "raw_query": self.raw_query,
            "resolved_query": self.resolved_query,
            "intent": self.intent,
            "routed_to": self.routed_to,
            "answer": self.answer,
            "is_faithful": self.is_faithful,
            "status": self.status,
        }
        if self.validation_report:
            res["validation"] = self.validation_report.to_dict()
        if self.provenance_audit_card:
            res["provenance_audit_card"] = self.provenance_audit_card
        if hasattr(self.agent_result, "to_dict"):
            res["agent_result"] = self.agent_result.to_dict()
        return res

    def format_display(
        self,
        include_audit: bool = False,
        include_validation: bool = False,
    ) -> str:
        """
        Renders the pipeline response with optional validation and provenance blocks.
        """
        sections = [self.answer]

        if include_validation and self.validation_report:
            v = self.validation_report
            badge = "PASSED" if v.is_valid and not v.has_warnings else "WARNING" if v.has_warnings else "FAILED"
            sections.append(
                f"\n---\n**Validation Status**: `{badge}` (Checks Passed: {len(v.passed_checks)}, "
                f"Warnings: {v.warning_count}, Errors: {v.error_count})"
            )
            for iss in v.issues:
                sections.append(f"- `[{iss.severity}]` {iss.message}")

        if include_audit and self.provenance_audit_card:
            sections.append(f"\n---\n{self.provenance_audit_card}")

        return "\n".join(sections)


class FinancialIntelligencePipeline:
    """
    Central pipeline coordinating memory, orchestration, validation, and provenance.
    """

    def __init__(
        self,
        orchestrator: Optional[FinancialOrchestrator] = None,
        conversation_manager: Optional[ConversationManager] = None,
        validator: Optional[FinancialValidator] = None,
        provenance_engine: Optional[ProvenanceEngine] = None,
    ):
        self.orchestrator = orchestrator or get_default_orchestrator()
        self.conversation_manager = conversation_manager or get_default_conversation_manager()
        self.validator = validator or FinancialValidator()
        self.provenance_engine = provenance_engine or get_default_provenance_engine()

    def process_query(
        self,
        query: str,
        session_id: str = "default",
        validate: bool = True,
        include_audit: bool = True,
    ) -> PipelineResponse:
        """
        Executes end-to-end pipeline processing:
        1. Contextual query resolution & slot inheritance (Memory)
        2. Intent classification and dispatch to specialized agent (Orchestrator)
        3. Pre-generation validation of facts and formulas (Validation)
        4. Lineage verification & audit card construction (Provenance)
        5. Session state update (Memory)
        """
        # Step 1: Contextual Resolution
        resolved: ResolvedQuery = self.conversation_manager.resolve_query(query, session_id=session_id)
        effective_query = resolved.resolved_query

        # Step 2: Route through Orchestrator
        orch_resp: OrchestratorResponse = self.orchestrator.route_query(effective_query)

        # Update Conversation State
        state = self.conversation_manager.get_session(session_id)
        if resolved.company:
            state.active_company = resolved.company
            if resolved.company not in state.recent_companies:
                state.recent_companies.append(resolved.company)
        if resolved.metric and resolved.metric not in ("Unknown", "Comparison"):
            state.active_metric = resolved.metric
        if resolved.fiscal_year:
            state.active_fiscal_year = resolved.fiscal_year
        if resolved.fiscal_period:
            state.active_fiscal_period = resolved.fiscal_period

        turn_index = len(state.turns) + 1

        # Step 3: Validation Layer
        val_report: Optional[ValidationReport] = None
        is_faithful = True

        if validate:
            val_report = ValidationReport(is_valid=True, has_warnings=False)
            agent_res = orch_resp.agent_result

            # Validate Statement Extraction
            if isinstance(agent_res, StatementExtractionResult):
                if agent_res.evidence:
                    self.validator.validate_retrieved_fact(agent_res.evidence, report=val_report)
                    self.validator.validate_source_metadata(agent_res.evidence, report=val_report)
                elif agent_res.status == "SUCCESS" and agent_res.value is None:
                    val_report.is_valid = False
                    is_faithful = False

            # Validate Investment Analysis
            elif hasattr(agent_res, "calculations"):
                for calc in getattr(agent_res, "calculations", []):
                    self.validator.validate_calculation(calc, report=val_report)

            # Validate Scenario Simulation
            elif hasattr(agent_res, "simulation_result") and getattr(agent_res, "simulation_result"):
                sim = getattr(agent_res, "simulation_result")
                if hasattr(sim, "source_facts"):
                    for sf in sim.source_facts:
                        self.validator.validate_source_metadata(sf, report=val_report)

            if val_report.error_count > 0:
                is_faithful = False

        # Step 4: Explainability & Provenance
        audit_card: Optional[str] = None
        if include_audit:
            try:
                agent_res = orch_resp.agent_result
                if hasattr(agent_res, "evidence") and getattr(agent_res, "evidence"):
                    chain = self.provenance_engine.build_from_statement_extraction(agent_res)
                    audit_card = chain.to_markdown()
                elif hasattr(agent_res, "calculations") and getattr(agent_res, "calculations"):
                    chain = self.provenance_engine.build_from_investment_analysis(agent_res)
                    audit_card = chain.to_markdown()
                elif hasattr(agent_res, "metrics_table") and getattr(agent_res, "metrics_table"):
                    chain = self.provenance_engine.build_from_comparison(agent_res)
                    audit_card = chain.to_markdown()
            except Exception as e:
                logger.debug(f"Provenance chain generation skipped for {type(orch_resp.agent_result).__name__}: {e}")

        # Assemble Final Response
        return PipelineResponse(
            session_id=session_id,
            turn_index=turn_index,
            raw_query=query,
            resolved_query=effective_query,
            intent=orch_resp.intent,
            routed_to=orch_resp.routed_to,
            answer=orch_resp.answer,
            agent_result=orch_resp.agent_result,
            validation_report=val_report,
            provenance_audit_card=audit_card,
            is_faithful=is_faithful,
            status="SUCCESS",
        )


# Global singleton and helper
_DEFAULT_PIPELINE: Optional[FinancialIntelligencePipeline] = None


def get_default_pipeline() -> FinancialIntelligencePipeline:
    global _DEFAULT_PIPELINE
    if _DEFAULT_PIPELINE is None:
        _DEFAULT_PIPELINE = FinancialIntelligencePipeline()
    return _DEFAULT_PIPELINE


def process_financial_query(
    query: str,
    session_id: str = "default",
    validate: bool = True,
    include_audit: bool = True,
) -> PipelineResponse:
    """Convenience function to run a query through the full pipeline."""
    return get_default_pipeline().process_query(
        query=query,
        session_id=session_id,
        validate=validate,
        include_audit=include_audit,
    )
