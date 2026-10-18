"""Pluggable chat LLM for the persona layer (reflection, consolidation, twin answers).

Any OpenAI-compatible Chat Completions endpoint works. Presets (base URLs from each vendor's
public OpenAI-compatibility docs):
- openai   https://api.openai.com/v1
- deepseek https://api.deepseek.com/v1
- qwen     https://dashscope.aliyuncs.com/compatible-mode/v1   (DashScope compatible mode)
- kimi     https://api.moonshot.cn/v1
- ollama   http://localhost:11434/v1                         (local, no key)

The API key is read from the env var named in config (`api_key_env`), never stored.
Tests use `StubLLM`; no network and no real key is ever needed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Protocol

import httpx

PRESETS: dict[str, dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key_env": "OPENAI_API_KEY"},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
             "api_key_env": "DASHSCOPE_API_KEY"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "api_key_env": "MOONSHOT_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b", "api_key_env": ""},
}


class ChatLLM(Protocol):
    name: str

    def complete(self, system: str, user: str, json_mode: bool = False) -> str: ...


class OpenAICompatLLM:
    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 client: httpx.Client | None = None, temperature: float = 0.2):
        self.base_url, self.model, self.api_key = base_url.rstrip("/"), model, api_key
        self.client = client or httpx.Client(timeout=120)
        self.temperature = temperature
        self.name = f"openai-compat:{model}"

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        body: dict = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        r = self.client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""


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
