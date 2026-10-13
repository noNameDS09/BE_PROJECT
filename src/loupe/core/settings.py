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

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"


@lru_cache
def get_settings() -> Settings:
    # LiteLLM reads provider keys from os.environ, so export .env there too.
    load_dotenv()
    return Settings()
