import asyncio
import unittest

from yimo.core.translator import Translator, render_system_prompt
from yimo.models.config import AppConfig
from yimo.utils.constants import DEFAULT_RAW_SYSTEM_PROMPT, DEFAULT_STRUCTURED_SYSTEM_PROMPT


class TestTranslatorPromptSelection(unittest.TestCase):
    def test_uses_raw_prompt_in_raw_mode(self):
        config = AppConfig()
        config.translation_mode = "raw_markdown"
        config.source_language = "English"
        config.target_language = "简体中文"
        config.raw_system_prompt = "RAW {current_language}->{target_language}"
        config.structured_system_prompt = "STRUCT {current_language}->{target_language}"

        t = Translator(config)
        captured: dict[str, str] = {}

        async def fake_raw(content: str, *, source_lang: str, target_lang: str, system_prompt: str, stop_flag):
            captured["system_prompt"] = system_prompt
            return "ok"

        t._raw_engine.translate_markdown = fake_raw  # type: ignore[assignment]

        asyncio.run(t.translate_markdown("hello"))
        self.assertEqual(captured.get("system_prompt"), "RAW English->简体中文")

    def test_uses_structured_prompt_in_structured_mode(self):
        config = AppConfig()
        config.translation_mode = "structured_graph"
        config.source_language = "English"
        config.target_language = "简体中文"
        config.raw_system_prompt = "RAW {current_language}->{target_language}"
        config.structured_system_prompt = "STRUCT {current_language}->{target_language}"

        t = Translator(config)
        captured: dict[str, str] = {}

        async def fake_structured(content: str, *, source_lang: str, target_lang: str, system_prompt: str, stop_flag):
            captured["system_prompt"] = system_prompt
            return "ok"

        t._structured_engine.translate_markdown = fake_structured  # type: ignore[assignment]

        asyncio.run(t.translate_markdown("hello"))
        self.assertEqual(captured.get("system_prompt"), "STRUCT English->简体中文")

    def test_blank_prompt_falls_back_to_default(self):
        config = AppConfig()
        config.translation_mode = "raw_markdown"
        config.source_language = "English"
        config.target_language = "简体中文"
        config.raw_system_prompt = "   "

        t = Translator(config)
        captured: dict[str, str] = {}

        async def fake_raw(content: str, *, source_lang: str, target_lang: str, system_prompt: str, stop_flag):
            captured["system_prompt"] = system_prompt
            return "ok"

        t._raw_engine.translate_markdown = fake_raw  # type: ignore[assignment]

        asyncio.run(t.translate_markdown("hello"))
        expected = render_system_prompt(DEFAULT_RAW_SYSTEM_PROMPT, "English", "简体中文")
        self.assertEqual(captured.get("system_prompt"), expected)

    def test_blank_structured_prompt_falls_back_to_default(self):
        config = AppConfig()
        config.translation_mode = "structured_graph"
        config.source_language = "English"
        config.target_language = "简体中文"
        config.structured_system_prompt = "\n\n"

        t = Translator(config)
        captured: dict[str, str] = {}

        async def fake_structured(content: str, *, source_lang: str, target_lang: str, system_prompt: str, stop_flag):
            captured["system_prompt"] = system_prompt
            return "ok"

        t._structured_engine.translate_markdown = fake_structured  # type: ignore[assignment]

        asyncio.run(t.translate_markdown("hello"))
        expected = render_system_prompt(DEFAULT_STRUCTURED_SYSTEM_PROMPT, "English", "简体中文")
        self.assertEqual(captured.get("system_prompt"), expected)


if __name__ == "__main__":
    unittest.main()

