import unittest

from yimo.core.markdown.segmenter import apply_front_matter_targets, segment_document
from yimo.models.config import AppConfig


class TestFrontMatterToml(unittest.TestCase):
    def test_toml_front_matter_parsed_and_written(self):
        cfg = AppConfig(front_matter_translate_keys=["title"])
        content = "+++\n" 'title = "Hello"\n' "+++\n" "\n" "Body\n"
        doc = segment_document(content, cfg)

        self.assertIsNotNone(doc.front_matter)
        self.assertEqual(doc.front_matter.delimiter, "+++")
        self.assertEqual(doc.front_matter.format, "toml")
        self.assertTrue(doc.front_matter_targets)

        target = doc.front_matter_targets[0]
        fm_text, data = apply_front_matter_targets(
            doc.front_matter,
            {target.id: "Hola"},
            doc.front_matter_targets,
        )
        self.assertTrue(fm_text.startswith("+++\n"))
        self.assertIn('title = "Hola"', fm_text)
        self.assertEqual(data.get("title"), "Hola")


if __name__ == "__main__":
    unittest.main()

