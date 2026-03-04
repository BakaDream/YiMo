# YiMo（译墨）

<div align="center">
  <img src="src/yimo/icons/none-background.svg" width="120" alt="YiMo logo" />
  <h1>YiMo（译墨）</h1>
  <p>一个基于 <b>PySide6</b> 的桌面 GUI 工具：批量翻译 <b>Markdown 文档</b>，并在输出侧<b>保持原目录结构</b>与<b>语法结构</b>。</p>
  <p>例如：你可以用它翻译基于 Markdown 的站点/文档工程，如 <b>MkDocs</b> / <b>VitePress</b> / <b>Hexo</b> / <b>Hugo</b> 等。</p>
  <p>YiMo translates Markdown docs (MkDocs/VitePress/Hexo/Hugo) while preserving structure.</p>
  <p>
    <a href="https://github.com/BakaDream/YiMo/releases"><img alt="Release" src="https://img.shields.io/github/v/release/BakaDream/YiMo?style=flat-square" /></a>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/github/license/BakaDream/YiMo?style=flat-square" /></a>
    <img alt="Python" src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" />
  </p>
  <p>简体中文 | <a href="README.en.md">English</a></p>
</div>

## 核心价值

- **保持目录结构**：输出侧保持源目录相对路径
- **资源自动复制**：图片 / CSS / JS 等静态资源会复制，不走翻译
- **结构稳定**：尽量保持 Markdown 结构与换行；对占位符（如 `[[YIMO_PH_000001]]`）有业务级校验
- **可控执行**：并发、失败重试、可中止
- **断点续跑**：保存/加载项目进度（YAML）

## Quickstart

### 方式一：下载运行（推荐）

1. 前往 GitHub Releases 下载对应平台产物：<https://github.com/BakaDream/YiMo/releases>
2. 打开应用后选择 **Source** 与 **Output**（目录模式或单文件模式）
3. 点击 **Scan** → 生成任务列表
4. 选择 Source/Target language → 点击 **Start**

常用操作：**Stop**（中止）、**Retry Failed**（重试失败项）、**Save Project / Load Project**（保存/恢复进度）。

### 方式二：从源码运行

要求：Python 3.12 + `uv`

```bash
uv sync --locked
uv run yimo
```

或：

```bash
uv run python main.py
```

## 关键概念（v0.2+）

### 翻译模式

| 模式 | 适用场景 | 特点 |
| --- | --- | --- |
| `raw_markdown` | 简单/快速/容错优先 | 直接翻译 Markdown 文本（更“直接”，但结构约束相对弱） |
| `structured_graph` | 结构稳定优先（推荐长文档） | 基于 **LangGraph** 分批翻译，并用 LangChain `with_structured_output()` 做结构化解析；仍保留**业务校验 + repair 重试**（最多 `structured_max_repair_attempts`） |

### System Prompt 拆分

v0.2.0 起，配置改为两套提示词：
- `raw_system_prompt`：用于 `raw_markdown`
- `structured_system_prompt`：用于 `structured_graph`

System Prompt 仍支持占位符：
- `{current_language}`：来自主界面的 Source language
- `{target_language}`：来自主界面的 Target language

### 配置文件 `yimo.yaml`

应用会在项目目录写入 `yimo.yaml`（包含 providers 与 API Key 等）。你一般不需要手写，推荐在 GUI 的 Settings 里完成。

安全提醒：
- `yimo.yaml` **包含密钥**，不要提交到仓库、不要分享给他人

## 功能特性

- **目录扫描**：批量生成翻译任务列表，保持相对路径结构
- **资源复制**：图片/静态资源自动复制（不走翻译）
- **多 Provider**：支持 OpenAI-compatible `base_url` + `api_key` + `model`（可在 Settings 管理）
- **可控并发**：并发、失败重试、可中止
- **项目进度**：支持保存/加载项目进度（YAML）
- **UI i18n**：English / 简体中文
- **打包**：PyInstaller & Nuitka，多平台二进制

## 打包（本机）

### PyInstaller

```bash
uv sync --locked
uv run --with pyinstaller --with pyinstaller-hooks-contrib python scripts/pyinstaller/build_onefile.py
```

输出目录：`dist/pyinstaller/<os>-<arch>/`

### Nuitka

```bash
uv sync --locked
uv run --with nuitka --with zstandard --with ordered-set python scripts/nuitka/build.py
```

输出目录：`dist/nuitka/<os>-<arch>/`

## CI / Releases

- 手动构建（Actions / Artifacts）：
  - PyInstaller：`.github/workflows/build-binaries.yml`
  - Nuitka：`.github/workflows/build-binaries-nuitka.yml`
- 打 tag 发布 release（自动上传二进制）：`.github/workflows/release.yml`（tag `v*` 触发）

## 开发指南

```bash
uv sync --locked
uv run python -m unittest discover -s tests
```

目录结构（核心）：
- `src/yimo/gui/`：GUI、QSS 主题、icons
- `src/yimo/core/`：扫描/翻译处理器与 LLM 调用
- `src/yimo/models/`：配置与任务/项目进度模型
- `tests/`：单元测试

参与贡献请看 `CONTRIBUTING.md`。

## License

本项目采用 **GPL-3.0-only**，详见 `LICENSE`。

## FAQ

### macOS 提示“无法打开/来自身份不明开发者”
这是 macOS Gatekeeper 的常见提示。你可以在「系统设置 → 隐私与安全性」中允许打开。

### 为什么 `yimo.yaml` 不应提交？
它包含 `api_key` 等敏感信息。即使你删除提交，历史记录也可能泄露。
