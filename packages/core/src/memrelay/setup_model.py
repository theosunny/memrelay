import json
import os
from pathlib import Path

from .config import Config
from .llm import PRESETS
from .vault import Vault

PROVIDERS = ("openai", "deepseek", "qwen", "kimi", "glm", "ollama")


def configure_model(home: Path, provider: str, model: str) -> dict:
    if provider not in PRESETS or provider not in PROVIDERS:
        raise ValueError("provider must be one of: " + ", ".join(PROVIDERS))
    previous = os.environ.get("MEMRELAY_HOME")
    os.environ["MEMRELAY_HOME"] = str(home)
    try:
        cfg = Config.load()
        cfg.persona_llm = provider
        cfg.backend = "local"
        cfg.llm.model_override = model.strip()
        cfg.llm.api_key_env = PRESETS[provider]["api_key_env"]
        Vault(cfg.vault).init()
        cfg.save()
        return {
            "provider": provider,
            "model": cfg.llm.model_override,
            "api_key_env": cfg.llm.api_key_env,
            "vault": str(cfg.vault),
        }
    finally:
        if previous is None:
            os.environ.pop("MEMRELAY_HOME", None)
        else:
            os.environ["MEMRELAY_HOME"] = previous


def main_json(home: Path, provider: str, model: str) -> None:
    print(json.dumps(configure_model(home, provider, model), ensure_ascii=False), flush=True)
