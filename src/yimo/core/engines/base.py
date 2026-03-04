from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from openai import AsyncOpenAI

from yimo.models.config import AppConfig, ProviderConfig


@dataclass(frozen=True)
class EngineContext:
    get_config: Callable[[], AppConfig]
    get_provider: Callable[[], ProviderConfig]
    get_openai_client: Callable[[], AsyncOpenAI]
    acquire_rate_limit: Callable[[], Awaitable[None]]


class TranslationEngine(Protocol):
    async def translate_markdown(
        self,
        content: str,
        *,
        source_lang: str,
        target_lang: str,
        system_prompt: str,
        stop_flag: threading.Event | None,
    ) -> str: ...

