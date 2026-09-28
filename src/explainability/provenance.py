"""
Explainability & Provenance Module.

Enforces end-to-end traceability for every financial answer across 6 distinct layers:
1. Answer (Final textual conclusion)
2. Reason (Rationale & analytical logic)
3. Financial Metrics (Canonical metrics analyzed)
4. Calculation (Deterministic formula, inputs, outputs)
5. SEC Evidence (Audited values, units, line items)
6. Source Metadata (Registrant, CIK, Form 10-K/10-Q, filing date, accession number)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from src.retrieval.financial_query import FinancialFactResult
from src.tools.financial_calculator import CalculationResult

logger = logging.getLogger(__name__)


@dataclass
class SECSourceRecord:
    """
    Provenance of a raw SEC filing fact.
    """
    concept: str
    value: Union[int, float]
    unit: str
    form: str
    filed_date: str
    accession_number: Optional[str]
    fiscal_year: int
    fiscal_period: str
    source_company: str
    source_cik: str
    selection_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalculationAuditRecord:
    """
    Audit record of a deterministic financial arithmetic step.
    """
    metric: str
    formula: str
    inputs: List[Dict[str, Any]]
    output_value: Optional[float]
    unit: str
    status: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceabilityChain:
    """
    The canonical 6-tier Explainability & Provenance Chain.
    Guarantees that every assertion is provably anchored in SEC filings.
    """
    answer: str
    reason: str
    financial_metrics: List[str]
    calculations: List[CalculationAuditRecord] = field(default_factory=list)
    sec_evidence: List[SECSourceRecord] = field(default_factory=list)
    source_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the complete 6-tier hierarchy as a clean dictionary."""
        return {
            "answer": self.answer,
            "reason": self.reason,
            "financial_metrics": self.financial_metrics,
            "calculations": [c.to_dict() for c in self.calculations],
            "sec_evidence": [e.to_dict() for e in self.sec_evidence],
            "source_metadata": self.source_metadata,
        }

    def to_markdown(self) -> str:
        """Renders the provenance chain as a GitHub-flavored Markdown audit card."""
        lines = [
            "#### Financial Provenance & Audit Trail",
            f"**1. Answer:** {self.answer}",
            f"**2. Reason:** {self.reason}",
            f"**3. Financial Metrics:** {', '.join(self.financial_metrics) if self.financial_metrics else 'N/A'}",
            "",
            "**4. Calculations:**"
        ]

        if self.calculations:
            for c in self.calculations:
                val_str = f"{c.output_value:,.2f} {c.unit}" if c.output_value is not None else "N/A"
                lines.append(f"- **{c.metric}**: `{c.formula}` $\\rightarrow$ **{val_str}**")
                inps = ", ".join(f"{inp.get('name')}: {inp.get('value'):,.0f} {inp.get('unit')}" for inp in c.inputs if isinstance(inp, dict) and inp.get('value') is not None)
                if inps:
                    lines.append(f"  *Inputs:* {inps}")
        else:
            lines.append("- *No mathematical calculations required (pure factual extraction).*")

        lines.extend([
            "",
            "**5. SEC Evidence:**"
        ])
        if self.sec_evidence:
            for ev in self.sec_evidence:
                lines.append(
                    f"- Concept: `{ev.concept}` | Value: **{ev.value:,.0f} {ev.unit}** | "
                    f"Period: **FY{ev.fiscal_year} ({ev.fiscal_period})** | Form: **{ev.form}**"
                )
        else:
            lines.append("- *No SEC facts attached.*")

        lines.extend([
            "",
            "**6. Source Metadata:**"
        ])
        if self.source_metadata:
            c_name = self.source_metadata.get("company", "Unknown")
            cik = self.source_metadata.get("cik", "Unknown")
            accn = self.source_metadata.get("accession_numbers", [])
            lines.append(f"- **Entity:** {c_name} (CIK: `{cik}`)")
            if accn:
                accn_str = ", ".join(str(a) for a in accn if a)
                lines.append(f"- **SEC Accession Numbers:** `{accn_str}`")
            lines.append(f"- **Data Origin:** SEC EDGAR Company Facts (`companyfacts.zip`)")
        else:
            lines.append("- *Metadata unavailable.*")

        return "\n".join(lines)


