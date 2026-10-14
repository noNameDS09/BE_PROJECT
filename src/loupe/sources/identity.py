"""The 25-company US universe, and the CIK identity table.

`configs/companies_us.yaml` is the human-edited source of truth for *which*
companies we study. CIKs are resolved live from SEC's `company_tickers.json`
rather than trusted from the file, because a wrong CIK silently attaches
another company's filings to our corpus. The resolution is cached in
`data/processed/identities.json` so a run is reproducible offline.

docs/PLAN.md D3 fixes the selection rule: ~15 FinanceBench companies still
filing, plus ~10 found by scanning FY2023-25 8-Ks for risk items.
"""

import json
from functools import lru_cache
from pathlib import Path

import httpx
import yaml
from pydantic import ValidationError

from loupe.core.schemas import Company, CompanyInfo

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# SEC returns HTTP 403 to a User-Agent without a contact address.
DEFAULT_USER_AGENT = "Loupe research project (set SEC_USER_AGENT in .env)"


class UniverseError(RuntimeError):
    """Raised when the configured universe cannot be resolved."""


def load_config(path: Path) -> dict:
    """Read the universe config, refusing one with nothing selectable.

    A present-but-empty `companies:` is the common case during setup, and
    silently returning no companies would look like "coverage 0/0, all fine".
    """
    raw = yaml.safe_load(path.read_text()) or {}
    selectable = (
        raw.get("companies") or raw.get("financebench_candidates") or raw.get("event_candidates")
    )
    if not selectable:
        raise UniverseError(
            f"{path} lists no companies. Add entries to "
            "`financebench_candidates:` or `companies:` before ingesting."
        )
    return raw


def candidate_tickers(path: Path) -> list[tuple[str, str]]:
    """Every ticker in the config as (ticker, source), FinanceBench first.

    Entries may be plain tickers or `{ticker, cik, name}` maps.
    """
    raw = load_config(path)
    out: list[tuple[str, str]] = []
    for key, source in (
        ("financebench_candidates", "financebench"),
        ("event_candidates", "event_scan"),
    ):
        for entry in raw.get(key) or []:
            if isinstance(entry, str):
                out.append((entry.upper(), source))
            elif isinstance(entry, dict) and entry.get("ticker"):
                out.append((str(entry["ticker"]).upper(), source))
    return out


def configured_ciks(path: Path) -> dict[str, str]:
    """ticker -> CIK as written in the config, for cross-checking."""
    raw = load_config(path)
    out: dict[str, str] = {}
    for key in ("financebench_candidates", "event_candidates", "companies"):
        for entry in raw.get(key) or []:
            if isinstance(entry, dict) and entry.get("ticker") and entry.get("cik"):
                out[str(entry["ticker"]).upper()] = str(entry["cik"]).zfill(10)
    return out


def fetch_ticker_map(
    user_agent: str | None,
    cache_path: Path | None = None,
    timeout: float = 30.0,
) -> dict[str, dict]:
    """ticker -> {cik, title}. Cached on disk because it is a single 10k-row file."""
    if cache_path and cache_path.exists():
        return json.loads(cache_path.read_text())

    headers = {"User-Agent": user_agent or DEFAULT_USER_AGENT}
    response = httpx.get(TICKERS_URL, headers=headers, timeout=timeout)
    response.raise_for_status()

    table: dict[str, dict] = {}
    for row in response.json().values():
        table[str(row["ticker"]).upper()] = {
            "cik": str(row["cik_str"]).zfill(10),
            "title": row["title"],
        }
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(table, indent=0, sort_keys=True))
    return table


@lru_cache
def _identity_cache_path(data_dir: str) -> Path:
    return Path(data_dir) / "processed" / "identities.json"


def resolve_universe(
    config_path: Path,
    user_agent: str | None = None,
    cache_path: Path | None = None,
) -> list[CompanyInfo]:
    """Resolve every configured ticker to a CIK, failing loudly on any mismatch.

    A missing ticker, or a CIK that disagrees with the one written in the
    config, is an error: silently ingesting the wrong company would make every
    citation in the benchmark wrong, and it would not look wrong.
    """
    ticker_map = fetch_ticker_map(user_agent, cache_path)
    configured = yaml.safe_load(config_path.read_text()) or {}
    declared = configured_ciks(config_path)
    frozen = {
        str(c["ticker"]).upper(): c
        for c in configured.get("companies") or []
        if isinstance(c, dict) and c.get("ticker")
    }

    resolved: list[CompanyInfo] = []
    missing: list[str] = []
    mismatched: list[str] = []
    for ticker, source in candidate_tickers(config_path):
        row = ticker_map.get(ticker)
        if row is None:
            missing.append(ticker)
            continue
        if ticker in declared and declared[ticker] != row["cik"]:
            mismatched.append(f"{ticker}: config {declared[ticker]} vs SEC {row['cik']}")
            continue
        entry = frozen.get(ticker) or {}
        try:
            resolved.append(
                CompanyInfo(
                    ticker=ticker,
                    name=row["title"],
                    cik=row["cik"],
                    sector=entry.get("sector"),
                    split=entry.get("split"),
                    source="frozen" if ticker in frozen else source,
                )
            )
        except ValidationError as exc:  # pragma: no cover - defensive
            raise UniverseError(f"{ticker}: {exc}") from exc

    if missing:
        raise UniverseError(
            f"tickers not found in SEC's file: {', '.join(sorted(missing))}. "
            "Remove them from configs/companies_us.yaml or fix the spelling."
        )
    if mismatched:
        raise UniverseError(
            "CIK mismatch against SEC's live file: " + "; ".join(sorted(mismatched))
        )
    return resolved


def to_companies(infos: list[CompanyInfo]) -> list[Company]:
    return [
        Company(
            id=i.ticker, name=i.name, country=i.country, cik=i.cik, sector=i.sector, split=i.split
        )
        for i in infos
    ]
