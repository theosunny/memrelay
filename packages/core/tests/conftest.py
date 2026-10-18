from __future__ import annotations

import pytest

from memrelay.config import Config
from memrelay.inbox import Inbox
from memrelay.vault import Vault


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMRELAY_HOME", str(tmp_path / "mr"))
    return tmp_path / "mr"


@pytest.fixture
def cfg(home):
    c = Config(vault=home / "vault", backend="local")
    c.save()
    return c


@pytest.fixture
def vault(cfg):
    v = Vault(cfg.vault)
    v.init()
    return v


@pytest.fixture
def inbox(vault):
    return Inbox(vault)
