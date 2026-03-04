from __future__ import annotations

from pydantic import BaseModel, Field


class GlossaryItem(BaseModel):
    source: str = Field(default="")
    target: str = Field(default="")


class MemoryBlock(BaseModel):
    summary: str = Field(default="")
    glossary: list[GlossaryItem] = Field(default_factory=list)


class TranslationPair(BaseModel):
    id: str
    text: str


class StructuredLLMOutput(BaseModel):
    translations: list[TranslationPair]
    memory: MemoryBlock = Field(default_factory=MemoryBlock)

