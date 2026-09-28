"""
Automated Benchmark Runner for the FARE Corporate Facts System.

Executes test suites across all 5 evaluation dimensions, synthesizes quantifiable
scores, and generates structured scorecards in Markdown and JSON.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from evaluation.benchmark_dataset import (
    BENCHMARK_DATASET,
    CONVERSATIONAL_MEMORY_BENCHMARK,
    INTENT_CLASSIFICATION_BENCHMARK,
    NUMERICAL_CALCULATION_BENCHMARK,
    STATEMENT_EXTRACTION_BENCHMARK,
)
from evaluation.metrics import EvaluationMetrics, MetricScore
from src.agents.orchestrator import FinancialOrchestrator, get_default_orchestrator
from src.agents.statement_extraction_agent import (
    StatementExtractionAgent,
    get_default_statement_agent,
)
from src.memory.conversation_state import ConversationManager, get_conversation_manager
from src.tools.financial_calculator import FinancialCalculator, get_default_calculator

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkReport:
    """
    Consolidated outcome of the FARE evaluation benchmark run.
    """
    retrieval_score: MetricScore
    faithfulness_score: MetricScore
    numerical_score: MetricScore
    intent_score: MetricScore
    memory_score: MetricScore
    composite_fare_score: float  # [0.0, 100.0]
    total_eval_cases: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "composite_fare_score": self.composite_fare_score,
            "total_eval_cases": self.total_eval_cases,
            "dimensions": {
                "retrieval": self.retrieval_score.to_dict(),
                "faithfulness": self.faithfulness_score.to_dict(),
                "numerical_precision": self.numerical_score.to_dict(),
                "intent_routing": self.intent_score.to_dict(),
                "conversational_memory": self.memory_score.to_dict(),
            }
        }

    def generate_markdown_scorecard(self) -> str:
        """
        Renders a comprehensive GitHub-Flavored Markdown Scorecard.
        """
        lines = [
            "# FARE Benchmark Evaluation Scorecard",
            "**Framework**: *Agent-Orchestrated Financial Risk Extraction & Conversational Intelligence*",
            f"**Composite FARE Score**: `{self.composite_fare_score:.2f}%` | **Total Test Cases**: `{self.total_eval_cases}`",
            "",
            "## Dimension Breakdown",
            "| Evaluation Dimension | Passed | Total | Score (%) | Status |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        scores = [
            self.retrieval_score,
            self.faithfulness_score,
            self.numerical_score,
            self.intent_score,
            self.memory_score,
        ]

        for s in scores:
            status = "PASS" if s.percentage >= 90.0 else "WARN" if s.percentage >= 75.0 else "FAIL"
            badge = f"**{status}**"
            lines.append(f"| {s.name} | {s.passed_cases} | {s.total_cases} | {s.percentage:.1f}% | {badge} |")

        lines.extend([
            "",
            "## Key Diagnostic Insights",
            f"- **Fact Retrieval**: {self.retrieval_score.diagnostics}",
            f"- **Faithfulness & Grounding**: {self.faithfulness_score.diagnostics}",
            f"- **Deterministic Arithmetic**: {self.numerical_score.diagnostics}",
            f"- **Orchestrator Routing**: {self.intent_score.diagnostics}",
            f"- **Conversational Memory**: {self.memory_score.diagnostics}",
            "",
            "> [!NOTE]\n> Evaluated against structured SEC EDGAR 10-K/10-Q corporate facts. Zero LLM arithmetic.",
        ])

        return "\n".join(lines)

    def export_json(self, filepath: Union[str, Path]) -> None:
        """Exports report dictionary to JSON file."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class BenchmarkRunner:
    """
    Automated evaluation harness for the FARE system.
    """

    def __init__(
        self,
        orchestrator: Optional[FinancialOrchestrator] = None,
        statement_agent: Optional[StatementExtractionAgent] = None,
        calculator: Optional[FinancialCalculator] = None,
        conversation_manager: Optional[ConversationManager] = None,
    ):
        self.orchestrator = orchestrator or get_default_orchestrator()
        self.statement_agent = statement_agent or get_default_statement_agent()
        self.calculator = calculator or get_default_calculator()
        self.conversation_manager = conversation_manager or get_conversation_manager()

    def run_statement_benchmarks(self) -> Tuple[MetricScore, MetricScore]:
        """Runs statement extraction retrieval and faithfulness evaluations."""
        retrieval_cases = []
        faithfulness_items = []

        for tc in STATEMENT_EXTRACTION_BENCHMARK:
            res = self.statement_agent.answer_query(tc.query)
            retrieval_cases.append({
                "query": tc.query,
                "predicted_value": res.value,
                "expected_value": tc.expected_value,
            })
            faithfulness_items.append({
                "query": tc.query,
                "value": res.value,
                "evidence": res.evidence,
            })

        retrieval_score = EvaluationMetrics.evaluate_retrieval(retrieval_cases)
        faithfulness_score = EvaluationMetrics.evaluate_faithfulness(faithfulness_items)
        return retrieval_score, faithfulness_score

    def run_intent_benchmark(self) -> MetricScore:
        """Runs Orchestrator intent classification benchmark."""
        routing_cases = []
        for tc in INTENT_CLASSIFICATION_BENCHMARK:
            pred_intent, _ = self.orchestrator.classify_intent(tc.query)
            routing_cases.append({
                "query": tc.query,
                "predicted_intent": pred_intent,
                "expected_intent": tc.expected_intent,
            })
        return EvaluationMetrics.evaluate_intent_routing(routing_cases)

    def run_numerical_benchmark(self) -> MetricScore:
        """Runs deterministic calculation benchmark."""
        calc_cases = []
        for tc in NUMERICAL_CALCULATION_BENCHMARK:
            if tc.metric_type == "revenue_growth":
                c_res = self.calculator.calculate_revenue_growth(
                    tc.inputs["current"],
                    tc.inputs["previous"],
                )
            elif tc.metric_type in ("profit_margin", "operating_margin"):
                c_res = self.calculator.calculate_profit_margin(
                    tc.inputs["income"],
                    tc.inputs["revenue"],
                    margin_type=tc.name,
                )
            else:
                c_res = None

            calc_cases.append({
                "name": tc.name,
                "calculated_value": c_res.value if c_res else None,
                "expected_value": tc.expected_value,
            })

        return EvaluationMetrics.evaluate_numerical_accuracy(calc_cases)

    def run_memory_benchmark(self) -> MetricScore:
        """Runs conversational memory multi-turn context resolution benchmark."""
        resolved_turns = []

        for session in CONVERSATIONAL_MEMORY_BENCHMARK:
            session_id = session.session_id
            self.conversation_manager.reset_session(session_id)

            for t in session.turns:
                query = t["input"]
                res = self.conversation_manager.resolve_query(query, session_id=session_id)
                self.conversation_manager.process_turn(query, session_id=session_id)

                resolved_entities = []
                if res.company:
                    resolved_entities.append(res.company.entity_name)
                if "Compare" in res.resolved_query:
                    for comp in self.conversation_manager.registry.list_companies(include_empty=False):
                        if comp.entity_name.lower() in res.resolved_query.lower() and comp.entity_name not in resolved_entities:
                            resolved_entities.append(comp.entity_name)

                resolved_turns.append({
                    "raw_input": query,
                    "resolved_entities": resolved_entities,
                    "expected_entities": t.get("expected_entities", []),
                    "resolved_years": [res.fiscal_year] if res.fiscal_year else [],
                    "expected_years": t.get("expected_years", []),
                    "resolved_metrics": [res.metric] if res.metric else [],
                    "expected_metrics": t.get("expected_metrics", []),
                })

        return EvaluationMetrics.evaluate_memory_resolution(resolved_turns)

    def run_full_benchmark(self) -> BenchmarkReport:
        """
        Executes all benchmark test suites and computes composite scores.
        """
        retrieval_s, faithfulness_s = self.run_statement_benchmarks()
        intent_s = self.run_intent_benchmark()
        numerical_s = self.run_numerical_benchmark()
        memory_s = self.run_memory_benchmark()

        scores = [retrieval_s, faithfulness_s, numerical_s, intent_s, memory_s]
        composite_score = sum(s.percentage for s in scores) / float(len(scores))
        total_cases = sum(s.total_cases for s in scores)

        return BenchmarkReport(
            retrieval_score=retrieval_s,
            faithfulness_score=faithfulness_s,
            numerical_score=numerical_s,
            intent_score=intent_s,
            memory_score=memory_s,
            composite_fare_score=round(composite_score, 2),
            total_eval_cases=total_cases,
        )


def run_benchmark() -> BenchmarkReport:
    """Convenience function to execute the full FARE benchmark suite."""
    runner = BenchmarkRunner()
    return runner.run_full_benchmark()


if __name__ == "__main__":
    report = run_benchmark()
    print(report.generate_markdown_scorecard())
