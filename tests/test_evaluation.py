"""
Tests for Phase 16: Comprehensive FARE Evaluation Suite.
"""

import pytest

from evaluation.benchmark_dataset import (
    BENCHMARK_DATASET,
    CONVERSATIONAL_MEMORY_BENCHMARK,
    INTENT_CLASSIFICATION_BENCHMARK,
    NUMERICAL_CALCULATION_BENCHMARK,
    STATEMENT_EXTRACTION_BENCHMARK,
)
from evaluation.benchmark_runner import BenchmarkReport, BenchmarkRunner, run_benchmark
from evaluation.metrics import EvaluationMetrics, MetricScore


# -----------------------------------------------------------------------------
# 1. Unit Tests for Evaluation Metric Calculators
# -----------------------------------------------------------------------------

def test_evaluation_metrics_retrieval():
    cases = [
        {"query": "q1", "predicted_value": 100.0, "expected_value": 100.0},
        {"query": "q2", "predicted_value": 100.05, "expected_value": 100.0},  # within 0.1% rel tol
        {"query": "q3", "predicted_value": 150.0, "expected_value": 100.0},   # failed
        {"query": "q4", "predicted_value": None, "expected_value": 100.0},    # failed
    ]
    score = EvaluationMetrics.evaluate_retrieval(cases, tolerance_rel=0.001)
    assert isinstance(score, MetricScore)
    assert score.total_cases == 4
    assert score.passed_cases == 2
    assert score.failed_cases == 2
    assert score.percentage == 50.0


def test_evaluation_metrics_faithfulness():
    faithful_case = {
        "query": "What was Abbott's revenue in 2024?",
        "value": 41950000000.0,
        "evidence": {
            "form": "10-K",
            "filed_date": "2025-02-14",
            "accession_number": "0000001800-25-000010",
            "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
            "value": 41950000000.0,
        },
    }
    unfaithful_case_missing_acc = {
        "query": "q2",
        "value": 100.0,
        "evidence": {
            "form": "10-K",
            "filed_date": "2025-02-14",
            "accession_number": None,  # Missing!
            "concept": "Revenues",
            "value": 100.0,
        },
    }
    unfaithful_case_discrepancy = {
        "query": "q3",
        "value": 200.0,  # Value mismatch with evidence!
        "evidence": {
            "form": "10-K",
            "filed_date": "2025-02-14",
            "accession_number": "0000001800-25-000010",
            "concept": "Revenues",
            "value": 100.0,
        },
    }

    score = EvaluationMetrics.evaluate_faithfulness([
        faithful_case,
        unfaithful_case_missing_acc,
        unfaithful_case_discrepancy,
    ])
    assert score.total_cases == 3
    assert score.passed_cases == 1
    assert score.failed_cases == 2
    assert score.percentage == pytest.approx(33.33, rel=1e-2)


def test_evaluation_metrics_numerical():
    cases = [
        {"name": "c1", "calculated_value": 15.25, "expected_value": 15.25},
        {"name": "c2", "calculated_value": 15.26, "expected_value": 15.25},  # within 0.02 abs tol
        {"name": "c3", "calculated_value": 16.50, "expected_value": 15.25},  # fail
    ]
    score = EvaluationMetrics.evaluate_numerical_accuracy(cases, tolerance_abs=0.02)
    assert score.total_cases == 3
    assert score.passed_cases == 2
    assert score.percentage == pytest.approx(66.67, rel=1e-2)


def test_evaluation_metrics_intent_routing():
    cases = [
        {"query": "q1", "predicted_intent": "COMPARISON", "expected_intent": "COMPARISON"},
        {"query": "q2", "predicted_intent": "STATEMENT_EXTRACTION", "expected_intent": "STATEMENT_EXTRACTION"},
        {"query": "q3", "predicted_intent": "INVESTMENT_ANALYSIS", "expected_intent": "STATEMENT_EXTRACTION"},  # fail
    ]
    score = EvaluationMetrics.evaluate_intent_routing(cases)
    assert score.total_cases == 3
    assert score.passed_cases == 2
    assert score.percentage == pytest.approx(66.67, rel=1e-2)


