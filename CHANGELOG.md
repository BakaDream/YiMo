# Changelog

All notable changes to this project will be documented in this file.

## v0.1.0

Initial public release.

- PySide6 GUI app for batch translating documentation while preserving directory structure.
- OpenAI-compatible providers (base_url/api_key/model) configurable in GUI.
- Task list with concurrency, retry, and stop.
- Project progress save/load (YAML).
- UI i18n (English / 简体中文) and a light QSS theme.
- Translation language selector (source/target) + system prompt placeholders `{current_language}` / `{target_language}`.
- Multi-platform binaries with PyInstaller and Nuitka (Windows/Linux/macOS arm64).

