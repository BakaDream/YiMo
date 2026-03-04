from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=32)
def _get_encoding(model: str | None):
    import tiktoken  # type: ignore

    name = (model or "").strip()
    if name:
        try:
            return tiktoken.encoding_for_model(name)
        except Exception:
            pass
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str | None) -> int:
    enc = _get_encoding(model)
    return len(enc.encode(text or ""))


def trim_to_tokens(text: str, model: str | None, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    enc = _get_encoding(model)
    tokens = enc.encode(text or "")
    if len(tokens) <= max_tokens:
        return text or ""
    return enc.decode(tokens[:max_tokens])