def test_evaluation_metrics_memory_resolution():
    turns = [
        {
            "raw_input": "What about 2022?",
            "resolved_entities": ["ABBOTT LABORATORIES"],
            "expected_entities": ["ABBOTT LABORATORIES"],
            "resolved_years": [2022],
            "expected_years": [2022],
            "resolved_metrics": ["Revenue"],
            "expected_metrics": ["Revenue"],
        },
        {
            "raw_input": "What was its net income?",
            "resolved_entities": [],  # Failed entity inheritance
            "expected_entities": ["ABBOTT LABORATORIES"],
            "resolved_years": [2022],
            "expected_years": [2022],
            "resolved_metrics": ["Net Income"],
            "expected_metrics": ["Net Income"],
        }
    ]
    score = EvaluationMetrics.evaluate_memory_resolution(turns)
    assert score.total_cases == 2
    assert score.passed_cases == 1
    assert score.percentage == 50.0


# -----------------------------------------------------------------------------
# 2. Benchmark Dataset Integrity
# -----------------------------------------------------------------------------

def test_benchmark_dataset_integrity():
    assert len(STATEMENT_EXTRACTION_BENCHMARK) >= 10
    assert len(INTENT_CLASSIFICATION_BENCHMARK) >= 20
    assert len(CONVERSATIONAL_MEMORY_BENCHMARK) >= 2
    assert len(NUMERICAL_CALCULATION_BENCHMARK) >= 5

    # Check that statement extraction cases have positive numbers and valid years
    for tc in STATEMENT_EXTRACTION_BENCHMARK:
        assert tc.expected_value > 0
        assert tc.fiscal_year >= 2020
        assert len(tc.cik) == 10

    # Check that all intent cases have known categories
    valid_intents = {
        "STATEMENT_EXTRACTION", "INVESTMENT_ANALYSIS", "COMPARISON",
        "RISK_EXTRACTION", "TONE_ANALYSIS", "SCENARIO_SIMULATION", "GENERAL"
    }
    for tc in INTENT_CLASSIFICATION_BENCHMARK:
        assert tc.expected_intent in valid_intents


# -----------------------------------------------------------------------------
# 3. Full Benchmark Runner Execution
# -----------------------------------------------------------------------------

def test_full_benchmark_execution():
    runner = BenchmarkRunner()
    report = runner.run_full_benchmark()

    assert isinstance(report, BenchmarkReport)
    assert report.total_eval_cases >= 40

    # Ensure all dimension benchmarks meet production quality standards (>= 90%)
    assert report.retrieval_score.percentage >= 90.0, f"Retrieval score: {report.retrieval_score.percentage}%"
    assert report.faithfulness_score.percentage >= 90.0, f"Faithfulness score: {report.faithfulness_score.percentage}%"
    assert report.numerical_score.percentage >= 90.0, f"Numerical score: {report.numerical_score.percentage}%"
    assert report.intent_score.percentage >= 90.0, f"Intent score: {report.intent_score.percentage}%"
    assert report.memory_score.percentage >= 90.0, f"Memory score: {report.memory_score.percentage}%"
    assert report.composite_fare_score >= 90.0, f"Composite FARE score: {report.composite_fare_score}%"

    # Scorecard generation
    scorecard = report.generate_markdown_scorecard()
    assert "# FARE Benchmark Evaluation Scorecard" in scorecard
    assert "| Fact Retrieval Accuracy |" in scorecard
    assert "| Fact Grounding & Faithfulness |" in scorecard
    assert "| Numerical Calculation Precision |" in scorecard
    assert "| Intent Classification & Routing Accuracy |" in scorecard
    assert "| Conversational Context Resolution Accuracy |" in scorecard
