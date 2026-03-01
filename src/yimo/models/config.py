from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from yimo.utils.constants import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_MODEL,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RPM_LIMIT,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_TEMPERATURE,
)
from yimo.utils.yaml_utils import dump_yaml, load_yaml


DEFAULT_CONFIG_FILENAME = "mkdocs-translate.yaml"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., description="Provider name (unique)")
    base_url: str = Field(default="https://api.openai.com/v1", description="OpenAI-compatible Base URL")
    api_key: str = Field(default="", description="API key for this provider")
    model: str = Field(default=DEFAULT_MODEL, description="Model name to use on this provider")
    rpm_limit: int = Field(default=DEFAULT_RPM_LIMIT, description="Requests per minute; <= 0 means unlimited")


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    active_provider: str = Field(default="default", description="Active provider name")
    providers: List[ProviderConfig] = Field(
        default_factory=lambda: [
            ProviderConfig(
                name="default",
                base_url="https://api.openai.com/v1",
                api_key="",
                model=DEFAULT_MODEL,
                rpm_limit=DEFAULT_RPM_LIMIT,
            )
        ]
    )

    max_concurrency: int = Field(default=DEFAULT_MAX_CONCURRENCY, description="Max concurrent translation tasks")
    max_retries: int = Field(default=3, description="Max retries for failed tasks")
    temperature: float = Field(default=DEFAULT_TEMPERATURE, description="Temperature for LLM sampling")
    request_timeout: int = Field(default=DEFAULT_REQUEST_TIMEOUT, description="Request timeout in seconds")
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT, description="System prompt for translation")

    @classmethod
    def default_path(cls) -> Path:
        return Path(DEFAULT_CONFIG_FILENAME)

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        config_path = Path(path) if path is not None else cls.default_path()
        if not config_path.exists():
            return cls()
        data = load_yaml(config_path)
        if not data:
            return cls()
        return cls.model_validate(data)

    def save(self, path: Path | None = None) -> None:
        config_path = Path(path) if path is not None else self.default_path()
        dump_yaml(config_path, self.model_dump(mode="json"))

    def get_active_provider(self) -> ProviderConfig:
        if not self.providers:
            return ProviderConfig(name="default")
        for provider in self.providers:
            if provider.name == self.active_provider:
                return provider
        return self.providers[0]
