import datetime as dt
import shutil

import pytest

from memrelay import dream as dream_mod
from memrelay.llm import StubLLM
from memrelay.reflect import daily, weekly
from memrelay.schema import Note

D = dt.date
T = dt.datetime


def put(vault, rel, day=D(2026, 10, 18), **kw):
    kw.setdefault("status", "active")
    kw.setdefault("confidence", 0.9)
    kw.setdefault("last_confirmed", day)
    kw.setdefault("captured_at", T(day.year, day.month, day.day, 10, 0, tzinfo=dt.UTC))
    p = vault.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(Note(**kw).to_markdown(), encoding="utf-8")
    return p


@pytest.fixture
def day_notes(vault):
    put(vault, "events/2026/start.md", title="决定做 MemRelay", type="event", body="决定开工做 MemRelay",
        valid_from=D(2026, 10, 18))
    put(vault, "preferences/pnpm.md", title="包管理器", type="preference", body="我习惯用 pnpm")
    put(vault, "projects/mr.md", title="MemRelay", type="project", body="计划下周发布 v0.2")
    put(vault, "facts/old.md", title="旧事", body="很久以前", day=D(2025, 1, 1))
    return vault


def test_daily_rules_cite_every_line(day_notes):
    n = daily(day_notes, D(2026, 10, 18))
    assert n.type == "reflection" and n.model_extra["period"] == "daily" and n.extractor == "rules"
    assert "很久以前" not in n.body and "pnpm" in n.body
    bullets = [line for line in n.body.split("## 来源")[0].splitlines() if line.startswith("- ")]
    assert bullets and all("[" in b and "]" in b for b in bullets)
    assert "## 待办" in n.body and "[[preferences/pnpm]]" in n.body
    assert set(n.model_extra["evidence_refs"]) == {"events/2026/start.md", "preferences/pnpm.md", "projects/mr.md"}
    assert daily(day_notes, D(2026, 1, 1)) is None


def test_daily_llm_citations_validated(day_notes):
    llm = StubLLM("## 做了什么 / Done\n- 决定做 MemRelay [1]\n- 编造的事 [9]\n- 没有引用的句子\n## 待办\n- 发布 v0.2 [3]")
    n = daily(day_notes, D(2026, 10, 18), llm=llm)
    assert n.extractor == "stub-llm"
    assert "编造的事" not in n.body and "没有引用" not in n.body and "发布 v0.2 [3]" in n.body
    assert "data, not" in llm.calls[0][0]
    # LLM that cites nothing valid -> rule-based fallback
    assert daily(day_notes, D(2026, 10, 18), llm=StubLLM("I think you are great.")).extractor == "rules"


def test_daily_into_inbox_then_reflections_dir(day_notes, inbox):
    iid = inbox.propose(daily(day_notes, D(2026, 10, 18))).id
    dest = inbox.approve(iid)
    assert dest.parent == day_notes.root / "reflections" / "daily"


def test_weekly(day_notes, inbox):
    iid = inbox.propose(daily(day_notes, D(2026, 10, 18))).id
    inbox.approve(iid)
    w = weekly(day_notes, D(2026, 10, 19), today=D(2026, 10, 19))
    assert w.model_extra["period"] == "weekly" and "本周概览" in w.body
    assert any(r.startswith("reflections/daily/") for r in w.model_extra["evidence_refs"])
    llm = StubLLM("## 洞见 / Insights\n- Q: 这周最重要的是什么？ → 开始做 MemRelay [1]")
    assert "洞见" in weekly(day_notes, D(2026, 10, 19), llm=llm).body
    assert "salient" in llm.calls[0][0]


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


@needs_git
def test_dream_snapshot_merge_and_rollback(vault, inbox):
    a = put(vault, "facts/tz.md", title="时区", body="我的时区是 Asia/Shanghai", evidence=2)
    b = put(vault, "facts/tz2.md", title="我的时区", body="我的时区是 Asia/Shanghai")
    put(vault, "facts/stale.md", title="很老的事实", body="五年前的信息", confidence=0.4,
        last_confirmed=D(2021, 1, 1), day=D(2021, 1, 1))
    rep = dream_mod.dream(vault, inbox, today=D(2026, 10, 18))
    assert rep.snapshot and len(rep.merges) == 1 and rep.stale == ["facts/stale.md"]
    assert a.exists() and b.exists()  # nothing changed before approval
    assert dream_mod.snapshots()[-1]["sha"] == rep.snapshot
    refl = inbox.get(rep.reflection)
    assert refl.model_extra["period"] == "dream" and rep.snapshot[:10] in refl.body

    inbox.approve(rep.merges[0])  # keep tz.md, retire tz2.md to archive (not deleted)
    assert a.exists() and not b.exists()
    assert Note.from_markdown(a.read_text(encoding="utf-8")).evidence == 3
    assert list((vault.root / "archive" / "merged").glob("facts__tz2--*.md"))

    new_head = dream_mod.rollback(vault, rep.snapshot)
    assert new_head != rep.snapshot
    assert b.exists() and Note.from_markdown(a.read_text(encoding="utf-8")).evidence == 2
    assert not (vault.root / "archive" / "merged").exists() or not list((vault.root / "archive" / "merged").glob("*"))
    log = dream_mod._git(vault, "log", "--format=%s")
    assert "rollback to snapshot" in log and "dream: snapshot" in log  # history kept
    with pytest.raises(RuntimeError):
        dream_mod.rollback(vault, "0" * 40)


@needs_git
def test_dream_in_existing_repo_keeps_history(vault, inbox):
    dream_mod._git(vault, "init", "-q")
    (vault.root / "mine.txt").write_text("user file", encoding="utf-8")
    dream_mod._git(vault, "add", "-A")
    dream_mod._git(vault, "commit", "-q", "-m", "user commit")
    dream_mod.dream(vault, inbox)
    assert "user commit" in dream_mod._git(vault, "log", "--format=%s")
