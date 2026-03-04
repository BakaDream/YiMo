from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import yaml
from frontmatter.default_handlers import YAMLHandler


@dataclass(frozen=True)
class FrontMatterBlock:
    delimiter: str
    format: Literal["yaml", "toml"]
    raw_block: str
    raw_meta: str
    data: dict[str, Any]


def parse_front_matter(text: str) -> tuple[FrontMatterBlock | None, str]:
    """
    Parse Front Matter at the beginning of a Markdown document.

    Supported forms (must start at the first line):
      YAML: --- ... ---
      TOML: +++ ... +++

    If not present, returns (None, original_text).
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return None, text

    first = lines[0].strip("\r\n").strip()
    if first not in {"---", "+++"}:
        return None, text

    delimiter = first
    fmt: Literal["yaml", "toml"] = "yaml" if delimiter == "---" else "toml"

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip("\r\n").strip() == delimiter:
            end_idx = i
            break
    if end_idx is None:
        return None, text

    raw_block = "".join(lines[: end_idx + 1])
    raw_meta = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])

    try:
        if fmt == "yaml":
            data = YAMLHandler().load(raw_meta) or {}
        else:
            try:
                from frontmatter.default_handlers import TOMLHandler  # type: ignore

                if TOMLHandler is not None:
                    data = TOMLHandler().load(raw_meta) or {}
                else:
                    raise ImportError("TOMLHandler unavailable")
            except Exception:
                try:
                    import tomllib

                    data = tomllib.loads(raw_meta) or {}
                except Exception:
                    # Best-effort fallback: if TOML parsing fails, try YAML so we at least don't crash.
                    data = yaml.safe_load(raw_meta) or {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    return FrontMatterBlock(delimiter=delimiter, format=fmt, raw_block=raw_block, raw_meta=raw_meta, data=data), body


def _dump_toml(data: dict[str, Any]) -> str:
    """
    Dump TOML metadata for front matter.

    Prefer the 3rd-party 'toml' package when available (better coverage),
    otherwise use a minimal dumper for common scalar/list/dict cases.
    """
    try:
        import toml  # type: ignore

        return toml.dumps(data)
    except Exception:
        pass

    def dump_value(v: Any) -> str:
        if v is None:
            return '""'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            return f"\"{escaped}\""
        if isinstance(v, list):
            return "[" + ", ".join(dump_value(x) for x in v) + "]"
        # fallback: stringify
        escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
        return f"\"{escaped}\""

    out_lines: list[str] = []

    def emit_table(prefix: list[str], table: dict[str, Any]) -> None:
        # emit scalars first
        scalars: dict[str, Any] = {}
        nested: dict[str, dict[str, Any]] = {}
        for k, v in table.items():
            if isinstance(v, dict):
                nested[k] = v
            else:
                scalars[k] = v

        if prefix:
            out_lines.append("[" + ".".join(prefix) + "]")
        for k, v in scalars.items():
            out_lines.append(f"{k} = {dump_value(v)}")
        for k, v in nested.items():
            out_lines.append("")
            emit_table([*prefix, k], v)

    emit_table([], data)
    return "\n".join(out_lines) + "\n"


def dump_front_matter(data: dict[str, Any], *, delimiter: str, format: Literal["yaml", "toml"]) -> str:
    if not data:
        dumped = ""
    else:
        if format == "yaml":
            dumped = YAMLHandler().export(data or {}, sort_keys=False, allow_unicode=True)
        else:
            try:
                from frontmatter.default_handlers import TOMLHandler  # type: ignore

                if TOMLHandler is not None:
                    dumped = TOMLHandler().export(data or {})
                else:
                    dumped = _dump_toml(data or {})
            except Exception:
                dumped = _dump_toml(data or {})

    dumped = dumped or ""
    if dumped and not dumped.endswith("\n"):
        dumped += "\n"
    return f"{delimiter}\n{dumped}{delimiter}\n"
