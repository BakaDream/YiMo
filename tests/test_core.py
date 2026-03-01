import unittest
from pathlib import Path
from mkdocs_translate.utils.file_utils import is_excluded, classify_file
from mkdocs_translate.models.config import AppConfig

class TestFileUtils(unittest.TestCase):
    def test_is_excluded(self):
        self.assertTrue(is_excluded(Path(".git/config")))
        self.assertTrue(is_excluded(Path("src/__pycache__/file.pyc")))
        self.assertFalse(is_excluded(Path("src/main.py")))

    def test_classify_file(self):
        self.assertEqual(classify_file(Path("doc.md")), "translate")
        self.assertEqual(classify_file(Path("image.png")), "resource")
        self.assertEqual(classify_file(Path("unknown.xyz")), "ignore")

class TestConfig(unittest.TestCase):
    def test_config_defaults(self):
        config = AppConfig()
        self.assertEqual(config.get_active_provider().model, "gpt-4o")
        self.assertEqual(config.get_active_provider().rpm_limit, 60)
        self.assertEqual(config.max_concurrency, 3)

if __name__ == "__main__":
    unittest.main()
