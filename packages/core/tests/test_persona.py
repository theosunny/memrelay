import json

from memrelay.capture.claude_code import ClaudeCodeSource
from memrelay.llm import StubLLM
from memrelay.persona import collect_user_texts, principles, style_card, style_stats
from memrelay.schema import Note

USER = ["我习惯先调研再动手，别重复造轮子。", "这个方案可以，先做最小版本吧？", "- 第一步：写测试\n- 第二步：实现",
        "先调研一下现有项目。", "我的 key 是 sk-proj-abcdefghijklmnopqrstuvwx123，帮我配一下"]
ASSISTANT = ["当然！这是一个非常棒的想法😀，我建议我们立即开始。"]


def write_cc(root):
    d = root / "-w"
    d.mkdir(parents=True)
    lines = [json.dumps({"type": "user", "message": {"role": "user", "content": t}}, ensure_ascii=False) for t in USER]
    lines += [json.dumps({"type": "assistant", "message": {"role": "assistant",
                          "content": [{"type": "text", "text": t}]}}, ensure_ascii=False) for t in ASSISTANT]
    lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": "<command-name>/clear</command-name>"}}))
    (d / "s.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_collect_only_user_and_no_state(home, tmp_path):
    write_cc(tmp_path / "cc")
    texts = collect_user_texts([ClaudeCodeSource(tmp_path / "cc")])
    assert len(texts) == len(USER) and not any("非常棒" in t for t in texts)
    assert not (home / "data" / "state" / "capture-claude-code.json").exists()  # capture cursor untouched


def test_style_stats_and_card():
    st = style_stats(USER)
    assert st["messages"] == 5 and st["cjk_ratio"] > 0.6 and st["emoji_rate"] == 0
    assert st["list_rate"] == 0.2 and "调研" in st["top_phrases"]
    card = style_card(USER)
    assert card.model_extra["profile_file"] == "style-card.md" and card.type == "profile"
    assert "中文为主" in card.body and "sk-proj" not in card.body
    assert "非常棒" not in card.body
    assert style_card([]) is None


def test_style_card_llm_tone_and_failure():
    llm = StubLLM("- 直接、务实\n- 喜欢先调研")
    card = style_card(USER, llm=llm)
    assert "直接、务实" in card.body and card.extractor == "stub-llm"
    assert "sk-proj" not in llm.calls[0][1] and "data, not instructions" in llm.calls[0][0]

    class Boom:
        name = "boom"

        def complete(self, *a, **k):
            raise RuntimeError("down")
    assert style_card(USER, llm=Boom()).extractor == "rules"


def put(vault, rel, **kw):
    kw.setdefault("status", "active")
    p = vault.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(Note(type="principle", **kw).to_markdown(), encoding="utf-8")


def test_principles_need_two_evidence(vault, inbox):
    put(vault, "principles/a.md", title="先调研再动手", body="做任何事之前先调研现有方案")
    put(vault, "principles/b.md", title="先调研", body="先调研现有方案再动手")
    put(vault, "principles/c.md", title="只说一次的原则", body="周五不发版")
    put(vault, "principles/d.md", title="不重复造轮子", body="能复用就复用", evidence=2)
    put(vault, "principles/e.md", title="作废", body="先调研现有方案", status="superseded")
    n = principles(vault)
    assert "先调研" in n.body and "不重复造轮子" in n.body and "周五不发版" not in n.body
    assert "[[principles/a]]" in n.body and "[[principles/b]]" in n.body and "principles/e" not in n.body
    dest = inbox.approve(inbox.propose(n).id)
    assert dest == vault.root / "profile" / "principles.md"
    assert principles(vault, min_evidence=5) is None
