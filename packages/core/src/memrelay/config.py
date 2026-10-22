"""MemRelay configuration and per-OS locations.

Locations (all overridable with the MEMRELAY_HOME env var, which tests use):
- config:  platformdirs.user_config_dir("memrelay")  -> config.toml
- data:    platformdirs.user_data_dir("memrelay")    -> per-device state (capture cursors,
           client-config backups, audit log). Never synced, unlike the vault.
- vault:   ~/MemRelay by default (the Markdown memory, safe to sync with Git/Syncthing).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import platformdirs

APP = "memrelay"


def _home_override() -> Path | None:
    v = os.environ.get("MEMRELAY_HOME")
    return Path(v).expanduser() if v else None


def config_dir() -> Path:
    h = _home_override()
    return h / "config" if h else Path(platformdirs.user_config_dir(APP, appauthor=False))


def data_dir() -> Path:
    h = _home_override()
    return h / "data" if h else Path(platformdirs.user_data_dir(APP, appauthor=False))


def default_vault() -> Path:
    h = _home_override()
    return h / "vault" if h else Path.home() / "MemRelay"



@dataclass
class ReviewConfig:
    """How proposals become memories. Default ``auto`` = automatic with safety rails."""

    mode: str = "auto"  # auto | assist | strict
    min_confidence: float = 0.55
    trusted_capture_agents: list[str] = field(
        default_factory=lambda: ["claude-code", "codex", "gemini-cli", "cursor"]
    )
    trusted_mcp_agents: list[str] = field(default_factory=lambda: ["*"])
    auto_memrelay_generated: bool = True
    auto_export_import: bool = True
    export_min_confidence: float = 0.7
    notify: bool = True

@dataclass
class LLMConfig:
    """OpenAI-compatible endpoint used by the optional LLM extractor."""

    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"  # name of the env var, never the key itself
    model_override: str = ""  # with a preset (deepseek/qwen/kimi/ollama): use this model instead


@dataclass
class Config:
    vault: Path = field(default_factory=default_vault)
    bm_project: str = "memrelay"
    bm_command: list[str] = field(default_factory=lambda: ["basic-memory"])
    # Isolated Basic Memory state so we never touch a user's existing BM setup.
    # Set to "" to share the user's default Basic Memory config instead.
    bm_config_dir: str | None = None
    # Storage engine: basic-memory (default) | local | openviking (stub; see backends/openviking.py)
    # Aliases: basic_memory, bm, ov. OpenViking never exposes forget through the gateway.
    backend: str = "basic-memory"
    openviking_base_url: str = ""  # e.g. https://host — unused until OV client is wired
    extractor: str = "stub"  # "stub" | "openai"
    hf_endpoint: str = "auto"  # "auto" | "off" | URL (see memrelay/hf.py)
    # Persona layer LLM: "off" (rule-based, offline) | "openai-compat" (uses [llm]) |
    # a preset: openai | deepseek | qwen | kimi | ollama  (see memrelay/llm.py)
    persona_llm: str = "off"
    # Highest visibility answer_as_me may use for your own agents: public|friends|work|private
    twin_visibility: str = "private"
    llm: LLMConfig = field(default_factory=LLMConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)

    @property
    def path(self) -> Path:
        return config_dir() / "config.toml"

    def resolved_bm_config_dir(self) -> Path | None:
        if self.bm_config_dir == "":
            return None
        if self.bm_config_dir:
            return Path(self.bm_config_dir).expanduser()
        return data_dir() / "basic-memory"

    # --- persistence -------------------------------------------------------
    @classmethod
    def load(cls) -> Config:
        p = config_dir() / "config.toml"
        if not p.exists():
            return cls()
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
        llm = LLMConfig(**{k: v for k, v in raw.pop("llm", {}).items()
                           if k in LLMConfig.__dataclass_fields__})
        review = ReviewConfig(**{k: v for k, v in raw.pop("review", {}).items()
                                 if k in ReviewConfig.__dataclass_fields__})
        if "vault" in raw:
            raw["vault"] = Path(raw["vault"]).expanduser()
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__ and k not in ("llm", "review")}
        return cls(**known, llm=llm, review=review)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        d = asdict(self)
        llm = d.pop("llm")
        review = d.pop("review")
        lines = []
        for k, v in d.items():
            if v is None:
                continue
            lines.append(f"{k} = {_toml(v)}")
        lines.append("\n[llm]")
        lines += [f"{k} = {_toml(v)}" for k, v in llm.items()]
        lines.append("\n[review]")
        lines += [f"{k} = {_toml(v)}" for k, v in review.items()]
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.path


def _toml(v: object) -> str:
    import json

    if isinstance(v, Path):
        v = v.as_posix()
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)  # JSON strings are valid TOML basic strings
