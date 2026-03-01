from __future__ import annotations

from dataclasses import dataclass

from yimo.i18n.locales.en import STRINGS as EN_STRINGS
from yimo.i18n.locales.zh_CN import STRINGS as ZH_CN_STRINGS
from yimo.models.config import AppConfig


_LOCALES: dict[str, dict[str, str]] = {
    "en": EN_STRINGS,
    "zh_CN": ZH_CN_STRINGS,
}


def _system_locale_to_language(system_locale: str) -> str:
    # Only zh_CN is supported for Chinese. Anything else falls back to English.
    return "zh_CN" if system_locale == "zh_CN" else "en"


@dataclass
class I18nManager:
    language: str = "en"

    @property
    def supported(self) -> set[str]:
        return set(_LOCALES.keys())

    def set_language(self, lang: str) -> None:
        self.language = lang if lang in _LOCALES else "en"

    def set_from_config(self, config: AppConfig, system_locale: str) -> None:
        configured = (config.ui_language or "").strip()
        if configured in _LOCALES:
            self.language = configured
            return
        self.language = _system_locale_to_language(system_locale)

    def t(self, key: str, **kwargs) -> str:
        text = _LOCALES.get(self.language, {}).get(key)
        if text is None:
            text = EN_STRINGS.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

