"""Rule-based extractor: no LLM, deterministic. For tests, offline use, and as a baseline.

Only the USER's own sentences are considered (assistant text is never treated as a fact
about the user).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..capture.base import Message
from .base import Candidate

# Clear first-person preference / fact patterns → confidence 0.7 (above review.min_confidence).
# Weaker / principle heuristics stay at 0.5 so they still need a human or a higher-mode LLM.
RULES: list[tuple[str, float, re.Pattern[str]]] = [
    ("preference", 0.7, re.compile(r"(我(?:更)?(?:喜欢|偏好|习惯|倾向于?|讨厌|不喜欢)[^。！？!?\n]{2,120})")),
    ("preference", 0.7, re.compile(r"(?i)\b(I (?:prefer|like|love|hate|dislike|always|never|usually) [^.!?\n]{3,160})")),
    ("fact", 0.7, re.compile(r"(?:请)?记住[:：,，]?\s*([^。！？!?\n]{2,160})")),
    ("fact", 0.7, re.compile(r"(?i)\bremember(?: that)?[:,]?\s+([^.!?\n]{3,160})")),
    ("fact", 0.7, re.compile(r"(我(?:是|在|住在|来自|负责|用的是|使用)[^。！？!?\n]{2,120})")),
    ("fact", 0.7, re.compile(r"(?i)\b(I(?:'m| am) (?:a|an|the|based in|from|working on) [^.!?\n]{3,160})")),
    ("principle", 0.5, re.compile(r"((?:原则是|我的原则|记住不要|不要重复造轮子)[^。！？!?\n]{0,120})")),
]


class StubExtractor:
    name = "stub@0.1"

    def extract(self, messages: Iterable[Message]) -> list[Candidate]:
        out: list[Candidate] = []
        seen: set[tuple[str, str]] = set()
        for m in messages:
            if m.role != "user":
                continue
            for mtype, conf, pat in RULES:
                for match in pat.finditer(m.text):
                    sent = match.group(1).strip(" ，,。.")
                    key = (mtype, sent.lower())
                    if len(sent) < 3 or key in seen:
                        continue
                    seen.add(key)
                    out.append(Candidate(
                        title=sent[:60], content=sent, type=mtype, confidence=conf,
                        evidence=match.group(0).strip(), source_ref=m.source_ref,
                    ))
        return out
