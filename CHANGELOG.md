# Changelog

All notable changes to this project will be documented in this file.

## v0.2.0

### Breaking / Changed

- Config: split `system_prompt` into `raw_system_prompt` and `structured_system_prompt`.
  - Old `system_prompt` will be ignored (falls back to defaults).
- `structured_graph` now requires LangGraph at runtime (no fallback execution path).

### Added / Improved

- New `structured_graph` engine:
  - Runs on LangGraph.
  - Uses LangChain `with_structured_output()` for structured parsing (still keeps business validation + repair retries).
- Markdown pipeline improvements:
  - Better segmentation / placeholder protection.
  - Better Front Matter translation support (configurable keys).
- Settings UI improvements:
  - Providers management embedded in Settings.
  - New advanced options (e.g. translate link text / image alt, code-like line heuristics).
- Structured translation defaults tuned for larger documents (`structured_chunk_tokens`, `structured_memory_max_tokens`, `structured_max_repair_attempts`).

### Fixed

- Output path defaults to `*-translate*` on source selection; re-selecting source overwrites output path consistently.

## v0.1.0

Initial public release.

- PySide6 GUI app for batch translating documentation while preserving directory structure.
- OpenAI-compatible providers (base_url/api_key/model) configurable in GUI.
- Task list with concurrency, retry, and stop.
- Project progress save/load (YAML).
- UI i18n (English / 简体中文) and a light QSS theme.
- Translation language selector (source/target) + system prompt placeholders `{current_language}` / `{target_language}`.
- Multi-platform binaries with PyInstaller and Nuitka (Windows/Linux/macOS arm64).