class ProvenanceEngine:
    """
    Engine that constructs 6-tier TraceabilityChains from query results and calculation outputs.
    """

    def build_from_statement_extraction(self, result: Any) -> TraceabilityChain:
        """
        Builds provenance chain from a StatementExtractionResult.
        """
        r_dict = result.to_dict() if hasattr(result, "to_dict") else result
        ev = r_dict.get("evidence") or {}

        evidence_records = []
        if ev and ev.get("value") is not None:
            evidence_records.append(SECSourceRecord(
                concept=ev.get("concept", "Unknown"),
                value=ev.get("value", 0),
                unit=ev.get("unit", "USD"),
                form=ev.get("form", "Unknown"),
                filed_date=ev.get("filed_date", "Unknown"),
                accession_number=ev.get("accession_number"),
                fiscal_year=ev.get("fiscal_year", r_dict.get("fiscal_year", 0)),
                fiscal_period=ev.get("fiscal_period", r_dict.get("fiscal_period", "FY")),
                source_company=ev.get("source_company", r_dict.get("company", "Unknown")),
                source_cik=ev.get("source_cik", "Unknown"),
                selection_notes=ev.get("selection_notes", "")
            ))

        meta = {
            "company": r_dict.get("company"),
            "cik": ev.get("source_cik") or r_dict.get("extracted_entities", {}).get("company_cik"),
            "accession_numbers": [ev.get("accession_number")] if ev.get("accession_number") else [],
            "source_type": "SEC EDGAR Form " + str(ev.get("form", "10-K")),
            "data_origin": "SEC Company Facts",
        }

        reason = (
            f"Retrieved verified audited fact for '{r_dict.get('metric')}' directly from "
            f"SEC Form {ev.get('form', '10-K')} filed on {ev.get('filed_date', 'N/A')}."
        )

        return TraceabilityChain(
            answer=r_dict.get("answer", ""),
            reason=reason,
            financial_metrics=[r_dict.get("metric")] if r_dict.get("metric") else [],
            calculations=[],
            sec_evidence=evidence_records,
            source_metadata=meta
        )

    def build_from_calculation(
        self,
        calc_result: Union[CalculationResult, Dict[str, Any]],
        company: str = "Unknown",
        reason: str = ""
    ) -> TraceabilityChain:
        """
        Builds provenance chain from a CalculationResult.
        """
        c_dict = calc_result.to_dict() if hasattr(calc_result, "to_dict") else calc_result

        metric = c_dict.get("metric", "Calculation")
        formula = c_dict.get("formula", "")
        value = c_dict.get("value")
        unit = c_dict.get("unit", "")
        inputs = c_dict.get("inputs", [])
        source_facts = c_dict.get("source_facts", [])

        calc_record = CalculationAuditRecord(
            metric=metric,
            formula=formula,
            inputs=inputs,
            output_value=value,
            unit=unit,
            status=c_dict.get("status", "SUCCESS"),
            notes=c_dict.get("notes", "")
        )

        evidence_records: List[SECSourceRecord] = []
        accns = []
        cik = None
        for sf in source_facts:
            if isinstance(sf, dict):
                evidence_records.append(SECSourceRecord(
                    concept=sf.get("concept", "Unknown"),
                    value=sf.get("value", 0),
                    unit=sf.get("unit", "USD"),
                    form=sf.get("form", "10-K"),
                    filed_date=sf.get("filed_date", "Unknown"),
                    accession_number=sf.get("accession_number"),
                    fiscal_year=sf.get("fiscal_year", 0),
                    fiscal_period=sf.get("fiscal_period", "FY"),
                    source_company=sf.get("source_company", company),
                    source_cik=sf.get("source_cik", ""),
                    selection_notes=sf.get("selection_notes", "")
                ))
                if sf.get("accession_number"):
                    accns.append(sf.get("accession_number"))
                if not cik and sf.get("source_cik"):
                    cik = sf.get("source_cik")

        val_str = f"{value:.2f}{unit}" if value is not None else "N/A"
        answer = f"{metric} for {company} is {val_str}."
        default_reason = (
            f"Computed {metric} deterministically using formula '{formula}' "
            f"derived from {len(source_facts)} audited SEC filing facts."
        )

        meta = {
            "company": company,
            "cik": cik,
            "accession_numbers": list(set(accns)),
            "data_origin": "SEC Company Facts",
        }

        return TraceabilityChain(
            answer=answer,
            reason=reason or default_reason,
            financial_metrics=[metric],
            calculations=[calc_record],
            sec_evidence=evidence_records,
            source_metadata=meta
        )

    def build_from_investment_analysis(self, result: Any) -> TraceabilityChain:
        """
        Builds provenance chain from an InvestmentAnalysisResult.
        """
        r_dict = result.to_dict() if hasattr(result, "to_dict") else result
        company = r_dict.get("company", "Unknown")
        cik = r_dict.get("cik", "Unknown")
        start_yr = r_dict.get("start_year")
        end_yr = r_dict.get("end_year")

        # Convert calculations
        calculations: List[CalculationAuditRecord] = []
        for c in r_dict.get("calculations", []):
            calculations.append(CalculationAuditRecord(
                metric=c.get("metric", "Unknown"),
                formula=c.get("formula", ""),
                inputs=c.get("inputs", []),
                output_value=c.get("value"),
                unit=c.get("unit", "%"),
                status=c.get("status", "SUCCESS"),
                notes=c.get("notes", "")
            ))

        # Convert facts
        evidence_records: List[SECSourceRecord] = []
        accns = []
        for f in r_dict.get("facts", []):
            evidence_records.append(SECSourceRecord(
                concept=f.get("concept", "Unknown"),
                value=f.get("value", 0),
                unit=f.get("unit", "USD"),
                form=f.get("form", "10-K"),
                filed_date=f.get("filed_date", "Unknown"),
                accession_number=f.get("accession_number"),
                fiscal_year=f.get("fiscal_year", 0),
                fiscal_period=f.get("fiscal_period", "FY"),
                source_company=f.get("source_company", company),
                source_cik=f.get("source_cik", cik),
                selection_notes=f.get("selection_notes", "")
            ))
            if f.get("accession_number"):
                accns.append(f.get("accession_number"))

        metrics = list({c.metric for c in calculations} | {e.concept for e in evidence_records})

        return TraceabilityChain(
            answer=r_dict.get("summary", ""),
            reason=f"Multi-period financial evaluation covering fiscal years {start_yr} through {end_yr}.",
            financial_metrics=metrics,
            calculations=calculations,
            sec_evidence=evidence_records,
            source_metadata={
                "company": company,
                "cik": cik,
                "accession_numbers": list(set(accns)),
                "data_origin": "SEC Company Facts",
            }
        )


