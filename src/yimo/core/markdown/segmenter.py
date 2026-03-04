from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from markdown_it import MarkdownIt

from yimo.core.markdown.front_matter import FrontMatterBlock, dump_front_matter, parse_front_matter
from yimo.models.config import AppConfig


PLACEHOLDER_PREFIX = "[[YIMO_PH_"
PLACEHOLDER_RE = re.compile(r"\[\[YIMO_PH_\d{6}\]\]")

_REF_LINK_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s+\S+")
_ADMONITION_OPEN_RE = re.compile(r"^(\s*)(!!!|\?\?\?)(\+)?\s+\S+.*$")
_CONTAINER_OPEN_RE = re.compile(r"^\s*:::\s*\S+.*$")
_CONTAINER_CLOSE_RE = re.compile(r"^\s*:::\s*$")

_MD_PARSER: MarkdownIt | None = None


def _get_md_parser() -> MarkdownIt:
    global _MD_PARSER
    if _MD_PARSER is None:
        _MD_PARSER = MarkdownIt("commonmark", {"html": True})
    return _MD_PARSER


@dataclass
class Segment:
    kind: str
    raw: str
    translatable_id: str | None = None
    template: str | None = None
    placeholders: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class FrontMatterTarget:
    id: str
    path: tuple[str | int, ...]
    original: str


@dataclass(frozen=True)
class TranslatableItem:
    id: str
    text: str
    placeholders: dict[str, str]
    source: str  # "front_matter" | "body"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentedDocument:
    front_matter: FrontMatterBlock | None
    body_segments: list[Segment]
    translatable_items: list[TranslatableItem]
    front_matter_targets: list[FrontMatterTarget]
    body_text: str


class _PlaceholderGen:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"[[YIMO_PH_{self._n:06d}]]"


def parse_custom_keys(custom: str) -> list[list[str]]:
    out: list[list[str]] = []
    for raw in (custom or "").split(","):
        s = raw.strip()
        if not s:
            continue
        parts = [p.strip() for p in s.split(".") if p.strip()]
        if parts:
            out.append(parts)
    return out


def selected_front_matter_key_specs(config: AppConfig) -> list[list[str]]:
    base = [k.strip() for k in (config.front_matter_translate_keys or []) if k and k.strip()]
    specs: list[list[str]] = [[k] for k in base]
    specs.extend(parse_custom_keys(getattr(config, "front_matter_custom_keys", "")))
    # de-dup by normalized dotted path
    seen: set[str] = set()
    uniq: list[list[str]] = []
    for spec in specs:
        key = ".".join([p.lower() for p in spec])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(spec)
    return uniq


def _denylisted_path(path: Iterable[str], denylist: set[str]) -> bool:
    for p in path:
        if p.lower() in denylist:
            return True
    return False


_URL_LIKE_RE = re.compile(r"^(https?://|/|\.{1,2}/|#)")


