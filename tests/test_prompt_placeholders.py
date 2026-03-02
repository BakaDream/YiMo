import unittest

from yimo.core.translator import render_system_prompt


class TestPromptPlaceholders(unittest.TestCase):
    def test_replaces_placeholders(self):
        template = "from {current_language} to {target_language}"
        self.assertEqual(render_system_prompt(template, "English", "简体中文"), "from English to 简体中文")
        self.assertEqual(render_system_prompt(template, "auto", "简体中文"), "from auto to 简体中文")
        self.assertEqual(render_system_prompt(template, "French", "English"), "from French to English")

    def test_no_placeholders(self):
        template = "no placeholders here"
        self.assertEqual(render_system_prompt(template, "English", "简体中文"), template)

    def test_does_not_touch_other_braces(self):
        template = "keep {foo} but replace {current_language} -> {target_language}"
        out = render_system_prompt(template, "English", "简体中文")
        self.assertIn("{foo}", out)
        self.assertIn("English", out)
        self.assertIn("简体中文", out)

    def test_strips_and_falls_back_defaults(self):
        template = "from {current_language} to {target_language}"
        self.assertEqual(render_system_prompt(template, "  ", "  "), "from English to 简体中文")


if __name__ == "__main__":
    unittest.main()

