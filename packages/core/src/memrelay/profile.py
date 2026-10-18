"""Core profile generator (no LLM): reviewed memories -> profile/core-profile.md.

The core profile is the small, always-in-context block (Letta/MemGPT "core memory") that the
gateway serves via `get_profile` and that can be pasted into agents without MCP.
Every line links back to its source note, so provenance is never lost.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .schema import Note, Sensitivity, Status, effective_confidence
from .vault import Vault

SECTIONS = [
    ("fact", "我是谁 / About me"),
    ("project", "当前重点 / Current focus"),
    ("preference", "偏好 / Preferences"),
    ("principle", "原则 / Principles"),
]
PER_SECTION = {"fact": 12, "project": 5, "preference": 12, "principle": 8}
MIN_CONF = 0.5
MAX_CHARS = 4000


def _eligible(note: Note, today: dt.date) -> bool:
    return (
        note.status == Status.active.value
        and note.sensitivity == Sensitivity.normal.value
        and not (note.valid_to and note.valid_to <= today)
        and effective_confidence(note, today) >= MIN_CONF
    )


def _line(note: Note) -> str:
    text = " ".join(note.body.split("\n> ")[0].split())  # drop evidence quote
    return text if len(text) <= 160 else text[:157] + "…"


def build_profile(vault: Vault, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    groups: dict[str, list[tuple[float, int, str, Note]]] = {k: [] for k, _ in SECTIONS}
    for path, note in vault.iter_notes():
        if note.type in groups and _eligible(note, today):
            groups[note.type].append(
                (effective_confidence(note, today), note.importance, vault.rel(path), note)
            )
    lines = [
        "---",
        "title: Core Profile",
        "type: profile",
        "status: active",
        "source_agent: memrelay-profile",
        "source_channel: generated",
        f"captured_at: '{dt.datetime.now().astimezone().replace(microsecond=0).isoformat()}'",
        "---",
        "",
        "# 核心画像 / Core Profile",
        "",
        f"_由 MemRelay 根据已审核记忆自动生成于 {today.isoformat()}；每条后面是来源笔记。_",
        "",
    ]
    for key, heading in SECTIONS:
        items = sorted(groups[key], key=lambda x: (-x[1], -x[0], x[2]))[: PER_SECTION[key]]
        if not items:
            continue
        lines += [f"## {heading}", ""]
        for _c, _i, rel, note in items:
            lines.append(f"- {_line(note)}  ([[{rel.removesuffix('.md')}]])")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit("\n", 1)[0] + "\n- …\n"
    return text


def profile_path(vault: Vault) -> Path:
    return vault.root / "profile" / "core-profile.md"


def is_locked(vault: Vault) -> bool:
    p = profile_path(vault)
    if not p.exists():
        return False
    try:
        return bool(getattr(Note.from_markdown(p.read_text(encoding="utf-8")), "locked", False))
    except Exception:
        return True  # hand-written file without our frontmatter: never overwrite


def write_profile(vault: Vault, text: str) -> Path:
    if is_locked(vault):
        raise PermissionError("core-profile.md is locked or hand-written; not overwriting")
    p = profile_path(vault)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def export_plain(text: str) -> str:
    """Profile without frontmatter/links, for pasting into agents that lack MCP."""
    body = text.split("---", 2)[-1]
    import re

    body = re.sub(r"\s*\(\[\[[^\]]+\]\]\)", "", body)
    return body.strip() + "\n"
