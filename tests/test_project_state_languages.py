import unittest
from pathlib import Path

from yimo.models.task import ProjectState, TranslationTask


class TestProjectStateLanguages(unittest.TestCase):
    def test_dump_includes_languages(self):
        project = ProjectState(
            source_dir=Path("src"),
            dest_dir=Path("out"),
            tasks=[],
            source_language="auto",
            target_language="简体中文",
        )
        data = project.model_dump(mode="json")
        self.assertEqual(data["source_language"], "auto")
        self.assertEqual(data["target_language"], "简体中文")

    def test_old_data_missing_languages_is_compatible(self):
        old = {
            "source_dir": "src",
            "dest_dir": "out",
            "tasks": [
                {
                    "source_path": "a.md",
                    "dest_path": "b.md",
                    "status": "pending",
                    "error_message": None,
                    "is_resource": False,
                    "retries": 0,
                }
            ],
        }
        project = ProjectState.model_validate(old)
        self.assertEqual(project.source_language, "English")
        self.assertEqual(project.target_language, "简体中文")
        self.assertEqual(len(project.tasks), 1)
        self.assertIsInstance(project.tasks[0], TranslationTask)


if __name__ == "__main__":
    unittest.main()