def _url_or_path_like(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    return bool(_URL_LIKE_RE.match(v)) or "://" in v


def collect_front_matter_targets(block: FrontMatterBlock, config: AppConfig) -> list[FrontMatterTarget]:
    denylist = set([k.lower() for k in (config.front_matter_denylist_keys or [])])
    targets: list[FrontMatterTarget] = []

    def add_target(path: list[str | int], value: str, idx: int) -> None:
        if _url_or_path_like(value):
            return
        targets.append(FrontMatterTarget(id=f"fm{idx:04d}", path=tuple(path), original=value))

    idx = 1
    for spec in selected_front_matter_key_specs(config):
        if _denylisted_path(spec, denylist):
            continue

        cur: Any = block.data
        ok = True
        for k in spec:
            if not isinstance(cur, dict) or k not in cur:
                ok = False
                break
            cur = cur[k]
        if not ok:
            continue

        path_prefix: list[str | int] = list(spec)
        if isinstance(cur, str):
            add_target(path_prefix, cur, idx)
            idx += 1
        elif isinstance(cur, list) and cur and all(isinstance(x, str) for x in cur):
            for j, s in enumerate(cur):
                add_target(path_prefix + [j], s, idx)
                idx += 1

    return targets


def apply_front_matter_targets(
    block: FrontMatterBlock,
    translated: dict[str, str],
    targets: list[FrontMatterTarget],
) -> tuple[str, dict[str, Any]]:
    if not block:
        return "", {}

    data = copy.deepcopy(block.data)

    def set_path(path: tuple[str | int, ...], value: str) -> None:
        cur: Any = data
        for p in path[:-1]:
            cur = cur[p]  # type: ignore[index]
        cur[path[-1]] = value  # type: ignore[index]

    changed = False
    for t in targets:
        if t.id not in translated:
            continue
        new_v = translated[t.id]
        if isinstance(new_v, str) and new_v != t.original:
            set_path(t.path, new_v)
            changed = True

    if not changed:
        return block.raw_block, block.data
    return dump_front_matter(data, delimiter=block.delimiter, format=block.format), data


def _is_reference_link_def(line: str) -> bool:
    return bool(_REF_LINK_DEF_RE.match(line))


def _is_code_like_short_line(line: str, max_chars: int) -> bool:
    s = line.rstrip("\r\n")
    if not s.strip():
        return False
    if len(s) > max_chars:
        return False
    # Heuristic: avoid skipping normal prose lines that simply contain URLs or inline code.
    prose_signal = 0
    if re.search(r"[\u4e00-\u9fff]", s):
        prose_signal += 1
    prose_signal += len(re.findall(r"[A-Za-z]{3,}", s))

    hits = 0
    features = ["--", "::", "()", "{}", "=", "->"]
    for f in features:
        if f in s:
            hits += 1
    if s.lstrip().startswith(("$", ">", "#")):
        hits += 1

    # If it looks like prose and doesn't have strong code markers, don't skip.
    if prose_signal >= 3 and hits == 0:
        return False

    non_space = [c for c in s if not c.isspace()]
    if non_space:
        symbolish = sum(1 for c in non_space if not (c.isalnum() or c in "_-"))
        if symbolish / max(1, len(non_space)) > 0.25:
            hits += 1
    return hits >= 2


def mask_text(text: str, config: AppConfig, ph: _PlaceholderGen) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def put(value: str) -> str:
        key = ph.next()
        placeholders[key] = value
        return key

    # 1) Inline code spans
    out = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            j = i
            while j < len(text) and text[j] == "`":
                j += 1
            tick_len = j - i
            k = text.find("`" * tick_len, j)
            if k != -1:
                raw = text[i : k + tick_len]
                out.append(put(raw))
                i = k + tick_len
                continue
        out.append(text[i])
        i += 1
    text = "".join(out)

    # 2) HTML tags (single-line)
    def _mask_html(m: re.Match[str]) -> str:
        return put(m.group(0))

    text = re.sub(r"<[^>\n]+>", _mask_html, text)

    # 3) Images: preserve whole syntax (alt not translated)
    def _mask_image(m: re.Match[str]) -> str:
        return put(m.group(0))

    text = re.sub(r"!\[[^\]]*]\([^)\n]*\)", _mask_image, text)

    # 4) Links: translate link text but preserve destination
    if getattr(config, "translate_link_text", True):

        def _mask_link_dest(m: re.Match[str]) -> str:
            inner = m.group(2)
            return f"[{m.group(1)}]({put(inner)})"

        # Conservative: no newlines inside
        text = re.sub(r"\[([^\]\n]+)]\(([^)\n]+)\)", _mask_link_dest, text)

    # 5) Bare URLs
    def _mask_url(m: re.Match[str]) -> str:
        return put(m.group(0))

    text = re.sub(r"https?://[^\s)\]>\n]+", _mask_url, text)

    return text, placeholders


def unmask_text(text: str, placeholders: dict[str, str]) -> str:
    out = text
    for k, v in placeholders.items():
        out = out.replace(k, v)
    return out


def _indent_width(s: str) -> int:
    w = 0
    for ch in s:
        if ch == " ":
            w += 1
        elif ch == "\t":
            w += 4
        else:
            break
    return w


def _collect_admonition_info(lines: list[str]) -> tuple[set[int], list[tuple[int, int]]]:
    marker_lines: set[int] = set()
    content_ranges: list[tuple[int, int]] = []

    i = 0
    while i < len(lines):
        m = _ADMONITION_OPEN_RE.match(lines[i].rstrip("\r\n"))
        if not m:
            i += 1
            continue

        marker_lines.add(i)
        base_indent = _indent_width(m.group(1))

        j = i + 1
        while j < len(lines):
            if lines[j].strip() == "":
                j += 1
                continue
            if _indent_width(lines[j]) >= base_indent + 4:
                j += 1
                continue
            break

        if j > i + 1:
            content_ranges.append((i + 1, j))
        i = j

    return marker_lines, content_ranges


def _range_fully_within_any(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    for a, b in ranges:
        if start >= a and end <= b:
            return True
    return False


def segment_body(body: str, config: AppConfig, ph: _PlaceholderGen) -> list[Segment]:
    lines = body.splitlines(keepends=True)
    if not lines:
        return []

    # Default: everything is translatable text, blanks are kept as raw.
    line_kind: list[str] = ["text"] * len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "":
            line_kind[i] = "blank"

    admonition_marker_lines, admonition_content_ranges = _collect_admonition_info(lines)

    # Mark protected blocks using markdown-it-py token maps.
    md = _get_md_parser()
    tokens = md.parse(body)

    def mark_range(kind: str, start: int, end: int) -> None:
        start = max(0, start)
        end = min(len(lines), end)
        for k in range(start, end):
            # Fence blocks always win; indented code shouldn't override fenced code.
            if line_kind[k] == "code_block":
                continue
            if kind == "indented_code" and line_kind[k] in {"code_block", "html_block"}:
                continue
            if kind == "html_block" and line_kind[k] in {"code_block", "indented_code"}:
                continue
            line_kind[k] = kind

    for tok in tokens:
        if not getattr(tok, "map", None):
            continue
        start, end = tok.map  # type: ignore[misc]
        if tok.type == "fence":
            mark_range("code_block", start, end)
        elif tok.type == "html_block":
            mark_range("html_block", start, end)
        elif tok.type == "code_block":
            # Avoid false positives for mkdocs admonition indented content.
            if _range_fully_within_any(start, end, admonition_content_ranges):
                continue
            mark_range("indented_code", start, end)

    # MkDocs admonition marker line: keep syntax line raw, translate its content.
    for i in admonition_marker_lines:
        if 0 <= i < len(line_kind) and line_kind[i] == "text":
            line_kind[i] = "admonition_marker"

    # Container marker lines and reference link definitions: keep syntax lines raw.
    for i, line in enumerate(lines):
        if line_kind[i] != "text":
            continue
        s = line.rstrip("\r\n")
        if _CONTAINER_OPEN_RE.match(s) or _CONTAINER_CLOSE_RE.match(s):
            line_kind[i] = "container_marker"
            continue
        if _is_reference_link_def(s):
            line_kind[i] = "link_def"

    segments: list[Segment] = []
    buf_lines: list[str] = []
    buf_kind: str | None = None

    def flush_text_block(raw_text: str) -> None:
        if not raw_text:
            return
        trans_buf: list[str] = []
        for ln in raw_text.splitlines(keepends=True):
            if _is_code_like_short_line(ln, getattr(config, "code_like_short_line_max_chars", 80)):
                if trans_buf:
                    text_block = "".join(trans_buf)
                    template, placeholders = mask_text(text_block, config, ph)
                    segments.append(Segment(kind="text", raw=text_block, template=template, placeholders=placeholders))
                    trans_buf.clear()
                segments.append(Segment(kind="raw", raw=ln))
            else:
                trans_buf.append(ln)
        if trans_buf:
            text_block = "".join(trans_buf)
            template, placeholders = mask_text(text_block, config, ph)
            segments.append(Segment(kind="text", raw=text_block, template=template, placeholders=placeholders))

    def flush_buf() -> None:
        nonlocal buf_kind, buf_lines
        if not buf_lines or buf_kind is None:
            buf_lines = []
            buf_kind = None
            return
        raw = "".join(buf_lines)
        if buf_kind == "text":
            flush_text_block(raw)
        else:
            segments.append(Segment(kind=buf_kind, raw=raw))
        buf_lines = []
        buf_kind = None

    for i, line in enumerate(lines):
        kind = line_kind[i]
        if buf_kind is None:
            buf_kind = kind
            buf_lines = [line]
            continue
        if kind == buf_kind:
            buf_lines.append(line)
            continue
        flush_buf()
        buf_kind = kind
        buf_lines = [line]

    flush_buf()
    return segments


def segment_document(content: str, config: AppConfig) -> SegmentedDocument:
    fm, body = parse_front_matter(content)
    ph = _PlaceholderGen()

    fm_targets: list[FrontMatterTarget] = []
    translatables: list[TranslatableItem] = []
    if fm is not None:
        fm_targets = collect_front_matter_targets(fm, config)
        for t in fm_targets:
            translatables.append(
                TranslatableItem(
                    id=t.id,
                    text=t.original,
                    placeholders={},
                    source="front_matter",
                    meta={"path": t.path},
                )
            )

    body_segments = segment_body(body, config, ph)
    body_id = 1
    for seg in body_segments:
        if seg.template is not None:
            seg_id = f"b{body_id:04d}"
            body_id += 1
            seg.translatable_id = seg_id
            translatables.append(
                TranslatableItem(
                    id=seg_id,
                    text=seg.template,
                    placeholders=seg.placeholders,
                    source="body",
                )
            )

    return SegmentedDocument(
        front_matter=fm,
        body_segments=body_segments,
        translatable_items=translatables,
        front_matter_targets=fm_targets,
        body_text=body,
    )

