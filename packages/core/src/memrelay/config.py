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
class LLMConfig:
    """OpenAI-compatible endpoint used by the optional LLM extractor."""

    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"  # name of the env var, never the key itself


@dataclass
class Config:
    vault: Path = field(default_factory=default_vault)
    bm_project: str = "memrelay"
    bm_command: list[str] = field(default_factory=lambda: ["basic-memory"])
    # Isolated Basic Memory state so we never touch a user's existing BM setup.
    # Set to "" to share the user's default Basic Memory config instead.
    bm_config_dir: str | None = None
    backend: str = "basic-memory"  # "basic-memory" | "local"
    extractor: str = "stub"  # "stub" | "openai"
    hf_endpoint: str = "auto"  # "auto" | "off" | URL (see memrelay/hf.py)
    llm: LLMConfig = field(default_factory=LLMConfig)

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
        llm = LLMConfig(**raw.pop("llm", {}))
        if "vault" in raw:
            raw["vault"] = Path(raw["vault"]).expanduser()
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known, llm=llm)

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        d = asdict(self)
        llm = d.pop("llm")
        lines = []
        for k, v in d.items():
            if v is None:
                continue
            lines.append(f"{k} = {_toml(v)}")
        lines.append("\n[llm]")
        lines += [f"{k} = {_toml(v)}" for k, v in llm.items()]
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
