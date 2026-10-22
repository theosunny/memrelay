"""Pluggable memory engines behind the gateway (search / get / remember).

Default remains Basic Memory (separate process). OpenViking and similar engines are optional
backends — see docs/comparison.md. The MemRelay gateway never exposes delete/forget.
"""

from __future__ import annotations

import logging

from ..config import Config
from ..vault import Vault
from .base import MemoryBackend, SearchBackend
from .basic_memory import BasicMemoryBackend
from .local import LocalBackend
from .openviking import OpenVikingBackend

log = logging.getLogger(__name__)

# Config aliases: hyphen and underscore both accepted.
BACKEND_ALIASES = {
    "basic-memory": "basic_memory",
    "basic_memory": "basic_memory",
    "bm": "basic_memory",
    "local": "local",
    "openviking": "openviking",
    "ov": "openviking",
}


def normalize_backend(name: str) -> str:
    return BACKEND_ALIASES.get((name or "").strip().lower(), (name or "").strip().lower())


def make_backend(cfg: Config, vault: Vault) -> MemoryBackend:
    kind = normalize_backend(cfg.backend)
    if kind == "openviking":
        return OpenVikingBackend(cfg, vault)
    if kind == "basic_memory":
        if BasicMemoryBackend.available(cfg):
            return BasicMemoryBackend(cfg, vault)
        log.warning("basic-memory not found on PATH; falling back to local keyword search")
        return LocalBackend(vault)
    if kind == "local":
        return LocalBackend(vault)
    log.warning("unknown backend %r; falling back to local", cfg.backend)
    return LocalBackend(vault)


__all__ = [
    "MemoryBackend",
    "SearchBackend",
    "BasicMemoryBackend",
    "LocalBackend",
    "OpenVikingBackend",
    "make_backend",
    "normalize_backend",
]
