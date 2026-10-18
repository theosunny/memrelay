"""`memrelay connect --all`: auto-discover agents, preview each change, ask, apply."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from .adapters import ADAPTERS, AgentAdapter, Change, Env, ServerSpec, is_guided


@dataclass
class WizardResult:
    applied: list[Change] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    guided: list[str] = field(default_factory=list)


def discover(env: Env | None = None) -> list[tuple[AgentAdapter, bool]]:
    out = []
    for cls in ADAPTERS.values():
        a = cls(env)
        out.append((a, (not is_guided(a)) and a.detect()))
    return out


def run_wizard(
    spec: ServerSpec,
    confirm: Callable[[str], bool],
    echo: Callable[[str], None] = print,
    env: Env | None = None,
    yes: bool = False,
    include_guided: bool = True,
) -> WizardResult:
    res = WizardResult()
    found = discover(env)
    echo("检测到的智能体 / Detected agents:")
    for a, ok in found:
        if is_guided(a):
            continue
        echo(f"  [{'x' if ok else ' '}] {a.id:14} {a.name:24} {a.config_path()}")
    echo(f"MCP 启动命令 / server command: {spec.command} {' '.join(spec.args)}\n")

    for a, ok in found:
        if is_guided(a) or not ok:
            continue
        try:
            preview = a.install(spec, dry_run=True)
        except (ValueError, RuntimeError) as e:
            res.errors[a.id] = str(e)
            echo(f"! {a.id}: {e}")
            continue
        if preview.action == "noop":
            res.already.append(a.id)
            echo(f"= {a.id}: 已接入 / already connected")
            continue
        echo(f"→ {a.name}: {preview.path}")
        if preview.before is not None:
            echo(f"    当前 / current: {json.dumps(preview.before, ensure_ascii=False)}")
        echo(f"    写入 / write:   {json.dumps(preview.after, ensure_ascii=False)}")
        if preview.note:
            echo(f"    注意 / note: {preview.note}")
        if yes or confirm(f"接入 {a.name}？/ Connect {a.name}?"):
            ch = a.install(spec)
            res.applied.append(ch)
            echo(f"    ✓ 已写入，备份 / backup: {ch.backup}")
        else:
            res.skipped.append(a.id)

    if include_guided:
        guided = [a for a, _ in found if is_guided(a)]
        if guided:
            echo("\n以下客户端没有公开的配置文件路径，请按步骤手动添加 / Manual setup:")
            for a in guided:
                echo(a.install(spec).note or "")
                res.guided.append(a.id)
    echo(f"完成 / done: applied={len(res.applied)} skipped={len(res.skipped)} "
         f"already={len(res.already)} errors={len(res.errors)}")
    return res
