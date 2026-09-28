"""
FARE Evaluation Framework for SEC Corporate Intelligence.
"""

from evaluation.benchmark_dataset import BENCHMARK_DATASET
from evaluation.benchmark_runner import BenchmarkReport, BenchmarkRunner, run_benchmark
from evaluation.metrics import EvaluationMetrics, MetricScore

__all__ = [
    "BENCHMARK_DATASET",
    "BenchmarkRunner",
    "BenchmarkReport",
    "run_benchmark",
    "EvaluationMetrics",
    "MetricScore",
]
