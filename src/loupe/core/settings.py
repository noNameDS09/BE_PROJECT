"""Project settings, read from the environment and `.env`."""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sec_user_agent: str | None = None
    data_dir: Path = Path("data")
    models_config: Path = Path("configs/models.yaml")
    companies_config: Path = Path("configs/companies_us.yaml")

    # Corpus window, docs/PLAN.md D4. Benchmark items may need older filings,
    # which are fetched on demand rather than by widening this window.
    corpus_start: str = "2023-01-01"
    corpus_end: str = "2025-12-31"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "loupe.duckdb"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.cache_dir,
            self.logs_dir,
            self.raw_dir,
            self.processed_dir,
            self.index_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    # LiteLLM reads provider keys from os.environ, so export .env there too.
    load_dotenv()
    return Settings()