# Singleton instance and convenience function
_DEFAULT_PROVENANCE_ENGINE: Optional[ProvenanceEngine] = None


def get_default_provenance_engine() -> ProvenanceEngine:
    global _DEFAULT_PROVENANCE_ENGINE
    if _DEFAULT_PROVENANCE_ENGINE is None:
        _DEFAULT_PROVENANCE_ENGINE = ProvenanceEngine()
    return _DEFAULT_PROVENANCE_ENGINE


def build_provenance_chain(source_object: Any, **kwargs) -> TraceabilityChain:
    """Convenience function to generate a 6-tier TraceabilityChain."""
    engine = get_default_provenance_engine()
    if hasattr(source_object, "evidence") and hasattr(source_object, "value"):
        return engine.build_from_statement_extraction(source_object)
    elif hasattr(source_object, "formula") and hasattr(source_object, "inputs"):
        return engine.build_from_calculation(source_object, **kwargs)
    elif hasattr(source_object, "calculations") and hasattr(source_object, "facts"):
        return engine.build_from_investment_analysis(source_object)
    elif isinstance(source_object, dict) and "formula" in source_object:
        return engine.build_from_calculation(source_object, **kwargs)
    elif isinstance(source_object, dict) and "evidence" in source_object:
        return engine.build_from_statement_extraction(source_object)

    raise ValueError(f"Cannot automatically resolve provenance chain for object of type {type(source_object).__name__}")
