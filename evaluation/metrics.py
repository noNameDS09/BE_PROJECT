"""
Core Evaluation Metrics for the FARE Corporate Facts Framework.

Computes quantifiable scores across:
1. Fact Retrieval Accuracy
2. Faithfulness & Source Lineage Grounding
3. Deterministic Numerical Precision
4. Intent Classification Precision & Recall
5. Conversational Memory Resolution Accuracy
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class MetricScore:
    """
    Standardized metric evaluation result container.
    """
    name: str
    score: float  # [0.0, 1.0]
    percentage: float  # [0.0, 100.0]
    total_cases: int
    passed_cases: int
    failed_cases: int
    details: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"MetricScore(name='{self.name}', score={self.percentage:.1f}%, "
            f"passed={self.passed_cases}/{self.total_cases})"
        )


class EvaluationMetrics:
    """
    Calculates FARE benchmarks and evaluation metrics.
    """

    @staticmethod
    def evaluate_retrieval(
        eval_cases: List[Dict[str, Any]],
        tolerance_rel: float = 0.001,
    ) -> MetricScore:
        """
        Evaluates retrieval accuracy against ground-truth SEC facts.

        Each case expects:
        - query: str
        - predicted_value: Optional[float]
        - expected_value: float
        """
        total = len(eval_cases)
        if total == 0:
            return MetricScore("Retrieval Accuracy", 1.0, 100.0, 0, 0, 0, diagnostics="No cases evaluated.")

        passed = 0
        details = []

        for case in eval_cases:
            pred = case.get("predicted_value")
            exp = case.get("expected_value")
            query = case.get("query", "")

            is_pass = False
            error_reason = ""

            if pred is None:
                error_reason = "No fact retrieved (predicted value is None)."
            else:
                rel_diff = abs(pred - exp) / abs(exp) if exp != 0 else abs(pred)
                if rel_diff <= tolerance_rel:
                    is_pass = True
                else:
                    error_reason = f"Value mismatch: predicted {pred:,.0f} vs expected {exp:,.0f} (diff: {rel_diff*100:.2f}%)."

            if is_pass:
                passed += 1

            details.append({
                "query": query,
                "predicted": pred,
                "expected": exp,
                "passed": is_pass,
                "notes": error_reason if not is_pass else "Match verified.",
            })

        score = passed / float(total)
        diag = f"Successfully matched {passed} of {total} ground truth SEC facts."
        return MetricScore(
            name="Fact Retrieval Accuracy",
            score=round(score, 4),
            percentage=round(score * 100.0, 2),
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            details=details,
            diagnostics=diag,
        )

    @staticmethod
    def evaluate_faithfulness(extracted_results: List[Dict[str, Any]]) -> MetricScore:
        """
        Evaluates SEC source grounding and hallucination resistance.
        A result is faithful iff:
        1. It has evidence metadata attached.
        2. Evidence specifies non-empty SEC accession number, form, filing date, and concept.
        3. The reported value strictly equals the evidence source value.
        """
        total = len(extracted_results)
        if total == 0:
            return MetricScore("Faithfulness & Source Grounding", 1.0, 100.0, 0, 0, 0)

        passed = 0
        details = []

        for item in extracted_results:
            query = item.get("query", "")
            value = item.get("value")
            evidence = item.get("evidence")

            is_faithful = False
            flaws = []

            if not evidence or not isinstance(evidence, dict):
                flaws.append("Missing source evidence object.")
            else:
                ev_val = evidence.get("value")
                ev_form = evidence.get("form")
                ev_filed = evidence.get("filed_date")
                ev_acc = evidence.get("accession_number")
                ev_concept = evidence.get("concept")

                if not ev_form:
                    flaws.append("Missing filing form in evidence.")
                if not ev_filed:
                    flaws.append("Missing filed date in evidence.")
                if not ev_acc:
                    flaws.append("Missing SEC accession number.")
                if not ev_concept:
                    flaws.append("Missing taxonomy concept.")

                if value is not None and ev_val is not None:
                    if abs(float(value) - float(ev_val)) > 1e-4:
                        flaws.append(f"Discrepancy between stated value ({value}) and evidence value ({ev_val}).")
                elif value != ev_val:
                    flaws.append("Null state mismatch between stated value and evidence.")

                if not flaws:
                    is_faithful = True

            if is_faithful:
                passed += 1

            details.append({
                "query": query,
                "passed": is_faithful,
                "flaws": flaws,
            })

        score = passed / float(total)
        diag = f"{passed}/{total} responses met strict SEC lineage and grounding standards."
        return MetricScore(
            name="Fact Grounding & Faithfulness",
            score=round(score, 4),
            percentage=round(score * 100.0, 2),
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            details=details,
            diagnostics=diag,
        )

    @staticmethod
    def evaluate_numerical_accuracy(
        calculation_cases: List[Dict[str, Any]],
        tolerance_abs: float = 0.02,
    ) -> MetricScore:
        """
        Evaluates mathematical accuracy of deterministic calculations against expected figures.
        """
        total = len(calculation_cases)
        if total == 0:
            return MetricScore("Numerical Arithmetic Accuracy", 1.0, 100.0, 0, 0, 0)

        passed = 0
        details = []

        for case in calculation_cases:
            name = case.get("name", "")
            calc_val = case.get("calculated_value")
            exp_val = case.get("expected_value")

            is_pass = False
            notes = ""

            if calc_val is None:
                notes = "Calculation returned None."
            else:
                diff = abs(calc_val - exp_val)
                if diff <= tolerance_abs:
                    is_pass = True
                else:
                    notes = f"Arithmetic delta: {diff:.4f} exceeds tolerance {tolerance_abs}."

            if is_pass:
                passed += 1

            details.append({
                "name": name,
                "calculated": calc_val,
                "expected": exp_val,
                "passed": is_pass,
                "notes": notes if not is_pass else "Verified within tolerance.",
            })

        score = passed / float(total)
        return MetricScore(
            name="Numerical Calculation Precision",
            score=round(score, 4),
            percentage=round(score * 100.0, 2),
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            details=details,
            diagnostics=f"{passed}/{total} calculations verified with zero arithmetic defects.",
        )

    @staticmethod
    def evaluate_intent_routing(routing_cases: List[Dict[str, Any]]) -> MetricScore:
        """
        Evaluates Orchestrator intent classification and routing accuracy.
        """
        total = len(routing_cases)
        if total == 0:
            return MetricScore("Intent Routing Accuracy", 1.0, 100.0, 0, 0, 0)

        passed = 0
        per_class: Dict[str, Dict[str, int]] = {}
        details = []

        for case in routing_cases:
            q = case.get("query", "")
            pred = case.get("predicted_intent", "").strip().upper()
            exp = case.get("expected_intent", "").strip().upper()

            if exp not in per_class:
                per_class[exp] = {"total": 0, "correct": 0}
            per_class[exp]["total"] += 1

            is_match = (pred == exp)
            if is_match:
                passed += 1
                per_class[exp]["correct"] += 1

            details.append({
                "query": q,
                "predicted": pred,
                "expected": exp,
                "passed": is_match,
            })

        score = passed / float(total)
        class_summary = ", ".join([f"{k}: {v['correct']}/{v['total']}" for k, v in per_class.items()])

        return MetricScore(
            name="Intent Classification & Routing Accuracy",
            score=round(score, 4),
            percentage=round(score * 100.0, 2),
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            details=details,
            diagnostics=f"Overall: {passed}/{total}. Per class: ({class_summary}).",
        )

    @staticmethod
    def evaluate_memory_resolution(memory_turns: List[Dict[str, Any]]) -> MetricScore:
        """
        Evaluates conversational memory context resolution (anaphora, temporal/metric ellipsis).
        """
        total = len(memory_turns)
        if total == 0:
            return MetricScore("Conversational Memory Resolution", 1.0, 100.0, 0, 0, 0)

        passed = 0
        details = []

        for turn in memory_turns:
            raw_input = turn.get("raw_input", "")
            res_entities = set(turn.get("resolved_entities", []))
            exp_entities = set(turn.get("expected_entities", []))

            res_years = set(turn.get("resolved_years", []))
            exp_years = set(turn.get("expected_years", []))

            res_metrics = [m.lower() for m in turn.get("resolved_metrics", [])]
            exp_metrics = [m.lower() for m in turn.get("expected_metrics", [])]

            # Matching criteria
            entity_match = (exp_entities.issubset(res_entities)) if exp_entities else True
            year_match = (exp_years.issubset(res_years)) if exp_years else True
            metric_match = (all(any(em in rm for rm in res_metrics) for em in exp_metrics)) if exp_metrics else True

            turn_pass = entity_match and year_match and metric_match
            if turn_pass:
                passed += 1

            details.append({
                "input": raw_input,
                "passed": turn_pass,
                "entity_match": entity_match,
                "year_match": year_match,
                "metric_match": metric_match,
            })

        score = passed / float(total)
        return MetricScore(
            name="Conversational Context Resolution Accuracy",
            score=round(score, 4),
            percentage=round(score * 100.0, 2),
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            details=details,
            diagnostics=f"{passed}/{total} dialogue context transitions resolved successfully.",
        )
