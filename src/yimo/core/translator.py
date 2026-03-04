import asyncio
from openai import AsyncOpenAI
from yimo.models.config import AppConfig
from yimo.utils.rate_limiter import RateLimiter

from yimo.utils.constants import DEFAULT_RAW_SYSTEM_PROMPT, DEFAULT_STRUCTURED_SYSTEM_PROMPT
from yimo.core.engines.base import EngineContext
from yimo.core.engines.raw_markdown import RawMarkdownEngine
from yimo.core.engines.structured_graph import StructuredGraphEngine


def render_system_prompt(template: str, source_language: str, target_language: str) -> str:
    source = (source_language or "").strip() or "English"
    target = (target_language or "").strip() or "简体中文"
    return template.replace("{current_language}", source).replace("{target_language}", target)


class Translator:
    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None
        self._rate_limiter = RateLimiter(config.get_active_provider().rpm_limit)

        self._ctx = EngineContext(
            get_config=lambda: self.config,
            get_provider=lambda: self.config.get_active_provider(),
            get_openai_client=lambda: self.client,
            acquire_rate_limit=self._acquire_rate_limit,
        )
        self._raw_engine = RawMarkdownEngine(self._ctx)
        self._structured_engine = StructuredGraphEngine(self._ctx)

    @property
    def client(self):
        if self._client is None:
            provider = self.config.get_active_provider()
            self._client = AsyncOpenAI(
                api_key=provider.api_key,
                base_url=provider.base_url,
                timeout=float(self.config.request_timeout),
            )
        return self._client

    def update_config(self, config: AppConfig):
        """Update configuration and reset client."""
        self.config = config
        self._client = None
        self._rate_limiter.update_limit(config.get_active_provider().rpm_limit)

    async def _acquire_rate_limit(self) -> None:
        await self._rate_limiter.acquire()

    async def translate_markdown(self, content: str, *, stop_flag=None) -> str:
        if not content.strip():
            return ""

        source_lang = getattr(self.config, "source_language", "English")
        target_lang = getattr(self.config, "target_language", "简体中文")

        mode = getattr(self.config, "translation_mode", "raw_markdown") or "raw_markdown"

        if mode == "structured_graph":
            template = getattr(self.config, "structured_system_prompt", "") or ""
            if not template.strip():
                template = DEFAULT_STRUCTURED_SYSTEM_PROMPT
        else:
            template = getattr(self.config, "raw_system_prompt", "") or ""
            if not template.strip():
                template = DEFAULT_RAW_SYSTEM_PROMPT

        system_prompt = render_system_prompt(template, source_lang, target_lang)
        try:
            if mode == "structured_graph":
                return await self._structured_engine.translate_markdown(
                    content,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    system_prompt=system_prompt,
                    stop_flag=stop_flag,
                )
            return await self._raw_engine.translate_markdown(
                content,
                source_lang=source_lang,
                target_lang=target_lang,
                system_prompt=system_prompt,
                stop_flag=stop_flag,
            )
        except Exception as e:
            raise Exception(f"Translation API error: {str(e)}")

    async def validate_api_key(self) -> bool:
        """Simple check to validate API key."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
