"""`memrelay` command line."""

from __future__ import annotations

import datetime as dt
import difflib
import json
import sys

import typer

from . import __version__
from .config import Config, config_dir, data_dir
from .inbox import Inbox
from .vault import Vault

app = typer.Typer(help="MemRelay (忆桥): one reviewed personal memory for all your agents.",
                  no_args_is_help=True, add_completion=False)
inbox_app = typer.Typer(help="Review proposed memories / 审核收件箱", no_args_is_help=True)
connect_app = typer.Typer(help="Connect agents (write MCP configs) / 接入智能体", invoke_without_command=True)
capture_app = typer.Typer(help="Capture local agent history / 采集本地历史", no_args_is_help=True)
profile_app = typer.Typer(help="Core profile / 核心画像", no_args_is_help=True)
app.add_typer(inbox_app, name="inbox")
app.add_typer(connect_app, name="connect")
app.add_typer(capture_app, name="capture")
app.add_typer(profile_app, name="profile")


def _ctx() -> tuple[Config, Vault, Inbox]:
    cfg = Config.load()
    vault = Vault(cfg.vault)
    vault.init()
    return cfg, vault, Inbox(vault)


@app.command()
def version() -> None:
    typer.echo(__version__)


@app.command()
def init(vault: str | None = typer.Option(None, help="Vault directory (default ~/MemRelay)")) -> None:
    """Create config and vault layout. / 初始化配置和记忆库目录"""
    cfg = Config.load()
    if vault:
        from pathlib import Path
        cfg.vault = Path(vault).expanduser()
    created = Vault(cfg.vault).init()
    path = cfg.save()
    typer.echo(f"config: {path}\nvault:  {cfg.vault}  (+{len(created)} folders)\nstate:  {data_dir()}")


@app.command()
def serve() -> None:
    """Run the MCP gateway over stdio (agents launch this). / 启动 MCP 网关"""
    from .gateway import build_server

    build_server(Config.load()).run(show_banner=False)


@app.command()
def doctor() -> None:
    """Show paths and detected components. / 自检"""
    from .adapters import ADAPTERS
    from .backend import BasicMemoryBackend

    cfg = Config.load()
    typer.echo(f"memrelay {__version__}  python {sys.version.split()[0]}  platform {sys.platform}")
    typer.echo(f"config dir: {config_dir()}\ndata dir:   {data_dir()}\nvault:      {cfg.vault}")
    typer.echo(f"basic-memory on PATH: {BasicMemoryBackend.available(cfg)}  (backend={cfg.backend})")
    for aid, cls in ADAPTERS.items():
        a = cls()
        typer.echo(f"  {aid:15} detected={a.detect()!s:5} installed={a.installed() is not None!s:5} {a.config_path()}")


# ------------------------------------------------------------------ inbox
@inbox_app.command("list")
def inbox_list(as_json: bool = typer.Option(False, "--json")) -> None:
    _, _, inbox = _ctx()
    items = inbox.list()
    if as_json:
        typer.echo(json.dumps([{"id": i, **n.frontmatter(), "body": n.body} for i, n in items],
                              ensure_ascii=False, indent=2))
        return
    if not items:
        typer.echo("Inbox empty. / 收件箱为空")
        return
    for i, n in items:
        flags = f" [{','.join(n.flags)}]" if n.flags else ""
        typer.echo(f"{i}\n    [{n.type}] {n.title}  (from {n.source_agent}, conf {n.confidence}){flags}")
        plan = (n.model_extra or {}).get("consolidation")
        if plan and plan.get("op") != "ADD":
            typer.echo(f"    → {plan['op']} {plan.get('target', '')}  ({plan.get('reason', '')})")


@inbox_app.command("show")
def inbox_show(item_id: str) -> None:
    _, _, inbox = _ctx()
    typer.echo(inbox.get(item_id).to_markdown())


@inbox_app.command("approve")
def inbox_approve(
    item_ids: list[str],
    type: str | None = typer.Option(None, "--type", help="Override memory type"),
    title: str | None = typer.Option(None, "--title"),
    visibility: str | None = typer.Option(None, "--visibility"),
    as_new: bool = typer.Option(False, "--as-new", help="Ignore the consolidation plan; add as a new memory"),
) -> None:
    _, vault, inbox = _ctx()
    edits = {k: v for k, v in {"type": type, "title": title, "visibility": visibility}.items() if v}
    for iid in item_ids:
        dest = inbox.approve(iid, edits=edits, as_new=as_new)
        typer.echo(f"approved {iid} -> {vault.rel(dest)}")


