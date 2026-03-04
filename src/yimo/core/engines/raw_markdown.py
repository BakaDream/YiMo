from __future__ import annotations

import asyncio
import threading

from yimo.core.engines.base import EngineContext


class RawMarkdownEngine:
    def __init__(self, ctx: EngineContext) -> None:
        self._ctx = ctx

    async def translate_markdown(
        self,
        content: str,
        *,
        source_lang: str,
        target_lang: str,
        system_prompt: str,
        stop_flag: threading.Event | None,
    ) -> str:
        if stop_flag is not None and stop_flag.is_set():
            raise asyncio.CancelledError()

        if not content.strip():
            return ""

        await self._ctx.acquire_rate_limit()

        config = self._ctx.get_config()
        provider = self._ctx.get_provider()
        response = await self._ctx.get_openai_client().chat.completions.create(
            model=provider.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=config.temperature,
        )
        return response.choices[0].message.content or ""
