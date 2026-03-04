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

## Settings 配置指南（重点）

YiMo 的大部分“设计点”（供应商/限流/模式/提示词/Front Matter 等）都集中在 **Settings** 里完成。

- **全局配置文件**：默认读写启动程序时的工作目录下的 `yimo.yaml`
  - 从源码运行：通常就是你当前终端所在目录
  - 从已打包的二进制启动：不同平台/启动方式的“工作目录”可能不同（常见是应用所在目录或系统默认目录）
- **项目进度文件**：通过 **Save Project / Load Project** 保存/恢复（你自行选择保存路径），包含任务列表/状态，以及 Source/Target language 与 Translation mode；**不包含** Provider / API Key / Prompt 等全局设置

### 1) Provider（供应商 / OpenAI-compatible）

在 **Settings → Providers** 中可以新增/编辑/删除 Provider，并选择一个作为当前启用的 Provider。

每个 Provider 包含：
- `name`：Provider 名称（用于在列表中选择）
- `base_url`：OpenAI-compatible Base URL（例如 `https://api.openai.com/v1`，或自建/第三方兼容地址）
- `api_key`：密钥（注意保密）
- `model`：模型名称
- `rpm_limit`：Requests Per Minute（请求/分钟）的软限流
  - `<= 0` 表示不限制
  - YiMo 会按该值做节流，避免短时间内打爆 provider 的限额

### 2) Translation（翻译策略）

在 **Settings → Translation** 中可以配置：

- **Translation mode**：
  - `raw_markdown`：更直接、容错更高
  - `structured_graph`：更强调结构稳定（基于 LangGraph，并通过 LangChain `with_structured_output()` 做结构化输出；失败会进入 repair 重试）
- **Max concurrency / Max retries / Timeout / Temperature**：
  - 并发、失败重试次数、请求超时、采样温度等通用参数
- **structured_graph 调参**（仅结构化模式生效）：
  - `structured_chunk_tokens`：每批 payload 的 token 上限（越大越“整段”，越小越“细分”）
  - `structured_memory_max_tokens`：结构化“记忆”（summary/glossary）注入 prompt 的 token 上限
  - `structured_max_repair_attempts`：结构化输出校验失败时的修复重试次数
- **System Prompt（两套）**：
  - `raw_system_prompt`：用于 `raw_markdown`
  - `structured_system_prompt`：用于 `structured_graph`
  - 两者都支持占位符：`{current_language}`、`{target_language}`

### 3) Front Matter（要翻译哪些字段）

在 **Settings → Markdown** 的 Front Matter 区域中可以控制 Front Matter 的翻译范围（**仅 `structured_graph` 模式生效**；`raw_markdown` 只靠提示词约束，无法做字段级别的“精确选择”）：

- **常用字段（checkbox）**：`title` / `tags` / `description` / `summary` / `categories`
- **自定义字段**：通过逗号分隔填写（支持 `a.b.c` 这种嵌套路径）
- **禁止翻译字段（denylist）**：出于安全原因，`slug` / `url` / `permalink` / `date` / `draft` 等字段默认永不翻译；如需调整可手动编辑 `yimo.yaml` 的 `front_matter_denylist_keys`

建议：只翻译展示性字段（如标题、摘要、标签），避免翻译构建/路由相关字段。

### 4) Advanced（细粒度开关）

在 **Settings → Advanced** 中可以配置：
- 是否翻译链接文本：`[text](url)` 的 `text`（URL 保持不变）
- 是否翻译图片 alt：`![alt](src)` 的 `alt`（目前 `structured_graph` 会保护整段图片语法，默认不会翻译 alt；该开关主要为后续增强预留）
- “代码味短行”跳过阈值：用于减少把命令行/参数行误翻译的概率（结构化模式的分段器会用到）

> 安全提醒：`yimo.yaml` **包含 `api_key`**，请勿提交到仓库或分享给他人。

## 支持的文件与扫描规则

- **会翻译的文件**：`.md` / `.markdown`
- **会复制的资源文件**：`.png` `.jpg` `.jpeg` `.gif` `.svg` `.webp` `.css` `.js` `.json` `.pdf` `.ico` `.woff` `.ttf`
- **会忽略的目录**：`.git` / `__pycache__` / `node_modules` / `.venv` / `.idea` / `.vscode` / `site`

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

应用会在**启动时的工作目录**读写 `yimo.yaml`（包含 providers 与 API Key 等）。你一般不需要手写，推荐在 GUI 的 Settings 里完成。

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
