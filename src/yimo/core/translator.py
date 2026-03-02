import asyncio
from openai import AsyncOpenAI
from yimo.models.config import AppConfig


def render_system_prompt(template: str, source_language: str, target_language: str) -> str:
    source = (source_language or "").strip() or "English"
    target = (target_language or "").strip() or "简体中文"
    return template.replace("{current_language}", source).replace("{target_language}", target)


class Translator:
    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None

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

    async def translate_markdown(self, content: str) -> str:
        """
        Translate Markdown content using OpenAI API.
        """
        if not content.strip():
            return ""

        # Use system prompt from config, or fallback if empty (though config has default)
        system_prompt = render_system_prompt(
            self.config.system_prompt,
            getattr(self.config, "source_language", "English"),
            getattr(self.config, "target_language", "简体中文"),
        )
        
        try:
            provider = self.config.get_active_provider()
            response = await self.client.chat.completions.create(
                model=provider.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=self.config.temperature
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            # Re-raise to be handled by the caller/task manager
            raise Exception(f"Translation API error: {str(e)}")

    async def validate_api_key(self) -> bool:
        """Simple check to validate API key."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
