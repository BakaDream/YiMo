# YiMo

<div align="center">
  <img src="src/yimo/icons/none-background.svg" width="120" alt="YiMo logo" />
  <h1>YiMo</h1>
  <p>A <b>PySide6</b> desktop GUI app for translating documentation (mainly Markdown) while <b>preserving directory structure</b> and <b>Markdown structure</b>.</p>
  <p>
    <a href="https://github.com/BakaDream/YiMo/releases"><img alt="Release" src="https://img.shields.io/github/v/release/BakaDream/YiMo?style=flat-square" /></a>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/BakaDream/YiMo?style=flat-square" /></a>
    <img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" />
  </p>
  <p><a href="README.md">简体中文</a> | English</p>
</div>

## Who is this for?

Great for:
- Translating a whole docs folder (including images/static assets) into another language
- Keeping the output usable for MkDocs / VitePress / Hugo / Hexo builds
- Using OpenAI-compatible providers (`base_url` / `api_key` / `model`)

Not ideal for:
- Hard terminology enforcement / strict alignment workflows (YiMo focuses on workflow + structure stability)

## Key features

- Preserves directory structure in output
- Copies static assets (images/CSS/JS) without translating them
- Concurrency, retries, and a stop button
- Save/load project progress (YAML)
- Multiple OpenAI-compatible providers configurable in Settings
- English / Simplified Chinese UI
- Multi-platform binaries (PyInstaller and Nuitka)

## Quickstart

### Option A: Download binaries (recommended)

1. Download from GitHub Releases: <https://github.com/BakaDream/YiMo/releases>
2. Choose **Source** and **Output**
3. Click **Scan** → review tasks → click **Start**

Useful actions: **Stop**, **Retry Failed**, **Save Project / Load Project**.

### Option B: Run from source

Requirements: Python 3.12 + `uv`

```bash
uv sync --locked
uv run yimo
```

Or:

```bash
uv run python main.py
```

## Settings guide (important)

Most of YiMo’s “design knobs” (providers, rate limit, modes, prompts, Front Matter rules) are configured in **Settings**. The configuration is stored in `yimo.yaml` in your project folder.

### 1) Provider (OpenAI-compatible)

In **Settings → Providers**, you can add/edit/remove providers and choose the active one.

Each provider includes:
- `name`: provider display name
- `base_url`: OpenAI-compatible Base URL (e.g. `https://api.openai.com/v1`)
- `api_key`: secret key (keep it private)
- `model`: model name
- `rpm_limit`: requests-per-minute soft throttling
  - `<= 0` means unlimited
  - YiMo uses it to avoid hitting provider rate limits too aggressively

### 2) Translation (strategy)

In **Settings → Translation**, you can configure:

- **Translation mode**
  - `raw_markdown`: simpler and more tolerant
  - `structured_graph`: prioritizes structure stability (LangGraph + LangChain `with_structured_output()`; failures trigger repair retries)
- **Max concurrency / Max retries / Timeout / Temperature**
- **Two system prompts**
  - `raw_system_prompt` for `raw_markdown`
  - `structured_system_prompt` for `structured_graph`
  - Placeholders: `{current_language}` and `{target_language}`

### 3) Front Matter (what to translate)

In the Front Matter settings area you can control what keys are translated:

- Common keys (checkboxes): `title` / `tags` (defaults)
- Custom keys: comma-separated, supports nested paths like `a.b.c`
- Denylist keys: keys that should never be translated (e.g. `slug`, `url`, `permalink`, `date`, `draft`)

Tip: translate display-only fields (title/tags/summary) and avoid routing/build-related keys.

### 4) Markdown (fine-grained toggles)

In **Settings → Markdown**:
- Translate link text in `[text](url)` (URL stays unchanged)
- Translate image alt in `![alt](src)`
- Code-like short line threshold to reduce accidental translation of code/commands

Security note: `yimo.yaml` contains your `api_key`. Do not commit or share it.

## Concepts (v0.2+)

### Translation modes

| Mode | When to use | Notes |
| --- | --- | --- |
| `raw_markdown` | Simple & fast | Translates the Markdown text more directly |
| `structured_graph` | Structure stability | Built on **LangGraph** and LangChain `with_structured_output()`; keeps business validation + repair retries (`structured_max_repair_attempts`) |

### System prompt split

Since v0.2.0:
- `raw_system_prompt` for `raw_markdown`
- `structured_system_prompt` for `structured_graph`

Placeholders are supported:
- `{current_language}`
- `{target_language}`

### Config file: `yimo.yaml`

YiMo writes `yimo.yaml` in your project folder (including providers and API keys). You typically edit it via the GUI Settings.

Security note:
- `yimo.yaml` contains secrets. Do not commit or share it.

## Build locally

### PyInstaller

```bash
uv sync --locked
uv run --with pyinstaller --with pyinstaller-hooks-contrib python scripts/pyinstaller/build_onefile.py
```

Outputs: `dist/pyinstaller/<os>-<arch>/`

### Nuitka

```bash
uv sync --locked
uv run --with nuitka --with zstandard --with ordered-set python scripts/nuitka/build.py
```

Outputs: `dist/nuitka/<os>-<arch>/`

## Development

```bash
uv sync --locked
uv run python -m unittest discover -s tests
```

## License

GPL-3.0-only. See `LICENSE`.
