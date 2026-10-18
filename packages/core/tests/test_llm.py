import json

import httpx
import pytest

from memrelay.config import Config
from memrelay.llm import PRESETS, OpenAICompatLLM, StubLLM, get_llm, parse_json


def test_openai_compat_request_shape():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": 1}'}}]})

    llm = OpenAICompatLLM("https://api.deepseek.com/v1/", "deepseek-chat", "k",
                          client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert llm.complete("sys", "hi", json_mode=True) == '{"ok": 1}'
    assert seen["url"] == "https://api.deepseek.com/v1/chat/completions" and seen["auth"] == "Bearer k"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    no_key = OpenAICompatLLM("http://localhost:11434/v1", "m", None,
                             client=httpx.Client(transport=httpx.MockTransport(handler)))
    no_key.complete("s", "u")
    assert seen["auth"] is None and "response_format" not in seen["body"]


def test_get_llm_modes(monkeypatch):
    cfg = Config()
    assert get_llm(cfg) is None  # default: offline
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dk")
    cfg.persona_llm = "deepseek"
    m = get_llm(cfg)
    assert m.base_url == PRESETS["deepseek"]["base_url"] and m.model == "deepseek-chat" and m.api_key == "dk"
    cfg.persona_llm, cfg.llm.model_override = "ollama", "llama3.1"
    m = get_llm(cfg)
    assert m.base_url.startswith("http://localhost:11434") and m.model == "llama3.1" and m.api_key is None
    cfg.persona_llm = "openai-compat"
    cfg.llm.base_url, cfg.llm.model = "https://my.example/v1", "x"
    assert get_llm(cfg).base_url == "https://my.example/v1"
    cfg.persona_llm = "nope"
    with pytest.raises(KeyError):
        get_llm(cfg)


def test_config_roundtrip_persona_llm(home):
    c = Config(persona_llm="qwen")
    c.llm.model_override = "qwen-max"
    c.save()
    c2 = Config.load()
    assert c2.persona_llm == "qwen" and c2.llm.model_override == "qwen-max"
    assert "API_KEY" not in c2.path.read_text(encoding="utf-8").split("api_key_env")[0]


def test_parse_json_and_stub():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json("text {\"a\": 2} tail") == {"a": 2}
    assert parse_json("[1,2]") == {} and parse_json("nope") == {}
    s = StubLLM(["one", "two"])
    assert s.complete("a", "b") == "one" and s.complete("a", "b") == "two" and s.complete("a", "b") == ""
    assert StubLLM(lambda sy, u: u.upper()).complete("s", "hi") == "HI"
