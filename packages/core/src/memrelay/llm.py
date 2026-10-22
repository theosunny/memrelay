"""Pluggable chat LLM for the persona layer (reflection, consolidation, twin answers).

Any OpenAI-compatible Chat Completions endpoint works. Presets (base URLs from each vendor's
public OpenAI-compatibility docs):
- openai   https://api.openai.com/v1
- deepseek https://api.deepseek.com/v1
- qwen     https://dashscope.aliyuncs.com/compatible-mode/v1   (DashScope compatible mode)
- kimi     https://api.moonshot.cn/v1
- ollama   http://localhost:11434/v1                         (local, no key)
- glm      https://open.bigmodel.cn/api/coding/paas/v4       (Zhipu Coding Plan; use coding-plan keys)

The API key is read from the env var named in config (`api_key_env`), never stored.
Tests use `StubLLM`; no network and no real key is ever needed.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Protocol

import httpx

log = logging.getLogger(__name__)

PRESETS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
             "api_key_env": "DASHSCOPE_API_KEY"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "api_key_env": "MOONSHOT_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b", "api_key_env": ""},
    # Zhipu GLM Coding Plan OpenAI-compatible endpoint — coding-plan API keys only (not general GLM keys).
    "glm": {"base_url": "https://open.bigmodel.cn/api/coding/paas/v4", "model": "glm-5.3-flash",
            "api_key_env": "GLM_API_KEY"},
}


class ChatLLM(Protocol):
    name: str

    def complete(self, system: str, user: str, json_mode: bool = False) -> str: ...


def looks_like_json(text: str) -> bool:
    """True if text is plausibly a JSON object/array (optionally fenced)."""
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("```"):
        return True
    return t[0] in "{["


def message_text(message: dict) -> str:
    """Pick assistant text from a chat completion message.

    Some reasoning models (e.g. GLM coding) put tokens in ``reasoning_content`` and leave
    ``content`` empty. Only fall back to reasoning when it looks like JSON we can parse.
    """
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):  # multimodal-style parts
        parts = [p.get("text", "") for p in content if isinstance(p, dict)]
        joined = "".join(parts).strip()
        if joined:
            return joined
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and looks_like_json(reasoning):
        return reasoning
    return ""


class OpenAICompatLLM:
    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 client: httpx.Client | None = None, temperature: float = 0.2,
                 max_tokens: int = 1024):
        self.base_url, self.model, self.api_key = base_url.rstrip("/"), model, api_key
        self.client = client or httpx.Client(timeout=120)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.name = f"openai-compat:{model}"

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        body: dict = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        url = f"{self.base_url}/chat/completions"
        r = self.client.post(url, headers=headers, json=body)
        # Some APIs (GLM coding) reject response_format=json_object — retry without it.
        if r.status_code >= 400 and json_mode and "response_format" in body:
            err = (r.text or "")[:300].lower()
            if any(k in err for k in ("response_format", "json_object", "unsupported", "invalid", "not support")):
                body.pop("response_format", None)
                log.debug("retrying chat/completions without response_format (%s)", r.status_code)
                r = self.client.post(url, headers=headers, json=body)
            elif r.status_code == 400:
                # Broad fallback: 400 with json_mode often means format not supported
                body.pop("response_format", None)
                log.debug("retrying chat/completions without response_format after 400")
                r = self.client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            return ""
        return message_text(msg)


class StubLLM:
    """Deterministic LLM for tests: a fixed reply, a list of replies, or a function."""

    name = "stub-llm"

    def __init__(self, reply: str | list[str] | Callable[[str, str], str] = ""):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        self.calls.append((system, user))
        if callable(self.reply):
            return self.reply(system, user)
        if isinstance(self.reply, list):
            return self.reply.pop(0) if self.reply else ""
        return self.reply


def parse_json(text: str) -> dict:
    """Lenient JSON object parse (models sometimes wrap JSON in ``` fences)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t.split("\n", 1)[1] if "\n" in t else t
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        v = json.loads(t[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return v if isinstance(v, dict) else {}


def get_llm(cfg) -> ChatLLM | None:
    """Return the configured persona LLM, or None for the offline rule-based mode."""
    mode = getattr(cfg, "persona_llm", "off") or "off"
    if mode in ("off", "stub"):
        return None
    llm = cfg.llm
    if mode == "openai-compat":
        base, model, key_env = llm.base_url, llm.model, llm.api_key_env
    elif mode in PRESETS:
        p = PRESETS[mode]
        base, model, key_env = p["base_url"], llm.model_override or p["model"], p["api_key_env"]
    else:
        raise KeyError(f"unknown persona_llm {mode!r}: off | openai-compat | {' | '.join(PRESETS)}")
    return OpenAICompatLLM(base, model, os.environ.get(key_env) if key_env else None)
