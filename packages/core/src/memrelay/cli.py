"""`memrelay` command line."""

from __future__ import annotations

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
connect_app = typer.Typer(help="Connect agents (write MCP configs) / 接入智能体", no_args_is_help=True)
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
) -> None:
    _, vault, inbox = _ctx()
    edits = {k: v for k, v in {"type": type, "title": title, "visibility": visibility}.items() if v}
    for iid in item_ids:
        dest = inbox.approve(iid, edits=edits)
        typer.echo(f"approved {iid} -> {vault.rel(dest)}")


@inbox_app.command("reject")
def inbox_reject(item_ids: list[str], reason: str | None = typer.Option(None, "--reason")) -> None:
    _, vault, inbox = _ctx()
    for iid in item_ids:
        dest = inbox.reject(iid, reason)
        typer.echo(f"rejected {iid} -> {vault.rel(dest)}")


# ------------------------------------------------------------------ connect
@connect_app.command("list")
def connect_list() -> None:
    from .adapters import ADAPTERS

    for aid, cls in ADAPTERS.items():
        a = cls()
        typer.echo(f"{aid:15} {a.name:15} detected={a.detect()!s:5} installed={a.installed() is not None!s:5}")
        typer.echo(f"{'':15} {a.config_path()}  (source: {a.sources[0]})")


def _print_change(ch) -> None:
    tag = "DRY-RUN " if ch.dry_run else ""
    typer.echo(f"{tag}{ch.action}: {ch.adapter} -> {ch.path}")
    if ch.after is not None:
        typer.echo("  " + json.dumps(ch.after, ensure_ascii=False))
    if ch.backup:
        typer.echo(f"  backup: {ch.backup}")
    if ch.note:
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
