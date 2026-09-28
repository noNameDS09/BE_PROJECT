"""
Financial Validation Layer.

Operates prior to answer generation to enforce data integrity, mathematical correctness,
and source auditability across 7 key dimensions:
1. Retrieved values bounds & anomaly sanity
2. Calculation input completeness
3. Calculation output mathematical consistency
4. Source SEC metadata completeness
5. Missing data detection
6. Contradictory facts & accounting identity validation
7. Unit consistency
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from src.retrieval.financial_query import FinancialFactResult
from src.tools.financial_calculator import CalculationResult

logger = logging.getLogger(__name__)

# Reasonable financial sanity bounds
MAX_REASONABLE_VALUE = 50_000_000_000_000  # $50 Trillion (exceeds any single company's annual revenue/assets)
MIN_REASONABLE_YEAR = 1990
MAX_REASONABLE_YEAR = 2050


@dataclass
class ValidationIssue:
    """
    Representation of an issue detected by the validation layer.
    """
    check_name: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return f"[{self.severity}] {self.check_name}: {self.message}"


@dataclass
class ValidationReport:
    """
    Consolidated report produced by the validation layer.
    Answers must only be presented if is_valid is True (i.e. zero ERROR severity issues).
    """
    is_valid: bool
    has_warnings: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "has_warnings": self.has_warnings,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
            "passed_checks": self.passed_checks,
        }

    def __repr__(self) -> str:
        return (
            f"ValidationReport(is_valid={self.is_valid}, errors={self.error_count}, "
            f"warnings={self.warning_count}, passed={len(self.passed_checks)})"
        )


class FinancialValidator:
    """
    Multi-dimensional pre-generation validation engine.
    Ensures that factual retrievals and mathematical calculations meet strict audit standards.
    """

    # -------------------------------------------------------------------------
    # 1. Retrieved Values Validation
    # -------------------------------------------------------------------------

    def validate_retrieved_fact(
        self,
        fact: Union[FinancialFactResult, Dict[str, Any]],
        report: Optional[ValidationReport] = None
    ) -> ValidationReport:
        """
        Validates a single retrieved SEC fact against numerical bounds and financial sanity rules.
        """
        rep = report or ValidationReport(is_valid=True, has_warnings=False)
        d = fact.to_dict() if hasattr(fact, "to_dict") else fact

        val = d.get("value")
        concept = d.get("concept", "")

        # Check 1: Value existence and type
        if val is None:
            rep.issues.append(ValidationIssue(
                check_name="RetrievedValueCheck",
                severity="ERROR",
                message="Retrieved financial fact has a null/None value.",
                context={"fact": d}
            ))
            rep.is_valid = False
            return rep

        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            rep.issues.append(ValidationIssue(
                check_name="RetrievedValueCheck",
                severity="ERROR",
                message=f"Retrieved value '{val}' is not a finite numeric quantity.",
                context={"value": val}
            ))
            rep.is_valid = False
            return rep

        # Check 2: Implausible Extreme Values
        if abs(val) > MAX_REASONABLE_VALUE:
            rep.issues.append(ValidationIssue(
                check_name="ExtremeValueCheck",
                severity="WARNING",
                message=f"Value {val:,} exceeds plausible bounds (${MAX_REASONABLE_VALUE:,}). Check for scaling/unit tags.",
                context={"value": val, "concept": concept}
            ))
            rep.has_warnings = True

        # Check 3: Non-negativity sanity for balance sheet totals & revenue
        c_low = concept.lower()
        if any(term in c_low for term in ["assets", "cash"]) and "adjustment" not in c_low and val < 0:
            rep.issues.append(ValidationIssue(
                check_name="NonNegativityCheck",
                severity="ERROR",
                message=f"Concept '{concept}' reported negative value ({val:,}), which violates GAAP balance sheet constraints.",
                context={"concept": concept, "value": val}
            ))
            rep.is_valid = False

        if "revenue" in c_low and "contra" not in c_low and val < 0:
            rep.issues.append(ValidationIssue(
                check_name="RevenueNonNegativityCheck",
                severity="WARNING",
                message=f"Revenue reported a negative value ({val:,}). Verify if this represents an unusual restatement.",
                context={"concept": concept, "value": val}
            ))
            rep.has_warnings = True

        # Check 4: Fiscal Year sanity
        fy = d.get("fiscal_year")
        if fy is not None:
            if not isinstance(fy, int) or fy < MIN_REASONABLE_YEAR or fy > MAX_REASONABLE_YEAR:
                rep.issues.append(ValidationIssue(
                    check_name="FiscalYearBoundsCheck",
                    severity="ERROR",
                    message=f"Fiscal year {fy} is out of realistic chronological range ({MIN_REASONABLE_YEAR}–{MAX_REASONABLE_YEAR}).",
                    context={"fiscal_year": fy}
                ))
                rep.is_valid = False
            else:
                rep.passed_checks.append("FiscalYearBoundsCheck")

        # ---------------------------------------------------------------------
        # 4. Source Metadata Validation
        # ---------------------------------------------------------------------
        self._validate_source_metadata(d, rep)

        if rep.is_valid and "RetrievedValueCheck" not in rep.passed_checks:
            rep.passed_checks.append("RetrievedValueCheck")

        return rep

    def validate_source_metadata(
        self,
        fact: Union[FinancialFactResult, Dict[str, Any]],
        report: Optional[ValidationReport] = None
    ) -> ValidationReport:
        """Validates SEC filing provenance metadata directly."""
        rep = report or ValidationReport(is_valid=True, has_warnings=False)
        d = fact.to_dict() if hasattr(fact, "to_dict") else fact
        self._validate_source_metadata(d, rep)
        return rep

    def _validate_source_metadata(self, fact_dict: Dict[str, Any], rep: ValidationReport) -> None:
        """Validates SEC filing provenance metadata."""
        form = fact_dict.get("form")
        filed_date = fact_dict.get("filed_date")
        company = fact_dict.get("source_company")
        cik = fact_dict.get("source_cik")
        concept = fact_dict.get("concept")

        if not form or form == "Unknown":
            rep.issues.append(ValidationIssue(
                check_name="SourceMetadataCheck",
                severity="WARNING",
                message="Source SEC form is unknown or unspecified.",
                context={"form": form}
            ))
            rep.has_warnings = True

        if not filed_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(filed_date)):
            rep.issues.append(ValidationIssue(
                check_name="SourceMetadataCheck",
                severity="WARNING",
                message=f"Source filing date '{filed_date}' is missing or does not match ISO format (YYYY-MM-DD).",
                context={"filed_date": filed_date}
            ))
            rep.has_warnings = True

        if not company or not cik:
            rep.issues.append(ValidationIssue(
                check_name="SourceMetadataCheck",
                severity="ERROR",
                message="Fact lacks source company name or CIK provenance.",
                context={"company": company, "cik": cik}
            ))
            rep.is_valid = False

        if not concept:
            rep.issues.append(ValidationIssue(
                check_name="SourceMetadataCheck",
                severity="ERROR",
                message="Fact lacks underlying SEC XBRL concept name.",
                context={"fact": fact_dict}
            ))
            rep.is_valid = False
        else:
            rep.passed_checks.append("SourceMetadataCheck")

    # -------------------------------------------------------------------------
    # 2 & 3. Calculation Inputs & Outputs Validation
    # -------------------------------------------------------------------------

    def validate_calculation(
        self,
        calculation: Union[CalculationResult, Dict[str, Any]],
        report: Optional[ValidationReport] = None
    ) -> ValidationReport:
        """
        Validates mathematical calculation integrity:
        - Inputs completeness and non-null status
        - Denominator non-zero check
        - Output mathematical consistency against expected formula
        - Unit consistency
        """
        rep = report or ValidationReport(is_valid=True, has_warnings=False)
        d = calculation.to_dict() if hasattr(calculation, "to_dict") else calculation

        metric = d.get("metric", "Unknown Metric")
        status = d.get("status")
        value = d.get("value")
        inputs = d.get("inputs", [])
        formula = d.get("formula", "")

        # Check 1: Input completeness
        if not inputs:
            rep.issues.append(ValidationIssue(
                check_name="CalculationInputCheck",
                severity="ERROR",
                message=f"Calculation for '{metric}' has no input records.",
                context={"calculation": d}
            ))
            rep.is_valid = False
            return rep

        input_values = [inp.get("value") for inp in inputs if isinstance(inp, dict)]
        if any(v is None for v in input_values):
            if status != "MISSING_INPUTS":
                rep.issues.append(ValidationIssue(
                    check_name="CalculationInputCheck",
                    severity="ERROR",
                    message=f"Calculation for '{metric}' contains null input values but status is '{status}'.",
                    context={"inputs": inputs}
                ))
                rep.is_valid = False
            else:
                rep.passed_checks.append("MissingInputHandledCorrectly")
            return rep

        # Check 2: Unit Consistency across inputs
        input_units = {inp.get("unit") for inp in inputs if isinstance(inp, dict) and inp.get("unit")}
        if len(input_units) > 1:
            if status != "UNIT_MISMATCH":
                rep.issues.append(ValidationIssue(
                    check_name="UnitConsistencyCheck",
                    severity="ERROR",
                    message=f"Calculation for '{metric}' received conflicting input units: {input_units}.",
                    context={"inputs": inputs}
                ))
                rep.is_valid = False
            else:
                rep.passed_checks.append("UnitMismatchHandledCorrectly")
            return rep
        else:
            rep.passed_checks.append("UnitConsistencyCheck")

        # Check 3: Zero Denominator Handling
        if len(input_values) >= 2 and input_values[1] == 0:
            if status != "ZERO_DENOMINATOR":
                rep.issues.append(ValidationIssue(
                    check_name="ZeroDenominatorCheck",
                    severity="ERROR",
                    message=f"Calculation for '{metric}' has zero denominator but status is '{status}' (value={value}).",
                    context={"denominator": input_values[1]}
                ))
                rep.is_valid = False
            else:
                rep.passed_checks.append("ZeroDenominatorHandledCorrectly")
            return rep

        # Check 4: Output Verification against Formula
        if status == "SUCCESS" and value is not None:
            if math.isnan(value) or math.isinf(value):
                rep.issues.append(ValidationIssue(
                    check_name="CalculationOutputCheck",
                    severity="ERROR",
                    message=f"Calculation result for '{metric}' is NaN or Infinite.",
                    context={"value": value}
                ))
                rep.is_valid = False
                return rep

            # Re-compute mathematically to verify accuracy
            recomputed = self._recompute_formula(metric, input_values)
            if recomputed is not None:
                diff = abs(value - recomputed)
                if diff > 0.05:  # Tolerance beyond rounding
                    rep.issues.append(ValidationIssue(
                        check_name="MathematicalConsistencyCheck",
                        severity="ERROR",
                        message=(
                            f"Mathematical discrepancy in '{metric}': reported {value}, "
                            f"recomputed {recomputed:.4f} (diff={diff:.4f})."
                        ),
                        context={"reported": value, "recomputed": recomputed, "inputs": input_values}
                    ))
                    rep.is_valid = False
                else:
                    rep.passed_checks.append("MathematicalConsistencyCheck")

        return rep

    def _recompute_formula(self, metric: str, inputs: List[float]) -> Optional[float]:
        """Independent mathematical recomputation for verification."""
        if len(inputs) < 2:
            return None
        v1, v2 = float(inputs[0]), float(inputs[1])

        if metric == "Revenue Growth":
            return ((v1 - v2) / abs(v2)) * 100.0 if v2 != 0 else None
        elif "Margin" in metric:
            return (v1 / v2) * 100.0 if v2 != 0 else None
        elif metric in ("ROA", "ROE"):
            return (v1 / v2) * 100.0 if v2 != 0 else None
        elif metric in ("Current Ratio", "Debt-to-Equity", "Debt Ratio"):
            return (v1 / v2) if v2 != 0 else None

        return None

    # -------------------------------------------------------------------------
    # 5 & 6. Contradictory Facts & Accounting Identity Validation
    # -------------------------------------------------------------------------

    def validate_facts_consistency(
        self,
        facts: List[Union[FinancialFactResult, Dict[str, Any]]],
        report: Optional[ValidationReport] = None
    ) -> ValidationReport:
        """
        Detects contradictory facts or duplicate filings with irreconcilable values.
        """
        rep = report or ValidationReport(is_valid=True, has_warnings=False)
        seen_keys: Dict[Tuple[str, str, int, str], Dict[str, Any]] = {}

        for fact in facts:
            d = fact.to_dict() if hasattr(fact, "to_dict") else fact
            key = (
                str(d.get("source_cik")),
                str(d.get("concept")),
                int(d.get("fiscal_year", 0)),
                str(d.get("fiscal_period", "FY"))
            )

            if key in seen_keys:
                prev = seen_keys[key]
                v_curr = d.get("value")
                v_prev = prev.get("value")
                if v_curr != v_prev:
                    rep.issues.append(ValidationIssue(
                        check_name="ContradictoryFactsCheck",
                        severity="WARNING",
                        message=(
                            f"Contradictory facts detected for {key}: filed {d.get('filed_date')} "
                            f"reports {v_curr:,} vs filed {prev.get('filed_date')} reports {v_prev:,}."
                        ),
                        context={"fact1": d, "fact2": prev}
                    ))
                    rep.has_warnings = True
            else:
                seen_keys[key] = d

        rep.passed_checks.append("ContradictoryFactsCheck")
        return rep

    def validate_accounting_identity(
        self,
        assets: Optional[float],
        liabilities: Optional[float],
        equity: Optional[float],
        tolerance_pct: float = 2.0,
        report: Optional[ValidationReport] = None
    ) -> ValidationReport:
        """
        Enforces Fundamental Accounting Identity: Assets = Liabilities + Equity
        Flags severe discrepancies exceeding tolerance percentage.
        """
        rep = report or ValidationReport(is_valid=True, has_warnings=False)

        if assets is None or liabilities is None or equity is None:
            rep.issues.append(ValidationIssue(
                check_name="AccountingIdentityCheck",
                severity="INFO",
                message="Cannot verify accounting identity: one or more of Assets, Liabilities, or Equity is missing.",
                context={"assets": assets, "liabilities": liabilities, "equity": equity}
            ))
            return rep

        rhs = liabilities + equity
        diff = abs(assets - rhs)
        pct_diff = (diff / abs(assets)) * 100.0 if assets != 0 else 0.0

        if pct_diff > tolerance_pct:
            rep.issues.append(ValidationIssue(
                check_name="AccountingIdentityCheck",
                severity="WARNING",
                message=(
                    f"Accounting identity discrepancy: Assets (${assets:,.0f}) != Liabilities + Equity "
                    f"(${rhs:,.0f}), discrepancy of {pct_diff:.2f}%."
                ),
                context={"assets": assets, "liabilities": liabilities, "equity": equity, "discrepancy_pct": pct_diff}
            ))
            rep.has_warnings = True
        else:
            rep.passed_checks.append("AccountingIdentityCheck")

        return rep

    # -------------------------------------------------------------------------
    # Comprehensive Pipeline Gatekeeper
    # -------------------------------------------------------------------------

    def validate_pipeline_payload(
        self,
        facts: Optional[List[Any]] = None,
        calculations: Optional[List[Any]] = None
    ) -> ValidationReport:
        """
        Master gatekeeper called BEFORE final answer generation.
        Validates all facts, calculations, and consistency concurrently.
        """
        report = ValidationReport(is_valid=True, has_warnings=False)

        if facts:
            for f in facts:
                self.validate_retrieved_fact(f, report=report)
            self.validate_facts_consistency(facts, report=report)

        if calculations:
            for c in calculations:
                self.validate_calculation(c, report=report)

        return report


# Singleton instance and convenience function
_DEFAULT_VALIDATOR: Optional[FinancialValidator] = None


def get_default_validator() -> FinancialValidator:
    global _DEFAULT_VALIDATOR
    if _DEFAULT_VALIDATOR is None:
        _DEFAULT_VALIDATOR = FinancialValidator()
    return _DEFAULT_VALIDATOR


def validate_financial_data(
    facts: Optional[List[Any]] = None,
    calculations: Optional[List[Any]] = None
) -> ValidationReport:
    """Convenience function to run full validation prior to answer generation."""
    return get_default_validator().validate_pipeline_payload(facts=facts, calculations=calculations)
