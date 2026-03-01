import unittest

from yimo.i18n.manager import I18nManager
from yimo.models.config import AppConfig


class TestI18nManager(unittest.TestCase):
    def test_language_resolution_from_system_when_missing(self):
        config = AppConfig()
        config.ui_language = None

        i18n = I18nManager()
        i18n.set_from_config(config, system_locale="zh_CN")
        self.assertEqual(i18n.language, "zh_CN")

        i18n.set_from_config(config, system_locale="en_US")
        self.assertEqual(i18n.language, "en")

        i18n.set_from_config(config, system_locale="zh_TW")
        self.assertEqual(i18n.language, "en")

    def test_language_resolution_config_overrides_system(self):
        config = AppConfig(ui_language="zh_CN")
        i18n = I18nManager()
        i18n.set_from_config(config, system_locale="en_US")
        self.assertEqual(i18n.language, "zh_CN")

    def test_invalid_config_language_falls_back_to_english(self):
        config = AppConfig(ui_language="xx")
        i18n = I18nManager()
        i18n.set_from_config(config, system_locale="zh_CN")
        self.assertEqual(i18n.language, "zh_CN")

        i18n.set_from_config(config, system_locale="fr_FR")
        self.assertEqual(i18n.language, "en")

    def test_translation_fallback(self):
        i18n = I18nManager(language="xx")  # Invalid language => fallback to English table
        self.assertEqual(i18n.t("main.stop"), "Stop")
        self.assertEqual(i18n.t("this.key.does.not.exist"), "this.key.does.not.exist")

    def test_formatting(self):
        i18n = I18nManager(language="en")
        self.assertEqual(i18n.t("main.status.found_files", count=3), "Found 3 files to process")


if __name__ == "__main__":
    unittest.main()
