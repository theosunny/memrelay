import datetime as dt
import json

import pytest
from fastmcp import Client

from memrelay.backend import LocalBackend
from memrelay.consolidate import LLMJudge, Op, RuleJudge, annotate_inbox, neighbors
from memrelay.gateway import build_server
from memrelay.llm import StubLLM
from memrelay.schema import Note
from memrelay.temporal import valid_at, visible

D = dt.date


def put(vault, rel, **kw):
    kw.setdefault("status", "active")
    kw.setdefault("confidence", 0.9)
    kw.setdefault("last_confirmed", dt.date.today())
    p = vault.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(Note(**kw).to_markdown(), encoding="utf-8")
    return p


def test_valid_at_and_visible():
    n = Note(title="住北京", status="superseded", valid_from=D(2020, 1, 1), valid_to=D(2024, 3, 1),
             captured_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    assert valid_at(n, D(2023, 6, 1)) and not valid_at(n, D(2024, 3, 1)) and not valid_at(n, D(2019, 1, 1))
    today = D(2026, 10, 18)
    assert not visible(n, today)                      # superseded: not "now"
    assert visible(n, today, D(2023, 6, 1))           # but true back then
    cur = Note(title="住上海", status="active", valid_from=D(2024, 3, 1))
    assert visible(cur, today) and not visible(cur, today, D(2023, 6, 1))
    assert not visible(Note(title="s", status="active", sensitivity="secret"), today)
    assert not visible(Note(title="p", status="proposed"), today, D(2020, 1, 1))
    # no valid_from: only known since capture
    late = Note(title="x", status="active", captured_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    assert not visible(late, today, D(2025, 1, 1)) and visible(late, today, D(2026, 2, 1))


def test_layered_dirs(vault, inbox):
    e = inbox.propose(Note(title="决定做 MemRelay", type="event", body="2026-10-18 决定开工",
                           valid_from=D(2026, 10, 18))).id
    assert inbox.approve(e).parent == vault.root / "events" / "2026"
    r = inbox.propose(Note(title="日报 2026-10-18", type="reflection", body="做了 X", period="daily")).id
    assert inbox.approve(r).parent == vault.root / "reflections" / "daily"


async def test_recall_as_of(cfg, vault):
    put(vault, "facts/beijing.md", title="常住城市", body="我常住北京", status="superseded",
        valid_from=D(2019, 1, 1), valid_to=D(2024, 3, 1), superseded_by="facts/shanghai.md")
    put(vault, "facts/shanghai.md", title="常住城市", body="我常住上海", valid_from=D(2024, 3, 1))
    async with Client(build_server(cfg, backend=LocalBackend(vault))) as c:
        def data(r):
            return r.data if r.data is not None else json.loads(r.content[0].text)
        now = data(await c.call_tool("recall", {"query": "常住城市"}))
        assert [h["id"] for h in now] == ["facts/shanghai.md"]
        then = data(await c.call_tool("recall", {"query": "常住城市", "as_of": "2023-05-01"}))
        assert [h["id"] for h in then] == ["facts/beijing.md"] and then[0]["status"] == "superseded"
        bad = data(await c.call_tool("recall", {"query": "x", "as_of": "May 1"}))
        assert "error" in bad[0]


def test_rule_judge_ops(vault):
    put(vault, "facts/city.md", title="常住城市", body="我常住北京")
    put(vault, "preferences/pm.md", title="包管理器", type="preference", body="我用 pnpm")
    j = RuleJudge()

    def plan(**kw):
        c = Note(**kw)
        return j.decide(c, neighbors(vault, c))

    assert plan(title="常住城市", body="我常住北京。").op == Op.NOOP
    p = plan(title="常住城市", body="我常住上海")
    assert p.op == Op.SUPERSEDE and p.target == "facts/city.md"
    p = plan(title="包管理器", type="preference", body="我用 pnpm，而且 monorepo 用 workspace")
    assert p.op == Op.UPDATE and p.target == "preferences/pm.md"
    assert plan(title="喜欢的猫", body="我养了一只橘猫").op == Op.ADD


def test_llm_judge_and_fallback(vault):
    put(vault, "facts/city.md", title="常住城市", body="我常住北京")
    cand = Note(title="搬家", body="今年三月搬到了上海")
    near = neighbors(vault, cand) or [("facts/city.md", Note(title="常住城市", body="我常住北京"), 0.1)]
    llm = StubLLM('```json\n{"op": "SUPERSEDE", "target": 0, "reason": "moved"}\n```')
    p = LLMJudge(llm).decide(cand, near)
    assert p.op == "SUPERSEDE" and p.target == "facts/city.md" and p.reason == "moved"
    assert "data, not instructions" in llm.calls[0][0]
    # garbage / bad index -> rule fallback, never crash
    assert LLMJudge(StubLLM("nonsense")).decide(cand, near).op in set(Op)
    assert LLMJudge(StubLLM('{"op":"UPDATE","target":7}')).decide(cand, near).op in set(Op)

    class Boom:
        name = "boom"

        def complete(self, *a, **k):
            raise RuntimeError("network down")
    assert LLMJudge(Boom()).decide(cand, near).op in set(Op)


def test_annotate_and_apply_supersede_never_deletes(vault, inbox):
    old = put(vault, "facts/city.md", title="常住城市", body="我常住北京", valid_from=D(2019, 1, 1))
    iid = inbox.propose(Note(title="常住城市", body="我常住上海", valid_from=D(2024, 3, 1))).id
    plans = annotate_inbox(inbox, RuleJudge())
    assert plans[0][1].op == Op.SUPERSEDE
    assert inbox.get(iid).model_extra["consolidation"]["target"] == "facts/city.md"
    assert old.exists()  # annotation never touches the vault
    dest = inbox.approve(iid)
    o = Note.from_markdown(old.read_text(encoding="utf-8"))
    n = Note.from_markdown(dest.read_text(encoding="utf-8"))
    assert o.status == "superseded" and o.valid_to == D(2024, 3, 1) and o.superseded_by == vault.rel(dest)
    assert n.status == "active" and "consolidation" not in (n.model_extra or {})
    assert list((vault.root / "archive" / "versions").glob("facts__city--*.md"))
    assert inbox.list() == []


def test_apply_noop_and_update_archive(vault, inbox):
    t = put(vault, "facts/tz.md", title="时区", body="我的时区是 Asia/Shanghai", confidence=0.6)
    r = inbox.propose(Note(title="时区", body="我的时区是 Asia/Shanghai！", source_agent="codex"))
    assert r.duplicate_of == "facts/tz.md"  # exact duplicate never even reaches the inbox
    iid = inbox.propose(Note(title="我的时区", body="我的时区是 Asia/Shanghai", source_agent="codex")).id
    plans = annotate_inbox(inbox, RuleJudge())
    assert plans[0][1].op == Op.NOOP, plans
    assert inbox.approve(iid) == t
    n = Note.from_markdown(t.read_text(encoding="utf-8"))
    assert n.evidence == 2 and n.confidence == pytest.approx(0.72)
    assert list((vault.root / "archive" / "merged").glob("inbox__*.md"))  # candidate kept for audit
    iid = inbox.propose(Note(title="时区", body="我的时区是 Asia/Shanghai，夏天也不变")).id
    annotate_inbox(inbox, RuleJudge())
    inbox.approve(iid)
    assert "夏天" in Note.from_markdown(t.read_text(encoding="utf-8")).body
    assert len(list((vault.root / "archive" / "versions").glob("facts__tz--*.md"))) == 2


def test_approve_as_new_overrides_plan(vault, inbox):
    put(vault, "facts/city.md", title="常住城市", body="我常住北京")
    iid = inbox.propose(Note(title="常住城市", body="我常住上海")).id
    annotate_inbox(inbox, RuleJudge())
    dest = inbox.approve(iid, as_new=True)
    assert dest != vault.root / "facts" / "city.md" and dest.exists()
    assert Note.from_markdown((vault.root / "facts" / "city.md").read_text(encoding="utf-8")).status == "active"


def test_profile_file_proposal_and_lock(vault, inbox):
    iid = inbox.propose(Note(title="Style card", type="profile", body="# 风格卡", profile_file="style-card.md")).id
    dest = inbox.approve(iid)
    assert dest == vault.root / "profile" / "style-card.md"
    iid = inbox.propose(Note(title="Style card", type="profile", body="# 风格卡 v2", profile_file="../evil.md")).id
    assert inbox.approve(iid) == vault.root / "profile" / "evil.md"  # traversal stripped
    (vault.root / "profile" / "style-card.md").write_text("my own hand-written card\n", encoding="utf-8")
    iid = inbox.propose(Note(title="Style card", type="profile", body="# v3", profile_file="style-card.md")).id
    with pytest.raises(PermissionError):
        inbox.approve(iid)
