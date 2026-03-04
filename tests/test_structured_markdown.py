import asyncio
import json
import unittest

from yimo.core.engines.base import EngineContext
from yimo.core.engines.structured_graph import StructuredGraphEngine
from yimo.core.markdown.segmenter import PLACEHOLDER_RE, segment_document, unmask_text
from yimo.models.config import AppConfig, ProviderConfig


class _DummyMsg:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    """
    A minimal async LLM stub that:
      - first returns malformed/mismatched ids
      - then returns correct JSON when repair instructions exist
    """

    async def ainvoke(self, messages):
        payload = messages[-1].content
        data = json.loads(payload)
        items = data["items"]
        repair = data.get("rules", {}).get("repair")

        if not repair:
            # Trigger repair: drop one id
            translations = [{"id": items[0]["id"], "text": items[0]["text"]}]
        else:
            translations = [{"id": it["id"], "text": it["text"]} for it in items]

        out = {
            "translations": translations,
            "memory": {"summary": "s", "glossary": [{"source": "A", "target": "B"}]},
        }
        return _DummyMsg(json.dumps(out, ensure_ascii=False))


async def _no_rate_limit():
    return None


class TestStructuredMarkdown(unittest.TestCase):
    def test_no_front_matter(self):
        cfg = AppConfig()
        doc = segment_document("# T\n\nHi\n", cfg)
        self.assertIsNone(doc.front_matter)

    def test_front_matter_selected_keys_only(self):
        cfg = AppConfig(
            front_matter_translate_keys=["title", "tags", "slug"],
            front_matter_custom_keys="seo.title",
        )
        content = (
            "---\n"
            "title: Hello\n"
            "tags: [foo, bar]\n"
            "slug: keep-me\n"
            "seo:\n"
            "  title: Hello SEO\n"
            "---\n"
            "\n"
            "Body\n"
        )
        doc = segment_document(content, cfg)
        fm_ids = [it.id for it in doc.translatable_items if it.source == "front_matter"]
        self.assertTrue(any(i.startswith("fm") for i in fm_ids))
        # slug is denylisted by default -> should not become a target
        self.assertNotIn("slug", [str(t.path[-1]).lower() for t in doc.front_matter_targets if t.path])

    def test_mask_unmask_roundtrip(self):
        cfg = AppConfig()
        content = "Text `code` <span>x</span> [link](https://a) ![alt](img.png) https://b\n"
        doc = segment_document(content, cfg)
        segs = [s for s in doc.body_segments if s.translatable_id]
        self.assertEqual(len(segs), 1)
        seg = segs[0]
        self.assertIsNotNone(seg.template)
        restored = unmask_text(seg.template or "", seg.placeholders)
        self.assertEqual(restored, seg.raw)

    def test_code_block_preserved(self):
        cfg = AppConfig()
        content = "Intro\n\n```python\nprint('hi')\n```\n\nOutro\n"
        doc = segment_document(content, cfg)
        body_roundtrip = "".join(s.raw for s in doc.body_segments)
        self.assertEqual(body_roundtrip, doc.body_text)
        code = [s for s in doc.body_segments if s.kind == "code_block"]
        self.assertEqual(len(code), 1)
        self.assertIn("print('hi')", code[0].raw)
        for it in doc.translatable_items:
            self.assertNotIn("print('hi')", it.text)

    def test_validate_repair_loop(self):
        cfg = AppConfig(structured_max_repair_attempts=2, structured_chunk_tokens=80)
        provider = ProviderConfig(name="p", api_key="k", base_url="http://x", model="m", rpm_limit=0)

        ctx = EngineContext(
            get_config=lambda: cfg,
            get_provider=lambda: provider,
            get_openai_client=lambda: (_ for _ in ()).throw(RuntimeError("should not be called")),
            acquire_rate_limit=_no_rate_limit,
        )
        engine = StructuredGraphEngine(ctx, llm=_FakeLLM())

        # Avoid requiring langchain-core messages in unit tests
        engine._build_messages = lambda **kw: (_DummyMsg("sys"), _DummyMsg(kw["payload"]))  # type: ignore[attr-defined]

        out = asyncio.run(
            engine.translate_markdown(
                "Hello `x`.\n",
                source_lang="English",
                target_lang="简体中文",
                system_prompt="sp",
                stop_flag=None,
            )
        )
        self.assertIsInstance(out, str)
        self.assertEqual(PLACEHOLDER_RE.findall(out), [])


if __name__ == "__main__":
    unittest.main()
