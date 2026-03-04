from __future__ import annotations

import asyncio
import json
import operator
import threading
from dataclasses import dataclass
from typing import Any, Callable

from typing_extensions import Annotated, TypedDict

from yimo.core.engines.base import EngineContext
from yimo.core.llm.schema import StructuredLLMOutput
from yimo.core.llm.tokens import count_tokens, trim_to_tokens
from yimo.core.markdown.segmenter import (
    PLACEHOLDER_RE,
    SegmentedDocument,
    TranslatableItem,
    apply_front_matter_targets,
    segment_document,
    unmask_text,
)


@dataclass
class _Validation:
    ok: bool
    error: str | None = None


def _merge_translations(a: dict[str, str] | None, b: dict[str, str] | None) -> dict[str, str]:
    out: dict[str, str] = dict(a or {})
    out.update(b or {})
    return out


def _merge_glossary(
    a: list[dict[str, str]] | None,
    b: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in list(a or []) + list(b or []):
        source = (item.get("source") or "").strip()
        target = (item.get("target") or "").strip()
        key = source.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append({"source": source, "target": target})
    # Keep newest at the end; limit size.
    return merged[-50:]


class StructuredState(TypedDict, total=False):
    doc: SegmentedDocument
    cursor: int
    batch_ids: list[str]
    batch_items: list[dict[str, str]]
    batch_payload: str
    attempt: int
    max_attempts: int
    llm_raw: str
    llm_json: StructuredLLMOutput | None
    validation: _Validation
    translations: Annotated[dict[str, str], _merge_translations]
    memory_summary: str
    memory_glossary: Annotated[list[dict[str, str]], _merge_glossary]
    errors: Annotated[list[str], operator.add]
    repair: dict[str, Any] | None
    system_prompt: str
    source_lang: str
    target_lang: str
    stop_flag: threading.Event | None
    chunk_tokens: int
    memory_max_tokens: int
    model_name: str
    final_text: str


class StructuredGraphEngine:
    def __init__(self, ctx: EngineContext, *, llm: Any | None = None) -> None:
        self._ctx = ctx
        self._llm = llm

    async def translate_markdown(
        self,
        content: str,
        *,
        source_lang: str,
        target_lang: str,
        system_prompt: str,
        stop_flag: threading.Event | None,
    ) -> str:
        if not content.strip():
            return ""

        config = self._ctx.get_config()
        provider = self._ctx.get_provider()
        doc = segment_document(content, config)
        if not doc.translatable_items:
            return content

        initial_state: StructuredState = {
            "doc": doc,
            "cursor": 0,
            "batch_ids": [],
            "batch_items": [],
            "batch_payload": "",
            "attempt": 0,
            "max_attempts": int(getattr(config, "structured_max_repair_attempts", 2)),
            "llm_raw": "",
            "llm_json": None,
            "validation": _Validation(ok=True, error=None),
            "translations": {},
            "memory_summary": "",
            "memory_glossary": [],
            "errors": [],
            "system_prompt": system_prompt,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "stop_flag": stop_flag,
            "chunk_tokens": int(getattr(config, "structured_chunk_tokens", 2000)),
            "memory_max_tokens": int(getattr(config, "structured_memory_max_tokens", 300)),
            "model_name": str(getattr(provider, "model", "") or ""),
        }

        try:
            runner = self._build_runner()
            out_state = await runner(initial_state)
            return out_state["final_text"]
        except asyncio.CancelledError:
            raise
        except Exception as e:
            raise Exception(f"Structured translation failed: {e}")

    def _build_runner(self) -> Callable[[StructuredState], Any]:
        try:
            from langgraph.graph import END, StateGraph  # type: ignore
        except Exception:
            return self._run_fallback

        async def init_state(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            return {"cursor": 0, "translations": {}, "memory_summary": "", "memory_glossary": [], "errors": []}

        async def select_batch(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            doc: SegmentedDocument = state["doc"]
            cursor: int = state["cursor"]
            chunk_tokens: int = state["chunk_tokens"]
            model_name: str = state.get("model_name") or ""

            items: list[TranslatableItem] = doc.translatable_items[cursor:]
            picked: list[TranslatableItem] = []
            total = 0
            for it in items:
                add_tokens = count_tokens(it.text, model_name) + 40
                if picked and total + add_tokens > chunk_tokens:
                    break
                picked.append(it)
                total += add_tokens
                if total >= chunk_tokens:
                    break

            batch_ids = [it.id for it in picked]
            batch_items = [{"id": it.id, "text": it.text} for it in picked]

            payload = self._build_payload(
                memory_summary=state.get("memory_summary", ""),
                memory_glossary=state.get("memory_glossary", []),
                items=batch_items,
                memory_max_tokens=state["memory_max_tokens"],
                model_name=model_name,
                repair=state.get("repair", None),
            )
            return {"batch_ids": batch_ids, "batch_items": batch_items, "batch_payload": payload, "attempt": 0, "repair": None}

        async def rate_limit_acquire(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            await self._ctx.acquire_rate_limit()
            return {}

        async def llm_translate(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            llm = await self._get_llm()

            sys_msg, user_msg = self._build_messages(
                system_prompt=state["system_prompt"],
                source_lang=state["source_lang"],
                target_lang=state["target_lang"],
                payload=state["batch_payload"],
            )
            msg = await llm.ainvoke([sys_msg, user_msg])
            return {"llm_raw": getattr(msg, "content", "")}

        async def parse_llm_output(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            raw = (state.get("llm_raw") or "").strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            try:
                data = json.loads(raw)
                parsed = StructuredLLMOutput.model_validate(data)
                return {"llm_json": parsed, "validation": _Validation(ok=True, error=None)}
            except Exception as e:
                return {"llm_json": None, "validation": _Validation(ok=False, error=f"Output schema error: {e}")}

        async def validate_llm_output(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            existing: _Validation | None = state.get("validation")
            if existing is not None and not existing.ok:
                return {"validation": existing}
            batch_ids: list[str] = state["batch_ids"]
            doc: SegmentedDocument = state["doc"]
            id_to_placeholders = {it.id: set(it.placeholders.keys()) for it in doc.translatable_items}

            parsed: StructuredLLMOutput | None = state.get("llm_json")
            if parsed is None:
                return {"validation": _Validation(ok=False, error="No parsed output")}

            got_ids = [t.id for t in parsed.translations]
            if sorted(got_ids) != sorted(batch_ids) or len(got_ids) != len(batch_ids):
                return {"validation": _Validation(ok=False, error=f"IDs mismatch: expected={batch_ids}, got={got_ids}")}

            for t in parsed.translations:
                text = t.text or ""
                expected_ph = id_to_placeholders.get(t.id, set())
                missing = [p for p in expected_ph if p not in text]
                if missing:
                    return {"validation": _Validation(ok=False, error=f"Missing placeholders for {t.id}: {missing}")}
                unknown = [p for p in PLACEHOLDER_RE.findall(text) if p not in expected_ph]
                if unknown:
                    return {"validation": _Validation(ok=False, error=f"Unknown placeholders for {t.id}: {unknown}")}

            return {"validation": _Validation(ok=True, error=None)}

        async def commit_batch(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            parsed: StructuredLLMOutput = state["llm_json"]
            delta: dict[str, str] = {t.id: t.text for t in parsed.translations}
            return {"translations": delta}

        async def update_memory(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            parsed: StructuredLLMOutput = state["llm_json"]
            memory_max_tokens: int = state["memory_max_tokens"]
            model_name: str = state.get("model_name") or ""

            summary = trim_to_tokens((parsed.memory.summary or "").strip(), model_name, memory_max_tokens).strip()
            new_items = [
                {"source": (g.source or "").strip(), "target": (g.target or "").strip()} for g in (parsed.memory.glossary or [])
            ]
            return {"memory_summary": summary, "memory_glossary": new_items}

        async def advance_cursor(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            cursor: int = state["cursor"]
            cursor += len(state["batch_ids"])
            return {"cursor": cursor}

        async def prepare_repair(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            attempt = int(state.get("attempt") or 0) + 1
            val: _Validation = state["validation"]
            llm_raw = (state.get("llm_raw") or "").strip()
            if len(llm_raw) > 800:
                llm_raw = llm_raw[:800] + "…"
            repair = {
                "attempt": attempt,
                "error": val.error or "validation failed",
                "expected_ids": state.get("batch_ids", []),
                "previous_output_snippet": llm_raw,
                "requirements": [
                    "Output JSON only (no markdown fences, no explanations).",
                    "Return translations for all expected ids, exactly once each.",
                    "Do not remove or alter any placeholders like [[YIMO_PH_000001]].",
                    "The JSON object MUST include both keys: translations (array) and memory (object).",
                ],
            }
            payload = self._build_payload(
                memory_summary=state.get("memory_summary", ""),
                memory_glossary=state.get("memory_glossary", []),
                items=state.get("batch_items", []),
                memory_max_tokens=state["memory_max_tokens"],
                model_name=state.get("model_name") or "",
                repair=repair,
            )
            return {"attempt": attempt, "batch_payload": payload, "repair": repair, "llm_json": None}

        async def fail_graph(state: StructuredState) -> dict[str, Any]:
            val: _Validation = state.get("validation")
            llm_raw = (state.get("llm_raw") or "").strip()
            if len(llm_raw) > 800:
                llm_raw = llm_raw[:800] + "…"
            raise ValueError(f"{val.error or 'structured validation failed'}; last_output={llm_raw}")

        async def assemble_output(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            doc: SegmentedDocument = state["doc"]
            translations: dict[str, str] = state.get("translations") or {}

            fm_text = ""
            if doc.front_matter is not None:
                fm_text, _ = apply_front_matter_targets(doc.front_matter, translations, doc.front_matter_targets)

            out_parts: list[str] = []
            for seg in doc.body_segments:
                if seg.translatable_id:
                    translated = translations.get(seg.translatable_id, seg.template or "")
                    out_parts.append(unmask_text(translated, seg.placeholders))
                else:
                    out_parts.append(seg.raw)
            final_text = fm_text + "".join(out_parts)
            return {"final_text": final_text}

        async def final_validate(state: StructuredState) -> dict[str, Any]:
            self._ensure_not_stopped(state)
            final_text = state.get("final_text") or ""
            leftovers = PLACEHOLDER_RE.findall(final_text)
            if leftovers:
                raise ValueError(f"Leftover placeholders: {leftovers[:5]}")
            return {}

        def route_next(state: StructuredState) -> str:
            doc: SegmentedDocument = state["doc"]
            if int(state["cursor"]) >= len(doc.translatable_items):
                return "assemble_output"
            return "select_batch"

        def route_validation(state: StructuredState) -> str:
            v: _Validation = state["validation"]
            return "commit_batch" if v.ok else "prepare_repair"

        def route_repair(state: StructuredState) -> str:
            attempt = int(state.get("attempt") or 0)
            max_attempts = int(state.get("max_attempts") or 2)
            return "rate_limit_acquire" if attempt < max_attempts else "fail_graph"

        g: Any = StateGraph(state_schema=StructuredState)
        g.add_node("init_state", init_state)
        g.add_node("segment_document", lambda s: {})  # already done before graph run
        g.add_node("select_batch", select_batch)
        g.add_node("rate_limit_acquire", rate_limit_acquire)
        g.add_node("llm_translate", llm_translate)
        g.add_node("parse_llm_output", parse_llm_output)
        g.add_node("validate_llm_output", validate_llm_output)
        g.add_node("commit_batch", commit_batch)
        g.add_node("update_memory", update_memory)
        g.add_node("advance_cursor", advance_cursor)
        g.add_node("prepare_repair", prepare_repair)
        g.add_node("fail_graph", fail_graph)
        g.add_node("assemble_output", assemble_output)
        g.add_node("final_validate", final_validate)

        g.set_entry_point("init_state")
        g.add_edge("init_state", "select_batch")  # segment_document already done
        g.add_edge("select_batch", "rate_limit_acquire")
        g.add_edge("rate_limit_acquire", "llm_translate")
        g.add_edge("llm_translate", "parse_llm_output")
        g.add_edge("parse_llm_output", "validate_llm_output")
        g.add_conditional_edges("validate_llm_output", route_validation, {"commit_batch": "commit_batch", "prepare_repair": "prepare_repair"})
        g.add_edge("commit_batch", "update_memory")
        g.add_edge("update_memory", "advance_cursor")
        g.add_conditional_edges("advance_cursor", route_next, {"select_batch": "select_batch", "assemble_output": "assemble_output"})
        g.add_conditional_edges("prepare_repair", route_repair, {"rate_limit_acquire": "rate_limit_acquire", "fail_graph": "fail_graph"})
        g.add_edge("fail_graph", END)
        g.add_edge("assemble_output", "final_validate")
        g.add_edge("final_validate", END)

        compiled = g.compile()

        async def runner(state: StructuredState) -> dict[str, Any]:
            return await compiled.ainvoke(state)

        return runner

    async def _run_fallback(self, state: StructuredState) -> dict[str, Any]:
        state = dict(state)
        state.update({"cursor": 0, "translations": {}, "memory_summary": "", "memory_glossary": [], "errors": []})

        doc: SegmentedDocument = state["doc"]
        max_attempts = int(state.get("max_attempts") or 2)

        while state["cursor"] < len(doc.translatable_items):
            state.update(await self._fallback_select_batch(state))

            attempt = 0
            while True:
                self._ensure_not_stopped(state)
                await self._ctx.acquire_rate_limit()
                llm = await self._get_llm()
                sys_msg, user_msg = self._build_messages(
                    system_prompt=state["system_prompt"],
                    source_lang=state["source_lang"],
                    target_lang=state["target_lang"],
                    payload=state["batch_payload"],
                )
                msg = await llm.ainvoke([sys_msg, user_msg])
                raw = (getattr(msg, "content", "") or "").strip()
                try:
                    parsed = self._fallback_parse(raw)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise ValueError(f"JSON parse failed after repairs: {e}")
                    state["repair"] = {"error": f"JSON parse error: {e}", "expected_ids": state["batch_ids"]}
                    state["batch_payload"] = self._build_payload(
                        memory_summary=state.get("memory_summary", ""),
                        memory_glossary=state.get("memory_glossary", []),
                        items=state.get("batch_items", []),
                        memory_max_tokens=state["memory_max_tokens"],
                        model_name=state.get("model_name") or "",
                        repair=state["repair"],
                    )
                    continue

                state["llm_json"] = parsed
                validation = self._fallback_validate(state)
                if validation.ok:
                    for t in parsed.translations:
                        state["translations"][t.id] = t.text
                    state.update(self._fallback_update_memory(state))
                    state["cursor"] += len(state["batch_ids"])
                    break

                attempt += 1
                if attempt >= max_attempts:
                    raise ValueError(validation.error or "validation failed")
                state["repair"] = {"error": validation.error, "expected_ids": state["batch_ids"]}
                state["batch_payload"] = self._build_payload(
                    memory_summary=state.get("memory_summary", ""),
                    memory_glossary=state.get("memory_glossary", []),
                    items=state.get("batch_items", []),
                    memory_max_tokens=state["memory_max_tokens"],
                    model_name=state.get("model_name") or "",
                    repair=state["repair"],
                )

        state.update(self._fallback_assemble(state))
        self._fallback_final_validate(state)
        return state

    async def _fallback_select_batch(self, state: dict[str, Any]) -> dict[str, Any]:
        doc: SegmentedDocument = state["doc"]
        cursor: int = state["cursor"]
        chunk_tokens: int = state["chunk_tokens"]
        model_name: str = state.get("model_name") or ""
        items = doc.translatable_items[cursor:]
        picked: list[TranslatableItem] = []
        total = 0
        for it in items:
            add_tokens = count_tokens(it.text, model_name) + 40
            if picked and total + add_tokens > chunk_tokens:
                break
            picked.append(it)
            total += add_tokens
            if total >= chunk_tokens:
                break
        batch_ids = [it.id for it in picked]
        batch_items = [{"id": it.id, "text": it.text} for it in picked]
        payload = self._build_payload(
            memory_summary=state.get("memory_summary", ""),
            memory_glossary=state.get("memory_glossary", []),
            items=batch_items,
            memory_max_tokens=state["memory_max_tokens"],
            model_name=model_name,
            repair=state.get("repair"),
        )
        return {"batch_ids": batch_ids, "batch_items": batch_items, "batch_payload": payload}

    def _fallback_parse(self, raw: str) -> StructuredLLMOutput:
        s = raw.strip()
        if s.startswith("```"):
            lines = s.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            s = "\n".join(lines).strip()
        data = json.loads(s)
        return StructuredLLMOutput.model_validate(data)

    def _fallback_validate(self, state: dict[str, Any]) -> _Validation:
        doc: SegmentedDocument = state["doc"]
        id_to_placeholders = {it.id: set(it.placeholders.keys()) for it in doc.translatable_items}
        parsed: StructuredLLMOutput = state["llm_json"]
        batch_ids: list[str] = state["batch_ids"]
        got_ids = [t.id for t in parsed.translations]
        if sorted(got_ids) != sorted(batch_ids) or len(got_ids) != len(batch_ids):
            return _Validation(ok=False, error=f"IDs mismatch: expected={batch_ids}, got={got_ids}")
        for t in parsed.translations:
            expected = id_to_placeholders.get(t.id, set())
            missing = [p for p in expected if p not in (t.text or "")]
            if missing:
                return _Validation(ok=False, error=f"Missing placeholders for {t.id}: {missing}")
            unknown = [p for p in PLACEHOLDER_RE.findall(t.text or "") if p not in expected]
            if unknown:
                return _Validation(ok=False, error=f"Unknown placeholders for {t.id}: {unknown}")
        return _Validation(ok=True, error=None)

    def _fallback_update_memory(self, state: dict[str, Any]) -> dict[str, Any]:
        parsed: StructuredLLMOutput = state["llm_json"]
        memory_max_tokens: int = state["memory_max_tokens"]
        model_name: str = state.get("model_name") or ""
        summary = trim_to_tokens((parsed.memory.summary or "").strip(), model_name, memory_max_tokens).strip()
        old_glossary: list[dict[str, str]] = list(state.get("memory_glossary") or [])
        new_items = [{"source": (g.source or "").strip(), "target": (g.target or "").strip()} for g in parsed.memory.glossary]
        merged: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in (old_glossary + new_items)[-100:]:
            key = (item.get("source") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= 50:
                break
        return {"memory_summary": summary, "memory_glossary": merged}

    def _fallback_assemble(self, state: dict[str, Any]) -> dict[str, Any]:
        doc: SegmentedDocument = state["doc"]
        translations: dict[str, str] = state.get("translations") or {}
        fm_text = ""
        if doc.front_matter is not None:
            fm_text, _ = apply_front_matter_targets(doc.front_matter, translations, doc.front_matter_targets)
        out_parts: list[str] = []
        for seg in doc.body_segments:
            if seg.translatable_id:
                translated = translations.get(seg.translatable_id, seg.template or "")
                out_parts.append(unmask_text(translated, seg.placeholders))
            else:
                out_parts.append(seg.raw)
        return {"final_text": fm_text + "".join(out_parts)}

    def _fallback_final_validate(self, state: dict[str, Any]) -> None:
        final_text = state.get("final_text") or ""
        leftovers = PLACEHOLDER_RE.findall(final_text)
        if leftovers:
            raise ValueError(f"Leftover placeholders: {leftovers[:5]}")

    async def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(f"langchain-openai is required for structured_graph mode: {e}")

        provider = self._ctx.get_provider()
        config = self._ctx.get_config()

        # Prefer JSON-only mode when supported by the provider/model.
        kwargs: dict[str, Any] = {
            "temperature": float(config.temperature),
            "model_kwargs": {"response_format": {"type": "json_object"}},
        }

        # best-effort compatibility across versions
        for model_kw in ("model", "model_name"):
            kwargs[model_kw] = provider.model
            break
        for key_kw in ("api_key", "openai_api_key"):
            kwargs[key_kw] = provider.api_key
            break
        for base_kw in ("base_url", "openai_api_base"):
            kwargs[base_kw] = provider.base_url
            break
        for timeout_kw in ("timeout", "request_timeout"):
            kwargs[timeout_kw] = float(config.request_timeout)
            break

        try:
            return ChatOpenAI(**kwargs)
        except TypeError:
            # try alternate naming
            kwargs2 = dict(kwargs)
            if "model" in kwargs2:
                kwargs2["model_name"] = kwargs2.pop("model")
            if "api_key" in kwargs2:
                kwargs2["openai_api_key"] = kwargs2.pop("api_key")
            if "base_url" in kwargs2:
                kwargs2["openai_api_base"] = kwargs2.pop("base_url")
            if "timeout" in kwargs2:
                kwargs2["request_timeout"] = kwargs2.pop("timeout")
            try:
                return ChatOpenAI(**kwargs2)
            except Exception:
                # Fallback: disable JSON mode if unsupported.
                kwargs2["model_kwargs"] = {}
                return ChatOpenAI(**kwargs2)
        except Exception:
            # Fallback: disable JSON mode if unsupported.
            kwargs_plain = dict(kwargs)
            kwargs_plain["model_kwargs"] = {}
            return ChatOpenAI(**kwargs_plain)

    def _build_messages(self, *, system_prompt: str, source_lang: str, target_lang: str, payload: str) -> tuple[Any, Any]:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
        except Exception as e:
            raise RuntimeError(f"langchain-core is required for structured_graph mode: {e}")

        rules = (
            "\n\nYou MUST respond with a single JSON object only.\n"
            "If the System Prompt conflicts with any rule below, follow the rules below.\n"
            "Do not include markdown fences or any extra text.\n"
            "Keep all placeholders like [[YIMO_PH_000001]] EXACTLY unchanged.\n"
            "Do not add or remove placeholders.\n"
            "Translate only natural language parts; keep Markdown structure and line breaks as much as possible.\n"
            "You MUST return a translation for every requested id. If uncertain, output the best-effort translation; "
            "if you really cannot translate, return the input text unchanged for that id.\n"
        )
        sys = f"{system_prompt}{rules}"
        return SystemMessage(content=sys), HumanMessage(content=payload)

    def _build_payload(
        self,
        *,
        memory_summary: str,
        memory_glossary: list[dict[str, str]],
        items: list[dict[str, str]],
        memory_max_tokens: int,
        model_name: str,
        repair: dict[str, Any] | None,
    ) -> str:
        summary = trim_to_tokens((memory_summary or "").strip(), model_name, int(memory_max_tokens)).strip()
        required_ids = [it.get("id") for it in items if isinstance(it, dict) and it.get("id")]
        payload: dict[str, Any] = {
            "memory": {"summary": summary, "glossary": memory_glossary[-50:]},
            "items": items,
            "required_ids": required_ids,
            "output_schema": {
                "translations": [{"id": "b0001", "text": "..."}, {"id": "b0002", "text": "..."}],
                "memory": {"summary": "...", "glossary": [{"source": "...", "target": "..."}]},
            },
            "rules": {
                "output_json_only": True,
                "must_include_keys": ["translations", "memory"],
                "must_translate_all_ids": True,
                "keep_placeholders_prefix": "[[YIMO_PH_",
            },
        }
        if repair is not None:
            payload["rules"]["repair"] = repair
        return json.dumps(payload, ensure_ascii=False)

    def _ensure_not_stopped(self, state: dict[str, Any]) -> None:
        flag: threading.Event | None = state.get("stop_flag")
        if flag is not None and flag.is_set():
            raise asyncio.CancelledError()
