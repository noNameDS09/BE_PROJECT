"""Distress indicators from reported numbers: Altman Z'' plus 8-K risk-event counts.

Z'' (Altman 1995, for non-manufacturers and firms without a market price) uses book
values only, so it needs no share prices:
    Z'' = 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4
    X1 = working capital / total assets       X2 = retained earnings / total assets
    X3 = EBIT / total assets                  X4 = book equity / total liabilities
Zones: > 2.60 safe, 1.10-2.60 grey, < 1.10 distress. Not meaningful for banks and
insurers, whose balance sheets don't fit the model; those are reported as not applicable.
"""

from pydantic import BaseModel

from loupe.tools.facts import FactResult, FactsStore

NOT_APPLICABLE_SECTORS = {"Financials"}
COEF = {"x1": 6.56, "x2": 3.26, "x3": 6.72, "x4": 1.05}


class DistressResult(BaseModel):
    company_id: str
    fiscal_year: int
    z_score: float | None
    zone: str | None
    components: dict[str, float]
    inputs: list[FactResult]
    missing: list[str]
    note: str = ""


def zone(z: float) -> str:
    return "safe" if z > 2.6 else "grey" if z >= 1.1 else "distress"


def altman_z2(
    facts: FactsStore, company_id: str, fiscal_year: int, sector: str | None
) -> DistressResult:
    if sector in NOT_APPLICABLE_SECTORS:
        return DistressResult(
            company_id=company_id, fiscal_year=fiscal_year, z_score=None, zone=None,
            components={}, inputs=[], missing=[],
            note="Altman Z'' is not meaningful for banks and insurers.",
        )  # fmt: skip
    names = [
        "current_assets", "current_liabilities", "total_assets", "retained_earnings",
        "total_liabilities", "equity",
    ]  # fmt: skip
    got = {n: facts.get(company_id, n, fiscal_year) for n in names}
    ebit = facts.get(company_id, "operating_income", fiscal_year)
    if ebit is None:  # fall back to pre-tax income + interest expense
        pre, interest = (
            facts.get(company_id, m, fiscal_year) for m in ("pretax_income", "interest_expense")
        )
        if pre is not None:
            got["pretax_income"], got["interest_expense"] = pre, interest
        else:  # neither EBIT nor pre-tax income is reported: say so instead of failing
            got["operating_income"] = None
    else:
        got["operating_income"] = ebit
    missing = [n for n, v in got.items() if v is None and n != "interest_expense"]
    inputs = [v for v in got.values() if v is not None]
    if missing:
        return DistressResult(
            company_id=company_id, fiscal_year=fiscal_year, z_score=None, zone=None,
            components={}, inputs=inputs, missing=missing,
        )  # fmt: skip
    ta = got["total_assets"].value
    tl = got["total_liabilities"].value
    if "operating_income" in got:
        ebit_v = got["operating_income"].value
    else:
        ebit_v = got["pretax_income"].value + (
            got["interest_expense"].value if got.get("interest_expense") else 0
        )
    comps = {
        "x1": (got["current_assets"].value - got["current_liabilities"].value) / ta,
        "x2": got["retained_earnings"].value / ta,
        "x3": ebit_v / ta,
        "x4": got["equity"].value / tl,
    }
    z = sum(COEF[k] * v for k, v in comps.items())
    return DistressResult(
        company_id=company_id, fiscal_year=fiscal_year, z_score=round(z, 3), zone=zone(z),
        components={k: round(v, 4) for k, v in comps.items()}, inputs=inputs, missing=[],
    )  # fmt: skip
