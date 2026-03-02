# YiMo（译墨）

YiMo 是一个基于 **PySide6** 的桌面 GUI 工具，用于批量翻译文档（主要是 Markdown），并在输出侧**保持原目录结构**。它也会自动识别并复制资源文件（图片、CSS、JS 等），避免你手工整理。

> 项目定位：面向个人/团队的文档翻译工作流工具（支持 OpenAI-compatible providers）。

## 功能特性

- **目录扫描**：批量生成翻译任务列表，保持相对路径结构
- **资源复制**：图片/静态资源自动复制（不走翻译）
- **可控并发**：翻译任务并发、失败重试、可中止
- **项目进度**：支持保存/加载项目进度（YAML）
- **多 Provider**：支持 OpenAI-compatible `base_url` + `api_key` + `model`
- **UI i18n**：English / 简体中文
- **翻译语言选择**：原语言支持 `auto`，并内置多语言 + 支持自定义输入
- **打包**：PyInstaller & Nuitka，多平台二进制

## 下载与运行（推荐）

从 GitHub Releases 下载对应平台产物即可运行。

- Windows：下载 `*.exe`，双击运行
- macOS：下载 `*.zip`，解压后得到 `YiMo.app`，拖拽到「应用程序」后运行
- Linux：下载无后缀可执行文件，`chmod +x` 后运行

同一个平台会提供两套产物：
- `pyinstaller`：更传统的 Python 打包方式
- `nuitka`：编译式打包方式

你可以任选其一使用（功能一致）。

## 从源码运行（开发者/想自己跑）

要求：Python 3.12 + `uv`

```bash
uv sync --locked
uv run python main.py
```

也可以通过入口命令运行：

```bash
uv run yimo
```

## GUI 使用方法（建议流程）

1. 选择 **Source** 与 **Output**（目录模式或单文件模式）
2. 点击 **Scan** 扫描生成任务列表
3. 选择翻译语言：
   - **Source language**：可选 `auto`（自动识别）/ 内置语言 / 自定义输入
   - **Target language**：内置语言 / 自定义输入
4. 点击 **Start** 开始翻译
5. 如需中止：点击 **Stop**
6. 失败项可用 **Retry Failed** 重试
7. 需要下次继续：点击 **Save Project** 保存项目进度；之后可用 **Load Project** 恢复

## 配置说明（全部在 GUI 内完成）

应用会在项目目录写入 `yimo.yaml`（包含 providers 与 API Key 等）。你**不需要手写**该文件，全部在 GUI 中完成即可。

注意：
- `yimo.yaml` **包含密钥**，请勿提交到仓库或分享给他人
- 本仓库已将 `yimo.yaml` 加入 `.gitignore`

### Provider 配置（OpenAI-compatible）

在 Settings 中可以：
- 新增/编辑/删除 Provider
- 设置 `base_url`、`api_key`、`model`、`rpm_limit`
- 选择当前启用的 Provider
- 调整并发/重试/timeout/temperature

### System Prompt 占位符

你可以在 System Prompt 中使用：
- `{current_language}`：原语言（来自主界面的 Source language）
- `{target_language}`：目标语言（来自主界面的 Target language）

这两个占位符会在**每次翻译请求前**动态替换。

## 保存/加载项目进度

Save Project 会保存：
- 当前 Source/Output 路径
- 任务列表与状态（pending/processing/completed/failed…）
- 当前选择的翻译语言（Source/Target language）

Load Project 会恢复以上内容，便于断点续跑。

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

手动构建（Actions / Artifacts）：
- PyInstaller：`.github/workflows/build-binaries.yml`
- Nuitka：`.github/workflows/build-binaries-nuitka.yml`

打 tag 发布 release（自动上传二进制）：
- `.github/workflows/release.yml`（tag `v*` 触发）

## 开发指南

```bash
uv sync --locked
uv run python -m unittest discover -s tests
```

目录结构（核心）：
- `src/yimo/gui/`：GUI、QSS 主题、icons
- `src/yimo/core/`：扫描/翻译处理器与 OpenAI 调用
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

