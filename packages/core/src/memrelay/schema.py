"""Memory note schema: Markdown + YAML frontmatter, compatible with Basic Memory.

Basic Memory reads `title`, `type`, `tags`, `permalink` from frontmatter and keeps any other
keys as metadata, so provenance/temporal fields live alongside them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from enum import Enum
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    event = "event"
    fact = "fact"
    preference = "preference"
    procedure = "procedure"
    person = "person"
    project = "project"
    principle = "principle"
    reflection = "reflection"
    profile = "profile"


class Status(str, Enum):
    proposed = "proposed"
    active = "active"
    superseded = "superseded"
    rejected = "rejected"
    archived = "archived"


class Visibility(str, Enum):
    public = "public"
    friends = "friends"
    work = "work"
    private = "private"


class Sensitivity(str, Enum):
    normal = "normal"
    personal = "personal"
    secret = "secret"


def now() -> dt.datetime:
    return dt.datetime.now().astimezone().replace(microsecond=0)


class Note(BaseModel):
    model_config = ConfigDict(use_enum_values=True, extra="allow", validate_default=True)

    title: str
    type: MemoryType = MemoryType.fact
    body: str = Field(default="", exclude=True)
    tags: list[str] = Field(default_factory=list)
    status: Status = Status.proposed
    visibility: Visibility = Visibility.private
    sensitivity: Sensitivity = Sensitivity.normal
    confidence: float = Field(default=0.6, ge=0, le=1)
    importance: int = Field(default=5, ge=1, le=10)
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None
    superseded_by: str | None = None
    last_confirmed: dt.date | None = None
    # provenance
    source_agent: str = "unknown"
    source_channel: str = "unknown"  # mcp | local-capture | export-import | manual | share-sheet
    source_ref: str | None = None
    captured_at: dt.datetime = Field(default_factory=now)
    extractor: str | None = None
    evidence: int = 1
    flags: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------
    def fingerprint(self) -> str:
        """Content hash used for exact/near-exact dedup (type + normalised text)."""
        norm = re.sub(r"\s+", " ", f"{self.title} {self.body}").strip().lower()
        norm = re.sub(r"[。．.!！?？,，;；:：\"'“”‘’]", "", norm)
        return hashlib.sha256(f"{self.type}|{norm}".encode()).hexdigest()[:16]

    def frontmatter(self) -> dict[str, Any]:
        d = self.model_dump(mode="json", exclude_none=True)
        for k in ("tags", "flags"):
            if not d.get(k):
                d.pop(k, None)
        return d

    def to_markdown(self) -> str:
        fm = yaml.safe_dump(self.frontmatter(), allow_unicode=True, sort_keys=False).strip()
        body = self.body.strip()
        return f"---\n{fm}\n---\n\n{body}\n"

    @classmethod
    def from_markdown(cls, text: str) -> "Note":
        m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.S)
        if not m:
            raise ValueError("missing YAML frontmatter")
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            raise ValueError("frontmatter must be a mapping")
        meta.pop("body", None)
        return cls(**meta, body=m.group(2).strip())


_SAFE = re.compile(r"[^\w\u4e00-\u9fff-]+", re.U)


def slugify(title: str, max_len: int = 60) -> str:
    s = _SAFE.sub("-", title.strip().lower()).strip("-_")
    s = re.sub(r"-{2,}", "-", s)
    return (s[:max_len].rstrip("-") or "note")


def effective_confidence(note: Note, today: dt.date | None = None) -> float:
    """Confidence with exponential decay since last confirmation (persona-design §2.7)."""
    half_life = {
        "fact": 365, "preference": 180, "project": 90, "procedure": 365,
        "person": 365, "principle": 730, "profile": 365, "reflection": 180,
    }.get(str(note.type))
    if half_life is None:  # events don't decay
        return note.confidence
    today = today or dt.date.today()
    base = note.last_confirmed or note.captured_at.date()
    days = max((today - base).days, 0)
    return round(note.confidence * 0.5 ** (days / half_life), 4)
