"""Model registry loaded from configs/models.yaml."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

# Environment variable that must be set for each hosted provider.
PROVIDER_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "nvidia_nim": "NVIDIA_NIM_API_KEY",
}


class ModelSpec(BaseModel):
    alias: str
    model: str  # LiteLLM model string
    provider: str
    rpm: int = 0

    @property
    def api_base(self) -> str | None:
        if self.provider == "ollama":
            return os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        return None

    def missing_key(self) -> str | None:
        """Name of the required environment variable if it is unset, else None."""
        key = PROVIDER_KEYS.get(self.provider)
        if key and not os.environ.get(key):
            return key
        return None


class ModelRegistry:
    def __init__(self, specs: dict[str, ModelSpec]):
        self._specs = specs

    @classmethod
    def from_yaml(cls, path: Path) -> "ModelRegistry":
        raw = yaml.safe_load(path.read_text())["models"]
        return cls({alias: ModelSpec(alias=alias, **cfg) for alias, cfg in raw.items()})

    def get(self, alias: str) -> ModelSpec:
        try:
            return self._specs[alias]
        except KeyError:
            raise KeyError(f"Unknown model alias {alias!r}; see configs/models.yaml") from None

    def all(self) -> list[ModelSpec]:
        return list(self._specs.values())
