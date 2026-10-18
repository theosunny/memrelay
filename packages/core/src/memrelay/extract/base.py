"""Extraction interface: messages -> candidate memories (pluggable; LLM optional)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from ..capture.base import Message
from ..schema import MemoryType, Note


@dataclass
class Candidate:
    title: str
    content: str
    type: str = MemoryType.fact.value
    confidence: float = 0.5
    evidence: str | None = None
    source_ref: str | None = None
    valid_from: dt.date | None = None
    tags: list[str] = field(default_factory=list)

    def to_note(self, *, source_agent: str, source_channel: str, extractor: str) -> Note:
        body = self.content.strip()
        if self.evidence and self.evidence.strip() not in body:
            body += f"\n\n> 证据 / evidence: {self.evidence.strip()}"
        return Note(
            title=self.title[:200], type=self.type, body=body, tags=self.tags,
            confidence=self.confidence, valid_from=self.valid_from,
            source_agent=source_agent, source_channel=source_channel,
            source_ref=self.source_ref, extractor=extractor,
        )


class Extractor(Protocol):
    name: str

    def extract(self, messages: Iterable[Message]) -> list[Candidate]: ...


def get_extractor(kind: str, cfg=None) -> Extractor:
    if kind == "stub":
        from .stub import StubExtractor
        return StubExtractor()
    if kind == "openai":
        from .llm import OpenAICompatExtractor
        return OpenAICompatExtractor.from_config(cfg.llm)
    raise KeyError(f"unknown extractor {kind!r} (stub | openai)")
