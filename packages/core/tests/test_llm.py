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
    assert seen["body"]["max_tokens"] == 1024
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
    no_key = OpenAICompatLLM("http://localhost:11434/v1", "m", None,
                             client=httpx.Client(transport=httpx.MockTransport(handler)))
    no_key.complete("s", "u")
    assert seen["auth"] is None and "response_format" not in seen["body"]
    assert seen["body"]["max_tokens"] == 1024


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


def test_glm_preset(monkeypatch):
    monkeypatch.setenv("GLM_API_KEY", "gk")
    cfg = Config(persona_llm="glm")
    m = get_llm(cfg)
    assert m.base_url == PRESETS["glm"]["base_url"]
    assert m.model == "glm-5.3-flash" and m.api_key == "gk"
    assert "coding/paas" in m.base_url


def test_reasoning_content_and_response_format_retry():
    from memrelay.llm import looks_like_json, message_text

    assert looks_like_json('{"a":1}') and looks_like_json("```json\n{}\n```")
    assert not looks_like_json("just thinking") and not looks_like_json("")
    assert message_text({"content": "hi"}) == "hi"
    assert message_text({"content": "", "reasoning_content": '{"ok": true}'}) == '{"ok": true}'
    assert message_text({"content": None, "reasoning_content": "thinking..."}) == ""

    calls = {"n": 0}

    def handler(req: httpx.Request):
        calls["n"] += 1
        body = json.loads(req.content)
        if "response_format" in body:
            return httpx.Response(400, text="response_format json_object unsupported")
        return httpx.Response(200, json={"choices": [{"message": {
            "content": "", "reasoning_content": '{"ok": 1}'}}]})

    llm = OpenAICompatLLM("https://example/v1", "m", "k",
                          client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert llm.complete("s", "u", json_mode=True) == '{"ok": 1}'
    assert calls["n"] == 2
