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
        from langgraph.graph import END, StateGraph  # type: ignore

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
            if not hasattr(llm, "with_structured_output"):
                raise RuntimeError("LLM does not support with_structured_output()")

            try:
                structured_llm = llm.with_structured_output(
                    StructuredLLMOutput,
                    include_raw=True,
                )
            except Exception as e:
                raise RuntimeError(f"Failed to configure structured output: {e}")

            llm_raw = ""
            try:
                result = await structured_llm.ainvoke([sys_msg, user_msg])
            except Exception as e:
                return {"llm_raw": str(e), "llm_json": None, "validation": _Validation(ok=False, error=f"Output schema error: {e}")}

            parsed: StructuredLLMOutput | None = None
            parsing_error: Any | None = None

            if isinstance(result, StructuredLLMOutput):
                parsed = result
            elif isinstance(result, dict):
                parsing_error = result.get("parsing_error")
                llm_raw = self._summarize_llm_raw(result.get("raw"))
                parsed_any = result.get("parsed")
                if isinstance(parsed_any, StructuredLLMOutput):
                    parsed = parsed_any
                elif parsed_any is not None:
                    try:
                        parsed = StructuredLLMOutput.model_validate(parsed_any)
                    except Exception as e:
                        parsing_error = parsing_error or e
                        parsed = None
            else:
                llm_raw = self._summarize_llm_raw(result)

            if parsing_error is not None:
                return {"llm_raw": llm_raw, "llm_json": None, "validation": _Validation(ok=False, error=f"Output schema error: {parsing_error}")}
            if parsed is None:
                return {"llm_raw": llm_raw, "llm_json": None, "validation": _Validation(ok=False, error="No parsed output")}
            return {"llm_raw": llm_raw, "llm_json": parsed, "validation": _Validation(ok=True, error=None)}

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
                    "Output must conform to the requested schema (no markdown fences, no explanations).",
                    "Return translations for all expected ids, exactly once each.",
                    "Do not remove or alter any placeholders like [[YIMO_PH_000001]].",
                    "The output MUST include both keys: translations (array) and memory (object).",
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
        g.add_edge("llm_translate", "validate_llm_output")
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

    async def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        try:
            from langchain_openai import ChatOpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError(f"langchain-openai is required for structured_graph mode: {e}")

        provider = self._ctx.get_provider()
        config = self._ctx.get_config()

        kwargs: dict[str, Any] = {"temperature": float(config.temperature)}

        kwargs["model"] = provider.model
        kwargs["api_key"] = provider.api_key
        kwargs["base_url"] = provider.base_url
        kwargs["timeout"] = float(config.request_timeout)

        try:
            return ChatOpenAI(**kwargs)
        except TypeError:
            # try alternate naming
            kwargs2 = dict(kwargs)
            kwargs2["model_name"] = kwargs2.pop("model", provider.model)
            kwargs2["openai_api_key"] = kwargs2.pop("api_key", provider.api_key)
            kwargs2["openai_api_base"] = kwargs2.pop("base_url", provider.base_url)
            kwargs2["request_timeout"] = kwargs2.pop("timeout", float(config.request_timeout))
            return ChatOpenAI(**kwargs2)

    def _build_messages(self, *, system_prompt: str, source_lang: str, target_lang: str, payload: str) -> tuple[Any, Any]:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
        except Exception as e:
            raise RuntimeError(f"langchain-core is required for structured_graph mode: {e}")

        rules = (
            "\n\nYou MUST produce an output that conforms to the requested schema.\n"
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

    def _summarize_llm_raw(self, raw: Any) -> str:
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        content = getattr(raw, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        tool_calls = getattr(raw, "tool_calls", None)
        if tool_calls:
            try:
                return json.dumps({"tool_calls": tool_calls}, ensure_ascii=False)
            except Exception:
                return str(tool_calls)
        additional_kwargs = getattr(raw, "additional_kwargs", None)
        if additional_kwargs:
            try:
                return json.dumps({"additional_kwargs": additional_kwargs}, ensure_ascii=False)
            except Exception:
                return str(additional_kwargs)
        try:
            return str(raw)
        except Exception:
            return ""

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
