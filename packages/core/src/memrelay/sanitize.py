"""Secret redaction and prompt-injection flagging for anything entering the inbox."""

from __future__ import annotations

import re

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "anthropic_key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "cn_id_card": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "password_assign": re.compile(r"(?i)\b(?:password|passwd|pwd|密码)\s*[:=：]\s*\S+"),
}
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"ignore (?:all |any )?(?:previous|prior|above) (?:instructions|rules)",
        r"disregard (?:the )?(?:system|previous) prompt",
        r"you are now (?:a|an|in) ",
        r"^\s*(?:system|assistant)\s*:",
        r"忽略(?:之前|以上|前面|所有)的?(?:指令|规则|提示)",
        r"你现在(?:是|扮演)",
        r"<\s*/?\s*(?:system|instructions?)\s*>",
    )
]


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, kinds_found)."""
    found: list[str] = []
    for kind, pat in SECRET_PATTERNS.items():
        if pat.search(text):
            found.append(kind)
            text = pat.sub(f"[REDACTED:{kind}]", text)

    def _card(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            found.append("card_number")
            return "[REDACTED:card_number]"
        return m.group(0)

    text = _CARD.sub(_card, text)
    return text, sorted(set(found))


def injection_flags(text: str) -> list[str]:
    return ["possible_injection"] if any(p.search(text) for p in INJECTION_PATTERNS) else []
