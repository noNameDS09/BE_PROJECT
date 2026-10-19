"""The 25-company US universe as the dataset code needs it: ticker, names, sector, split."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPANIES_CONFIG = REPO_ROOT / "configs" / "companies_us.yaml"
METRICS_CONFIG = REPO_ROOT / "configs" / "metrics.yaml"

# Short names people actually use (configs hold SEC's conformed names, e.g. "PEPSICO INC").
DISPLAY_NAMES = {
    "PEP": "PepsiCo",
    "AMCR": "Amcor",
    "JNJ": "Johnson & Johnson",
    "MMM": "3M",
    "AMD": "AMD",
    "BBY": "Best Buy",
    "BA": "Boeing",
    "AXP": "American Express",
    "MGM": "MGM Resorts",
    "PFE": "Pfizer",
    "ULTA": "Ulta Beauty",
    "ADBE": "Adobe",
    "JPM": "JPMorgan Chase",
    "VZ": "Verizon",
    "CVS": "CVS Health",
    "ADM": "Archer-Daniels-Midland",
    "UNH": "UnitedHealth Group",
    "DBD": "Diebold Nixdorf",
    "SHAK": "Shake Shack",
    "SAH": "Sonic Automotive",
    "ECHO": "EchoStar",
    "KR": "Kroger",
    "RIG": "Transocean",
    "CMP": "Compass Minerals",
    "BFH": "Bread Financial",
}


class UniverseCompany(BaseModel):
    id: str
    name: str
    cik: str
    sector: str
    group: str
    split: str
    fiscal_year_end: str | None = None

    @property
    def display(self) -> str:
        return DISPLAY_NAMES.get(self.id, self.name)


@lru_cache
def load_universe(path: Path = COMPANIES_CONFIG) -> dict[str, UniverseCompany]:
    rows = yaml.safe_load(path.read_text())["companies"] or []
    fields = UniverseCompany.model_fields
    return {r["id"]: UniverseCompany(**{k: v for k, v in r.items() if k in fields}) for r in rows}


def company_split(ticker: str) -> str | None:
    company = load_universe().get(ticker)
    return company.split if company else None