@inbox_app.command("reject")
def inbox_reject(item_ids: list[str], reason: str | None = typer.Option(None, "--reason")) -> None:
    _, vault, inbox = _ctx()
    for iid in item_ids:
        dest = inbox.reject(iid, reason)
        typer.echo(f"rejected {iid} -> {vault.rel(dest)}")


@app.command("review")
def review(
    web: bool = typer.Option(True, "--web/--no-web", help="Open the local web review UI"),
    port: int = typer.Option(0, help="Port on 127.0.0.1 (0 = random free port)"),
    open_browser: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Review the inbox in a local browser page (127.0.0.1 only). / 本地网页审核"""
    from .web import serve

    _, _, inbox = _ctx()
    serve(inbox, port=port, open_browser=open_browser, echo=typer.echo)


@app.command("consolidate")
def consolidate_cmd(force: bool = typer.Option(False, help="Re-plan items that already have a plan")) -> None:
    """Plan ADD/UPDATE/SUPERSEDE/NOOP for inbox items (applied only when you approve). / 整理建议"""
    from .consolidate import annotate_inbox, get_judge

    cfg, _, inbox = _ctx()
    judge = get_judge(cfg)
    plans = annotate_inbox(inbox, judge, force=force)
    if not plans:
        typer.echo("Nothing to plan. / 没有需要整理的条目")
    for iid, p in plans:
        typer.echo(f"{p.op:9} {iid}" + (f" → {p.target}" if p.target else "") + f"  ({p.reason})")
    typer.echo(f"judge: {judge.name}. Review with `memrelay inbox list`; nothing is changed until you approve.")


# ------------------------------------------------------------------ persona / twin
reflect_app = typer.Typer(help="Daily/weekly reflections / 反思", no_args_is_help=True)
dream_app = typer.Typer(help="Dream: whole-vault consolidation with git snapshot / 大整理", invoke_without_command=True)
eval_app = typer.Typer(help="Twin fidelity eval / 分身保真度评估", no_args_is_help=True)
app.add_typer(reflect_app, name="reflect")
app.add_typer(dream_app, name="dream")
app.add_typer(eval_app, name="eval")


def _date(v: str | None) -> dt.date:
    return dt.date.fromisoformat(v) if v else dt.date.today()


@reflect_app.command("daily")
def reflect_daily(date: str | None = typer.Option(None, help="YYYY-MM-DD (default today)")) -> None:
    from .llm import get_llm
    from .reflect import daily

    cfg, vault, inbox = _ctx()
    n = daily(vault, _date(date), llm=get_llm(cfg))
    if n is None:
        typer.echo("No memories for that day. / 当天没有记忆")
        return
    r = inbox.propose(n)
    typer.echo(f"proposed {r.id} ({n.extractor}); review with `memrelay inbox show {r.id}`")


@reflect_app.command("weekly")
def reflect_weekly(date: str | None = typer.Option(None, help="week end YYYY-MM-DD (default today)")) -> None:
    from .llm import get_llm
    from .reflect import weekly

    cfg, vault, inbox = _ctx()
    n = weekly(vault, _date(date), llm=get_llm(cfg))
    if n is None:
        typer.echo("No memories for that week. / 本周没有记忆")
        return
    r = inbox.propose(n)
    typer.echo(f"proposed {r.id} ({n.extractor}); review with `memrelay inbox show {r.id}`")


@dream_app.callback()
def dream_main(ctx: typer.Context) -> None:
    """Snapshot the vault (git), then propose merges and list stale/long notes."""
    if ctx.invoked_subcommand:
        return
    from .dream import dream

    _, vault, inbox = _ctx()
    rep = dream(vault, inbox)
    typer.echo(f"snapshot {rep.snapshot}\nmerge proposals: {len(rep.merges)}  stale: {len(rep.stale)}  "
               f"long: {len(rep.long)}\nreview: memrelay inbox list   undo: memrelay dream rollback {rep.snapshot[:10]}")


@dream_app.command("list")
def dream_list() -> None:
    from .dream import snapshots

    for s in snapshots():
        typer.echo(f"{s['sha'][:10]}  {s['at']}  {s['message']}")


@dream_app.command("rollback")
def dream_rollback(sha: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Restore the vault to a snapshot as a new commit (history kept). / 回滚到快照"""
    from .dream import rollback

    _, vault, _ = _ctx()
    if not yes and not typer.confirm(f"Restore vault to {sha}? / 恢复到该快照？", default=False):
        raise typer.Exit(1)
    typer.echo(f"rolled back; new commit {rollback(vault, sha)}")


@profile_app.command("style")
def profile_style() -> None:
    """Style card from your own messages only → inbox. / 生成风格卡"""
    from .llm import get_llm
    from .persona import collect_user_texts, style_card

    cfg, _, inbox = _ctx()
    n = style_card(collect_user_texts(), llm=get_llm(cfg))
    if n is None:
        typer.echo("No user messages found in local capture sources. / 未找到你本人的消息")
        return
    r = inbox.propose(n)
    typer.echo(f"proposed {r.id} (profile/style-card.md, {n.evidence} messages)")


@profile_app.command("principles")
def profile_principles(min_evidence: int = typer.Option(2, min=1)) -> None:
    """Decision principles with ≥N evidence → inbox. / 生成决策原则"""
    from .persona import principles

    _, vault, inbox = _ctx()
    n = principles(vault, min_evidence=min_evidence)
    if n is None:
        typer.echo(f"No principle has ≥{min_evidence} evidence yet. / 还没有足够证据的原则")
        return
    r = inbox.propose(n)
    typer.echo(f"proposed {r.id} (profile/principles.md)")


def _twin_run(coro_fn):
    import asyncio

    from .backend import make_backend

    cfg, vault, _ = _ctx()

    async def go():
        b = make_backend(cfg, vault)
        await b.start()
        try:
            return await coro_fn(cfg, vault, b)
        finally:
            await b.stop()

    return asyncio.run(go())


@app.command("ask")
def ask(question: str, as_of: str | None = typer.Option(None, "--as-of"),
        as_json: bool = typer.Option(False, "--json")) -> None:
    """Ask your twin (same as the answer_as_me MCP tool). / 问分身"""
    from .llm import get_llm
    from .twin import answer_as_me

    res = _twin_run(lambda cfg, vault, b: answer_as_me(question, vault=vault, backend=b, llm=get_llm(cfg),
                                                        as_of=dt.date.fromisoformat(as_of) if as_of else None,
                                                        ceiling=cfg.twin_visibility))
    if as_json:
        typer.echo(json.dumps(res, ensure_ascii=False, indent=2))
        return
    typer.echo(f"{res['answer']}\n\nconfidence {res['confidence']}  ({res['mode']})")
    for c in res["citations"]:
        typer.echo(f"  [{c['n']}] {c['id']}  {c['title']}")
    typer.echo(f"\n{res['disclosure']}")


@app.command("draft")
def draft(context: str, channel: str = typer.Option("work", help="work | friends | public | self"),
          as_json: bool = typer.Option(False, "--json")) -> None:
    """Draft a message in your style. Prints text only; nothing is sent. / 代拟草稿"""
    from .llm import get_llm
    from .twin import draft_as_me

    res = _twin_run(lambda cfg, vault, b: draft_as_me(context, vault=vault, backend=b, llm=get_llm(cfg), channel=channel))
    if as_json:
        typer.echo(json.dumps(res, ensure_ascii=False, indent=2))
        return
    typer.echo(res["draft"])
    if res["needs_confirmation"]:
        typer.echo("\n⚠ 涉及承诺/金额/法律/健康，请本人确认 / needs your confirmation")
    typer.echo(f"\n{res['note']}")


@eval_app.command("init")
def eval_init(force: bool = typer.Option(False, "--force")) -> None:
    """Write a sample eval/qa.yaml into the vault. / 生成示例题库"""
    from .evals import SAMPLE

    _, vault, _ = _ctx()
    p = vault.root / "eval" / "qa.yaml"
    if p.exists() and not force:
        typer.echo(f"exists: {p} (use --force)")
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(SAMPLE, encoding="utf-8")
    typer.echo(f"written: {p}")


@eval_app.command("run")
def eval_run(path: str | None = typer.Option(None, help="qa.yaml (default <vault>/eval/qa.yaml)"),
             as_json: bool = typer.Option(False, "--json")) -> None:
    """Score the twin: facts, point-in-time, refusals, unknowns. / 运行评估"""
    from pathlib import Path

    from .evals import load_cases, run_eval
    from .llm import get_llm
    from .twin import answer_as_me

    cfg0, vault0, _ = _ctx()
    cases = load_cases(Path(path) if path else vault0.root / "eval" / "qa.yaml")

    async def go(cfg, vault, b):
        return await run_eval(cases, lambda q, when: answer_as_me(
            q, vault=vault, backend=b, llm=get_llm(cfg), as_of=when, ceiling=cfg.twin_visibility))

    rep = _twin_run(go)
    scores = rep.scores()
    if as_json:
        typer.echo(json.dumps({"scores": scores, "results": [
            {"id": r.case.id, "category": r.case.category, "passed": r.passed, "why": r.why,
             "answer": r.answer, "confidence": r.confidence} for r in rep.results]}, ensure_ascii=False, indent=2))
        return
    for r in rep.results:
        typer.echo(f"{'PASS' if r.passed else 'FAIL'}  {r.case.category:8} {r.case.id}" + (f"  — {r.why}" if r.why else ""))
    typer.echo("")
    for k, v in scores.items():
        typer.echo(f"{k:9} {v['passed']}/{v['total']}  ({v['accuracy']:.0%})")


# ------------------------------------------------------------------ connect
@connect_app.callback()
def connect_main(
    ctx: typer.Context,
    all_: bool = typer.Option(False, "--all", help="Interactive wizard: discover every agent / 交互式向导"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without asking"),
    command: str | None = typer.Option(None, help="Override the MCP server command"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if not all_:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)
    from .adapters import ServerSpec
    from .wizard import run_wizard

    spec = ServerSpec(command=command, args=["serve"]) if command else ServerSpec()
    res = run_wizard(spec, confirm=lambda q: typer.confirm(q, default=True), echo=typer.echo, yes=yes)
    if res.errors:
        raise typer.Exit(2)


@connect_app.command("list")
def connect_list() -> None:
    from .adapters import ADAPTERS, is_guided

    for aid, cls in ADAPTERS.items():
        a = cls()
        kind = "guided" if is_guided(a) else f"detected={a.detect()!s:5} installed={a.installed() is not None!s:5}"
        typer.echo(f"{aid:15} {a.name:26} {kind}")
        typer.echo(f"{'':15} {a.config_path() or '(manual setup)'}  (source: {a.sources[0]})")


def _print_change(ch) -> None:
    tag = "DRY-RUN " if ch.dry_run else ""
    typer.echo(f"{tag}{ch.action}: {ch.adapter} -> {ch.path}")
    if ch.after is not None:
        typer.echo("  " + json.dumps(ch.after, ensure_ascii=False))
    if ch.backup:
        typer.echo(f"  backup: {ch.backup}")
    if ch.note and ch.action == "guided":
        typer.echo(ch.note)
    elif ch.note:
        typer.echo(f"  note: {ch.note}")


@connect_app.command("install")
def connect_install(
    adapter_ids: list[str] = typer.Argument(None, help="Adapter ids; omit with --all"),
    all_: bool = typer.Option(False, "--all", help="All detected agents"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    from .adapters import ADAPTERS, ServerSpec, get_adapter

    ids = adapter_ids or ([a for a, c in ADAPTERS.items() if c().detect()] if all_ else [])
    if not ids:
        typer.echo("Nothing to do: pass adapter ids or --all.")
        raise typer.Exit(1)
    for aid in ids:
        _print_change(get_adapter(aid).install(ServerSpec(), dry_run=dry_run))


@connect_app.command("uninstall")
def connect_uninstall(adapter_ids: list[str], dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    from .adapters import get_adapter

    for aid in adapter_ids:
        _print_change(get_adapter(aid).uninstall(dry_run=dry_run))


@connect_app.command("rollback")
def connect_rollback(adapter_ids: list[str]) -> None:
    """Restore the config file as it was before the last MemRelay change."""
    from .adapters import get_adapter

    for aid in adapter_ids:
        used = get_adapter(aid).rollback()
        typer.echo(f"{aid}: " + (f"restored from {used.name}" if used else "no backup"))


# ------------------------------------------------------------------ capture
@capture_app.command("claude-code")
def capture_claude_code(
    watch: bool = typer.Option(False, "--watch", help="Keep running and capture on change"),
    extractor: str | None = typer.Option(None, help="stub | openai (default from config)"),
) -> None:
    """Claude Code transcripts -> candidate memories in inbox/."""
    from .capture.claude_code import ClaudeCodeSource
    from .capture.runner import run_once
    from .capture.runner import watch as watch_fn
    from .extract.base import get_extractor

    cfg, _, inbox = _ctx()
    ex = get_extractor(extractor or cfg.extractor, cfg)
    src = ClaudeCodeSource()

    def report(r) -> None:
        typer.echo(f"messages={r.messages} candidates={r.candidates} "
                   f"proposed={len(r.proposed)} duplicates={r.duplicates}")

    if watch:
        typer.echo(f"watching {src.root} (Ctrl+C to stop)")
        watch_fn(src, ex, inbox, src.root, on_report=report)
    else:
        report(run_once(src, ex, inbox))


@capture_app.command("all")
def capture_all(
    watch: bool = typer.Option(False, "--watch", help="Keep running (used by autostart)"),
    extractor: str | None = typer.Option(None, help="stub | openai (default from config)"),
) -> None:
    """All local sources: Claude Code, Codex, Gemini CLI."""
    from .capture.registry import SOURCES
    from .capture.runner import run_once, watch_all
    from .extract.base import get_extractor

    cfg, _, inbox = _ctx()
    ex = get_extractor(extractor or cfg.extractor, cfg)
    sources = [cls() for cls in SOURCES.values()]

    def report(sid, r) -> None:
        typer.echo(f"{sid:12} messages={r.messages} candidates={r.candidates} "
                   f"proposed={len(r.proposed)} duplicates={r.duplicates}")

    if watch:
        watch_all(sources, ex, inbox, on_report=report)
    else:
        for s in sources:
            report(s.id, run_once(s, ex, inbox))


@capture_app.command("source")
def capture_source(source_id: str) -> None:
    """One source by id: claude-code | codex | gemini-cli."""
    from .capture.registry import SOURCES
    from .capture.runner import run_once
    from .extract.base import get_extractor

    cfg, _, inbox = _ctx()
    if source_id not in SOURCES:
        typer.echo(f"unknown source; known: {', '.join(SOURCES)}")
        raise typer.Exit(1)
    r = run_once(SOURCES[source_id](), get_extractor(cfg.extractor, cfg), inbox)
    typer.echo(f"messages={r.messages} candidates={r.candidates} proposed={len(r.proposed)} duplicates={r.duplicates}")


# ------------------------------------------------------------------ import
import_app = typer.Typer(help="Import ChatGPT / Claude export packages / 导入导出包", no_args_is_help=True)
app.add_typer(import_app, name="import")


@import_app.command("scan")
def import_scan(folder: list[str] = typer.Option(None, "--dir", help="Folder(s) to scan (default: Downloads)")) -> None:
    from pathlib import Path

    from .importers import scan

    found = scan([Path(f).expanduser() for f in folder] if folder else None)
    if not found:
        typer.echo("No ChatGPT/Claude export found. / 没有发现导出包")
    for c in found:
        mark = " (already imported / 已导入)" if c.already_imported else ""
        typer.echo(f"{c.kind:8} {c.size / 1e6:7.1f} MB  {c.mtime:%Y-%m-%d %H:%M}  {c.path}{mark}")


@import_app.command("run")
def import_run(
    paths: list[str] = typer.Argument(None, help="Export zip / conversations.json; omit to scan Downloads"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Do not ask before importing"),
    archive: bool = typer.Option(True, help="Also keep raw transcripts via Basic Memory importers"),
    folder: list[str] = typer.Option(None, "--dir"),
) -> None:
    from pathlib import Path

    from .backend import BasicMemoryBackend
    from .extract.base import get_extractor
    from .importers import archive_with_basic_memory, run_import, scan

    cfg, vault, inbox = _ctx()
    if paths:
        targets = [Path(p).expanduser() for p in paths]
    else:
        targets = [c.path for c in scan([Path(f).expanduser() for f in folder] if folder else None)
                   if not c.already_imported]
    if not targets:
        typer.echo("Nothing to import. / 没有可导入的内容")
        return
    archiver = None
    if archive and BasicMemoryBackend.available(cfg):
        bm = BasicMemoryBackend(cfg, vault)
        bm.ensure_project()
        env = bm.env()

        def archiver(kind, raw):
            archive_with_basic_memory(kind, raw, cfg.bm_command, env)
    elif archive:
        typer.echo("basic-memory not on PATH: skipping raw archive. / 未安装 basic-memory，跳过原文归档")
    ex = get_extractor(cfg.extractor, cfg)
    for p in targets:
        if not yes and not typer.confirm(f"导入 / Import {p}?", default=False):
            continue
        try:
            rep = run_import(p, ex, inbox, archive=archiver)
        except (ValueError, OSError) as e:
            typer.echo(f"skip: {e}")
            continue
        typer.echo(f"{rep.kind}: conversations={rep.conversations} messages={rep.messages} "
                   f"proposed={len(rep.proposed)} duplicates={rep.duplicates} archived={rep.archived}"
                   + (f" archive_error={rep.archive_error}" if rep.archive_error else ""))


# ------------------------------------------------------------------ autostart
autostart_app = typer.Typer(help="Run capture at login / 开机自启", no_args_is_help=True)
app.add_typer(autostart_app, name="autostart")


def _print_plan(plan, dry_run: bool) -> None:
    tag = "DRY-RUN " if dry_run else ""
    for path, text in plan.write.items():
        typer.echo(f"{tag}write {path}:\n{text}")
    for c in plan.commands:
        typer.echo(f"{tag}run: {' '.join(c)}")
    for path in plan.remove:
        typer.echo(f"{tag}remove {path}")
    for n in plan.notes:
        typer.echo(f"note: {n}")


@autostart_app.command("install")
def autostart_install(
    dry_run: bool = typer.Option(False, "--dry-run"),
    method: str = typer.Option("default", help="Windows only: default (Task Scheduler) | startup-folder"),
) -> None:
    from .autostart import Autostart

    _print_plan(Autostart(method=method).install(dry_run=dry_run), dry_run)


@autostart_app.command("uninstall")
def autostart_uninstall(
    dry_run: bool = typer.Option(False, "--dry-run"),
    method: str = typer.Option("default"),
) -> None:
    from .autostart import Autostart

    _print_plan(Autostart(method=method).uninstall(dry_run=dry_run), dry_run)


@autostart_app.command("status")
def autostart_status(method: str = typer.Option("default")) -> None:
    from .autostart import Autostart

    typer.echo("installed" if Autostart(method=method).installed() else "not installed")


# ------------------------------------------------------------------ profile
@profile_app.command("build")
def profile_build(yes: bool = typer.Option(False, "--yes", "-y", help="Write without asking")) -> None:
    from .profile import build_profile, profile_path, write_profile

    _, vault, _ = _ctx()
    new = build_profile(vault)
    p = profile_path(vault)
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "current", "new", lineterm=""))
    body_changed = [d for d in diff if d.startswith(("+", "-")) and "captured_at" not in d
                    and not d.startswith(("+++", "---")) and "自动生成于" not in d]
    if not body_changed:
        typer.echo("Core profile unchanged. / 核心画像无变化")
        return
    typer.echo("\n".join(diff))
    if yes or typer.confirm("Write this core profile? / 写入核心画像？"):
        typer.echo(f"written: {write_profile(vault, new)}")


@profile_app.command("export")
def profile_export() -> None:
    """Print the profile as plain text for agents without MCP."""
    from .profile import export_plain, profile_path

    _, vault, _ = _ctx()
    p = profile_path(vault)
    if not p.exists():
        typer.echo("No profile yet; run `memrelay profile build`.")
        raise typer.Exit(1)
    typer.echo(export_plain(p.read_text(encoding="utf-8")))


if __name__ == "__main__":
    app()
