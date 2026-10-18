import datetime as dt

import pytest

from memrelay.config import Config
from memrelay.schema import Note, effective_confidence, slugify


def test_roundtrip_and_fingerprint():
    n = Note(title="常住城市", body="我常住上海。", tags=["home"], source_agent="t",
             valid_from=dt.date(2024, 3, 1))
    m = Note.from_markdown(n.to_markdown())
    assert m.title == n.title and m.body == n.body and m.valid_from == dt.date(2024, 3, 1)
    assert m.type == "fact" and m.status == "proposed"
    assert m.fingerprint() == n.fingerprint()
    assert Note(title="常住城市", body="我常住上海").fingerprint() == n.fingerprint()  # punctuation-insensitive


def test_extra_frontmatter_is_kept():
    m = Note.from_markdown("---\ntitle: x\nlocked: true\n---\nbody")
    assert m.locked is True and "locked: true" in m.to_markdown()


def test_missing_frontmatter_rejected():
    with pytest.raises(ValueError):
        Note.from_markdown("just text")


def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("我的 偏好/设置") == "我的-偏好-设置"
    assert slugify("../../etc") == "etc"
    assert slugify("???") == "note"


def test_confidence_decay():
    n = Note(title="p", type="preference", confidence=0.8, last_confirmed=dt.date(2026, 1, 1))
    assert effective_confidence(n, dt.date(2026, 1, 1)) == 0.8
    assert abs(effective_confidence(n, dt.date(2026, 6, 30)) - 0.4) < 0.01  # 180-day half-life
    e = Note(title="e", type="event", confidence=0.7, last_confirmed=dt.date(2000, 1, 1))
    assert effective_confidence(e, dt.date(2026, 1, 1)) == 0.7  # events don't decay


def test_config_roundtrip(home):
    c = Config(vault=home / "v", extractor="openai")
    c.llm.model = "deepseek-chat"
    c.save()
    d = Config.load()
    assert d.vault == home / "v" and d.extractor == "openai" and d.llm.model == "deepseek-chat"
    assert d.resolved_bm_config_dir() == home / "data" / "basic-memory"
