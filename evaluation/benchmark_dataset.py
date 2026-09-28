"""
Curated Ground-Truth Benchmark Dataset for FARE Evaluation.

Grounded in SEC EDGAR facts from companyfacts.zip for Abbott Laboratories,
Advanced Micro Devices (AMD), AAR Corp, and Aflac Incorporated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StatementTestCase:
    """Ground truth case for factual statement extraction."""
    query: str
    company: str
    cik: str
    metric: str
    fiscal_year: int
    expected_value: float
    unit: str = "USD"
    tolerance_rel: float = 0.001  # 0.1% tolerance for float rounding


@dataclass
class IntentTestCase:
    """Ground truth case for Orchestrator intent classification."""
    query: str
    expected_intent: str
    description: str = ""


@dataclass
class MemorySessionCase:
    """Multi-turn dialogue session testing conversational memory."""
    session_id: str
    turns: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CalculationTestCase:
    """Deterministic calculation ground truth."""
    name: str
    metric_type: str
    inputs: Dict[str, float]
    expected_value: float
    tolerance: float = 0.01


STATEMENT_EXTRACTION_BENCHMARK: List[StatementTestCase] = [
    # Abbott Laboratories (CIK 0000001800)
    StatementTestCase(
        query="What was Abbott's revenue in 2024?",
        company="Abbott",
        cik="0000001800",
        metric="Revenue",
        fiscal_year=2024,
        expected_value=41950000000.0,
    ),
    StatementTestCase(
        query="What was Abbott's net income in 2024?",
        company="Abbott",
        cik="0000001800",
        metric="Net Income",
        fiscal_year=2024,
        expected_value=13402000000.0,
    ),
    StatementTestCase(
        query="What was Abbott's operating income in 2024?",
        company="Abbott",
        cik="0000001800",
        metric="Operating Income",
        fiscal_year=2024,
        expected_value=6825000000.0,
    ),
    StatementTestCase(
        query="What was Abbott's revenue in 2023?",
        company="Abbott",
        cik="0000001800",
        metric="Revenue",
        fiscal_year=2023,
        expected_value=40109000000.0,
    ),
    StatementTestCase(
        query="What was Abbott's revenue in 2022?",
        company="Abbott",
        cik="0000001800",
        metric="Revenue",
        fiscal_year=2022,
        expected_value=43653000000.0,
    ),
    # Advanced Micro Devices (CIK 0000002488)
    StatementTestCase(
        query="What was AMD's revenue in 2023?",
        company="AMD",
        cik="0000002488",
        metric="Revenue",
        fiscal_year=2023,
        expected_value=22680000000.0,
    ),
    StatementTestCase(
        query="What was AMD's net income in 2023?",
        company="AMD",
        cik="0000002488",
        metric="Net Income",
        fiscal_year=2023,
        expected_value=854000000.0,
    ),
    StatementTestCase(
        query="What was AMD's revenue in 2022?",
        company="AMD",
        cik="0000002488",
        metric="Revenue",
        fiscal_year=2022,
        expected_value=23601000000.0,
    ),
    StatementTestCase(
        query="What was AMD's revenue in 2021?",
        company="AMD",
        cik="0000002488",
        metric="Revenue",
        fiscal_year=2021,
        expected_value=16434000000.0,
    ),
    # AAR Corp (CIK 0000001750)
    StatementTestCase(
        query="What was AAR Corp's revenue in 2023?",
        company="AAR CORP.",
        cik="0000001750",
        metric="Revenue",
        fiscal_year=2023,
        expected_value=1990500000.0,
    ),
    # Aflac (CIK 0000004977)
    StatementTestCase(
        query="What was Aflac's revenue in 2023?",
        company="Aflac Incorporated",
        cik="0000004977",
        metric="Revenue",
        fiscal_year=2023,
        expected_value=18701000000.0,
    ),
]


INTENT_CLASSIFICATION_BENCHMARK: List[IntentTestCase] = [
    # 1. Statement Extraction
    IntentTestCase("What was Abbott's revenue in 2024?", "STATEMENT_EXTRACTION"),
    IntentTestCase("How much cash did AMD have in 2023?", "STATEMENT_EXTRACTION"),
    IntentTestCase("Tell me the net income of Aflac in 2023", "STATEMENT_EXTRACTION"),
    IntentTestCase("What was AAR Corp's operating income for 2023?", "STATEMENT_EXTRACTION"),

    # 2. Investment Analysis
    IntentTestCase("Analyze Abbott's financial performance from 2022 to 2024", "INVESTMENT_ANALYSIS"),
    IntentTestCase("Evaluate AMD's revenue trends over time", "INVESTMENT_ANALYSIS"),
    IntentTestCase("How has Aflac's financial health evolved between 2021 and 2023?", "INVESTMENT_ANALYSIS"),
    IntentTestCase("Analyze the growth trajectory of AAR Corp", "INVESTMENT_ANALYSIS"),

    # 3. Comparison
    IntentTestCase("Compare Abbott and AMD in 2023", "COMPARISON"),
    IntentTestCase("Abbott vs AMD margin benchmarking", "COMPARISON"),
    IntentTestCase("Compare Aflac and Abbott performance in 2023", "COMPARISON"),
    IntentTestCase("Compare AAR Corp versus AMD on profitability", "COMPARISON"),

    # 4. Risk Extraction
    IntentTestCase("What financial risks does Abbott face?", "RISK_EXTRACTION"),
    IntentTestCase("Assess solvency and leverage risks for AMD", "RISK_EXTRACTION"),
    IntentTestCase("Evaluate default threat and liquidity distress for AAR Corp", "RISK_EXTRACTION"),
    IntentTestCase("What bankruptcy risks exist for Aflac?", "RISK_EXTRACTION"),

    # 5. Tone Analysis
    IntentTestCase("Analyze management tone for Abbott in 2023", "TONE_ANALYSIS"),
    IntentTestCase("What was the sentiment in AMD's earnings remarks?", "TONE_ANALYSIS"),
    IntentTestCase("Did the tone shift between 2022 and 2023 for Abbott?", "TONE_ANALYSIS"),
    IntentTestCase("Evaluate managerial optimism and mood for Aflac", "TONE_ANALYSIS"),

    # 6. Scenario Simulation
    IntentTestCase("Simulate a 10% revenue drop for Abbott in 2024", "SCENARIO_SIMULATION"),
    IntentTestCase("Stress test AMD with a 5% inflation shock", "SCENARIO_SIMULATION"),
    IntentTestCase("What if revenue drops 15% for AAR Corp?", "SCENARIO_SIMULATION"),
    IntentTestCase("Run a breakeven analysis for Abbott in 2024", "SCENARIO_SIMULATION"),

    # 7. General Fallback
    IntentTestCase("Hello, what is the weather today?", "GENERAL"),
    IntentTestCase("Who won the 2022 World Cup?", "GENERAL"),
    IntentTestCase("Can you write a poem about finance?", "GENERAL"),
]


CONVERSATIONAL_MEMORY_BENCHMARK: List[MemorySessionCase] = [
    MemorySessionCase(
        session_id="eval-session-abbott-multi-turn",
        turns=[
            {
                "turn": 1,
                "input": "What was Abbott's revenue in 2023?",
                "expected_entities": ["ABBOTT LABORATORIES"],
                "expected_metrics": ["Revenue"],
                "expected_years": [2023],
                "description": "Baseline turn establishing company, metric, and year.",
            },
            {
                "turn": 2,
                "input": "What about 2022?",
                "expected_entities": ["ABBOTT LABORATORIES"],
                "expected_metrics": ["Revenue"],
                "expected_years": [2022],
                "description": "Temporal ellipsis inheriting company and metric.",
            },
            {
                "turn": 3,
                "input": "What was its net income?",
                "expected_entities": ["ABBOTT LABORATORIES"],
                "expected_metrics": ["Net Income"],
                "expected_years": [2022],
                "description": "Anaphoric reference ('its') and metric ellipsis inheriting year.",
            },
            {
                "turn": 4,
                "input": "Compare it with AMD",
                "expected_entities": ["ABBOTT LABORATORIES", "ADVANCED MICRO DEVICES INC"],
                "expected_metrics": ["Net Income"],
                "expected_years": [2022],
                "description": "Comparative entity bridging from prior context.",
            },
        ]
    ),
    MemorySessionCase(
        session_id="eval-session-amd-multi-turn",
        turns=[
            {
                "turn": 1,
                "input": "Analyze AMD financial trends",
                "expected_entities": ["ADVANCED MICRO DEVICES INC"],
                "expected_metrics": [],
                "expected_years": [],
                "description": "Entity establishment without explicit metric/year.",
            },
            {
                "turn": 2,
                "input": "What about its revenue in 2021?",
                "expected_entities": ["ADVANCED MICRO DEVICES INC"],
                "expected_metrics": ["Revenue"],
                "expected_years": [2021],
                "description": "Pronoun resolution inheriting AMD.",
            },
        ]
    )
]


NUMERICAL_CALCULATION_BENCHMARK: List[CalculationTestCase] = [
    CalculationTestCase(
        name="Abbott Revenue Growth FY23->FY24",
        metric_type="revenue_growth",
        inputs={"current": 41950000000.0, "previous": 40109000000.0},
        expected_value=4.58999,  # ~4.59%
        tolerance=0.01,
    ),
    CalculationTestCase(
        name="Abbott Net Profit Margin FY24",
        metric_type="profit_margin",
        inputs={"income": 5683000000.0, "revenue": 41950000000.0},
        expected_value=13.54708,  # ~13.55%
        tolerance=0.01,
    ),
    CalculationTestCase(
        name="Abbott Operating Margin FY24",
        metric_type="operating_margin",
        inputs={"income": 6864000000.0, "revenue": 41950000000.0},
        expected_value=16.36234,  # ~16.36%
        tolerance=0.01,
    ),
    CalculationTestCase(
        name="AMD Revenue Growth FY22->FY23",
        metric_type="revenue_growth",
        inputs={"current": 22680000000.0, "previous": 23601000000.0},
        expected_value=-3.90238,  # ~ -3.90%
        tolerance=0.01,
    ),
    CalculationTestCase(
        name="AMD Net Profit Margin FY23",
        metric_type="profit_margin",
        inputs={"income": 854000000.0, "revenue": 22680000000.0},
        expected_value=3.76543,  # ~3.77%
        tolerance=0.01,
    ),
]


BENCHMARK_DATASET = {
    "statement_extraction": STATEMENT_EXTRACTION_BENCHMARK,
    "intent_classification": INTENT_CLASSIFICATION_BENCHMARK,
    "conversational_memory": CONVERSATIONAL_MEMORY_BENCHMARK,
    "numerical_calculation": NUMERICAL_CALCULATION_BENCHMARK,
}
