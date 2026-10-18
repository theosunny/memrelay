"""Hugging Face endpoint fallback for Basic Memory's embedding-model download.

Basic Memory's semantic search uses fastembed, which downloads models through
huggingface_hub; huggingface_hub reads the `HF_ENDPOINT` environment variable
(huggingface_hub/constants.py: `ENDPOINT = os.getenv("HF_ENDPOINT", ...)`, and fastembed's
model_management.py mentions "huggingface.co (or an `HF_ENDPOINT` mirror)").
In mainland China huggingface.co is often unreachable; https://hf-mirror.com is a widely used
public mirror that implements the same API (usage documented at https://hf-mirror.com).

Policy (config `hf_endpoint`):
- "auto" (default): keep a user-set HF_ENDPOINT; otherwise probe huggingface.co, and if it is
  unreachable but a mirror answers, use the mirror.
- a URL: always use it.   - "" / "off": never set anything.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

OFFICIAL = "https://huggingface.co"
MIRRORS = ("https://hf-mirror.com",)
_cache: dict[str, str | None] = {}


def _probe(url: str, timeout: float = 3.0) -> bool:
    try:
        r = httpx.head(url, timeout=timeout, follow_redirects=True)
        return r.status_code < 500
    except httpx.HTTPError:
        return False


def resolve_endpoint(setting: str | None, environ: dict[str, str],
                     probe: Callable[[str], bool] = _probe, use_cache: bool = True) -> str | None:
    """Return the HF_ENDPOINT value to set for child processes, or None to leave it alone."""
    if setting in ("", "off", "none"):
        return None
    if setting and setting != "auto":
        return setting.rstrip("/")
    if environ.get("HF_ENDPOINT"):
        return None  # user already chose
    if use_cache and "auto" in _cache:
        return _cache["auto"]
    chosen: str | None = None
    if not probe(OFFICIAL):
        chosen = next((m for m in MIRRORS if probe(m)), None)
    _cache["auto"] = chosen
    return chosen
