import unittest

from yimo.core.markdown.segmenter import segment_document
from yimo.models.config import AppConfig


class TestMarkdownExtensionBlocks(unittest.TestCase):
    def test_mkdocs_admonition_marker_raw_but_content_translatable(self):
        cfg = AppConfig()
        content = "!!! note\n" "    This should be translated.\n" "\n" "After.\n"
        doc = segment_document(content, cfg)

        kinds = [s.kind for s in doc.body_segments]
        self.assertIn("admonition_marker", kinds)

        body_texts = [it.text for it in doc.translatable_items if it.source == "body"]
        joined = "\n".join(body_texts)
        self.assertIn("This should be translated.", joined)
        self.assertNotIn("!!! note", joined)

    def test_vuepress_container_marker_raw_but_content_translatable(self):
        cfg = AppConfig()
        content = "::: tip\n" "Content should be translated.\n" ":::\n"
        doc = segment_document(content, cfg)

        kinds = [s.kind for s in doc.body_segments]
        self.assertIn("container_marker", kinds)

        body_texts = [it.text for it in doc.translatable_items if it.source == "body"]
        joined = "\n".join(body_texts)
        self.assertIn("Content should be translated.", joined)
        self.assertNotIn(":::", joined)


if __name__ == "__main__":
    unittest.main()

