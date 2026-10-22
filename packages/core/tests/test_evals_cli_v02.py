import datetime as dt
import json
import shutil

import pytest
from typer.testing import CliRunner

from memrelay.backend import LocalBackend
from memrelay.cli import app
from memrelay.evals import SAMPLE, Case, judge, load_cases, run_eval
from memrelay.schema import Note
from memrelay.twin import answer_as_me

D = dt.date
runner = CliRunner()


def ok(*args, input=None):
    r = runner.invoke(app, list(args), input=input)
    assert r.exit_code == 0, r.output
    return r.output


def put(vault, rel, **kw):
    kw.setdefault("status", "active")
    kw.setdefault("confidence", 0.9)
    kw.setdefault("last_confirmed", dt.date.today())
    p = vault.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(Note(**kw).to_markdown(), encoding="utf-8")
    return p


def seed(vault):
    put(vault, "facts/sh.md", title="常住城市", body="我常住上海", valid_from=D(2024, 3, 1))
    put(vault, "facts/bj.md", title="常住城市", body="我常住北京", status="superseded",
        valid_from=D(2019, 1, 1), valid_to=D(2024, 3, 1))
    put(vault, "preferences/pm.md", title="包管理器", type="preference", body="我用 pnpm 包管理器")


def test_load_cases_and_categories(tmp_path):
    p = tmp_path / "qa.yaml"
    p.write_text(SAMPLE, encoding="utf-8")
    cases = load_cases(p)
    assert [c.category for c in cases] == ["fact", "temporal", "fact", "refusal", "refusal", "unknown"]
    assert cases[1].as_of == D(2023, 6, 1)
    p.write_text("- {id: x}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(p)


def test_judge_rules():
    c = Case(id="a", q="?", expect_any=["上海"])
    assert judge(c, {"answer": "我住上海", "citations": [1], "confidence": 0.5})[0]
    assert not judge(c, {"answer": "我住上海", "citations": [], "confidence": 0.5})[0]  # must be cited
    assert not judge(c, {"answer": "x", "refused": True})[0]
    assert judge(Case(id="r", q="?", should_refuse=True), {"refused": True})[0]
    assert judge(Case(id="u", q="?", expect_unknown=True), {"answer": "不知道", "citations": [], "confidence": 0})[0]


async def test_sample_eval_passes_on_seeded_vault(vault, tmp_path):
    seed(vault)
    p = tmp_path / "qa.yaml"
    p.write_text(SAMPLE, encoding="utf-8")
    b = LocalBackend(vault)
    rep = await run_eval(load_cases(p), lambda q, when: answer_as_me(q, vault=vault, backend=b, as_of=when))
    s = rep.scores()
    assert s["overall"]["accuracy"] == 1.0, [(r.case.id, r.why) for r in rep.results if not r.passed]
    assert s["refusal"]["total"] == 2 and s["temporal"]["passed"] == 1


def test_cli_v02_flow(cfg, vault, tmp_path, monkeypatch):
    seed(vault)
    assert "written" in ok("eval", "init")
    out = ok("eval", "run")
    assert "overall" in out and "6/6" in out
    data = json.loads(ok("eval", "run", "--json"))
    assert data["scores"]["overall"]["accuracy"] == 1.0
    a = json.loads(ok("ask", "我常住哪个城市？", "--as-of", "2023-01-01", "--json"))
    assert "北京" in a["answer"] and a["disclosure"]
    d = ok("draft", "回复同事：用什么包管理器", "--channel", "self")
    assert "pnpm" in d and "草稿" in d
    assert "pnpm" not in ok("draft", "回复同事：用什么包管理器")  # private memories stay out of work drafts
    # consolidation + reflection via CLI
    from memrelay.inbox import Inbox
    Inbox(vault).propose(Note(title="常住城市", body="我常住深圳"))
    assert "SUPERSEDE" in ok("consolidate")
    assert "SUPERSEDE" in ok("inbox", "list")
    daily = ok("reflect", "daily")
    assert any(x in daily for x in ("proposed", "auto_approved", "pending", "duplicate", "No memories", "needs_attention"))
    assert "No principle" in ok("profile", "principles")
    fake = tmp_path / "cchome"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "nocodex"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (fake / "projects" / "-w").mkdir(parents=True)
    (fake / "projects" / "-w" / "s.jsonl").write_text(json.dumps(
        {"type": "user", "message": {"role": "user", "content": "我习惯先调研再动手"}}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    style_out = ok("profile", "style")
    assert "style-card" in style_out or "style-card.md" in style_out or "No user messages" in style_out


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_cli_dream(cfg, vault):
    seed(vault)
    out = ok("dream")
    assert "snapshot" in out
    sha = out.split("snapshot ")[1].split()[0]
    assert sha[:10] in ok("dream", "list")
    assert "rolled back" in ok("dream", "rollback", sha, "--yes")
