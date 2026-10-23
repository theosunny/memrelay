from pathlib import Path

from memrelay.config import Config
from memrelay.setup_model import configure_model


def test_deepseek_writes_preset_and_not_the_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("MEMRELAY_HOME", raising=False)
    info = configure_model(tmp_path, "deepseek", "deepseek-chat")
    assert info["api_key_env"] == "DEEPSEEK_API_KEY"
    text = (tmp_path / "config" / "config.toml").read_text(encoding="utf-8")
    assert 'persona_llm = "deepseek"' in text
    assert 'backend = "local"' in text
    assert "sk-" not in text
    assert (tmp_path / "vault").is_dir()
    monkeypatch.setenv("MEMRELAY_HOME", str(tmp_path))
    loaded = Config.load()
    assert loaded.persona_llm == "deepseek"
    assert loaded.llm.model_override == "deepseek-chat"
    assert loaded.backend == "local"


def test_ollama_allows_empty_env_name(tmp_path: Path):
    info = configure_model(tmp_path, "ollama", "")
    assert info["api_key_env"] == ""


def test_unknown_provider_rejected(tmp_path: Path):
    try:
        configure_model(tmp_path, "claude", "")
    except ValueError as exc:
        assert "openai" in str(exc)
    else:
        raise AssertionError("expected ValueError")
