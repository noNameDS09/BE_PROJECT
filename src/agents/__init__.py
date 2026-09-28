"""
Agents package for FARE-style financial multi-agent reasoning.
"""

from src.agents.statement_extraction_agent import (
    StatementExtractionAgent,
    StatementExtractionResult,
    extract_financial_statement_fact,
    get_default_statement_agent,
)

from src.agents.investment_agent import (
    InvestmentAgent,
    InvestmentAnalysisResult,
    analyze_financial_performance,
    get_default_investment_agent,
)

from src.agents.comparison_agent import (
    ComparisonAgent,
    ComparisonResult,
    compare_companies,
    get_default_comparison_agent,
)

from src.agents.risk_extraction_agent import (
    RiskExtractionAgent,
    RiskExtractionResult,
    RiskItem,
    assess_company_risks,
    get_default_risk_agent,
    LIMITATION_NOTICE,
)

from src.agents.orchestrator import (
    FinancialOrchestrator,
    OrchestratorResponse,
    process_query,
    get_default_orchestrator,
    INTENT_STATEMENT_EXTRACTION,
    INTENT_INVESTMENT_ANALYSIS,
    INTENT_COMPARISON,
    INTENT_RISK_EXTRACTION,
)

__all__ = [
    "StatementExtractionAgent",
    "StatementExtractionResult",
    "extract_financial_statement_fact",
    "get_default_statement_agent",
    "InvestmentAgent",
    "InvestmentAnalysisResult",
    "analyze_financial_performance",
    "get_default_investment_agent",
    "ComparisonAgent",
    "ComparisonResult",
    "compare_companies",
    "get_default_comparison_agent",
    "RiskExtractionAgent",
    "RiskExtractionResult",
    "RiskItem",
    "assess_company_risks",
    "get_default_risk_agent",
    "LIMITATION_NOTICE",
    "FinancialOrchestrator",
    "OrchestratorResponse",
    "process_query",
    "get_default_orchestrator",
    "INTENT_STATEMENT_EXTRACTION",
    "INTENT_INVESTMENT_ANALYSIS",
    "INTENT_COMPARISON",
    "INTENT_RISK_EXTRACTION",
]
