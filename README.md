## YiMo（译墨）

一个基于 PySide6 的 GUI 工具，用于批量翻译（或复制资源文件）并保持目录结构。

### 配置文件

应用配置使用项目目录下的 `yimo.yaml`（包含 providers 与 API Key）。该文件已加入 `.gitignore`，不要提交到仓库。

### 本地运行

```bash
uv sync --locked
uv run python main.py
```

### PyInstaller 打包（本机）

仓库提供统一脚本：`scripts/pyinstaller/build_onefile.py`

```bash
uv sync --locked
uv run --with pyinstaller --with pyinstaller-hooks-contrib python scripts/pyinstaller/build_onefile.py
```

输出目录：`dist/pyinstaller/<os>-<arch>/`

- Windows / Linux：生成单文件可执行（`--onefile`）
  - Windows：`dist/pyinstaller/windows-x86_64/yimo.exe`
  - Linux：`dist/pyinstaller/linux-x86_64/yimo`
- macOS：生成 `.app` 后打包为 zip（`--onedir + --windowed`，最终产物仍是单个 zip 文件）
  - `dist/pyinstaller/macos-*/yimo-macos-*.zip`

> macOS 的 `.app` 不建议使用 `--onefile`（PyInstaller 已提示未来版本会报错），因此脚本在 macOS 自动改用 `--onedir` 并 zip 输出。

### GitHub Actions 多平台打包

workflow：`.github/workflows/build-binaries.yml`（`workflow_dispatch` 手动触发）

GitHub-hosted runner 产物矩阵：
- Windows x86_64（`windows-latest`）
- Linux x86_64（`ubuntu-latest`）
- macOS x86_64（`macos-13`）
- macOS arm64（`macos-14`）

运行完成后会在 Actions 的 artifacts 中看到对应平台的打包产物。
