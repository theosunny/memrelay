"""Dream: an occasional whole-vault consolidation pass (persona-design §2.9, after PilotDeck).

1. `git commit` a snapshot of the vault first (the vault becomes a git repo if it is not one).
2. Find near-duplicate active memories and propose merges (NOOP + merge_source) to the inbox.
3. List stale memories (effective confidence < 0.3) and very long notes in a `dream` reflection.
Nothing in the vault changes until you approve proposals; `rollback(sha)` restores any snapshot
as a new commit, so history is never rewritten.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import data_dir
from .consolidate import similarity
from .schema import Note, Status, effective_confidence
from .vault import Vault

GIT_ID = ["-c", "user.name=MemRelay", "-c", "user.email=memrelay@localhost", "-c", "commit.gpgsign=false"]
LONG_NOTE = 3000
DUP_THRESHOLD = 0.85


def git_available() -> bool:
    return shutil.which("git") is not None


def _git(vault: Vault, *args: str) -> str:
    r = subprocess.run(["git", *GIT_ID, "-C", str(vault.root), *args],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def _state() -> Path:
    return data_dir() / "state" / "dream-snapshots.json"


def snapshots() -> list[dict]:
    p = _state()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def snapshot(vault: Vault, message: str) -> str:
    if not git_available():
        raise RuntimeError("git is required for Dream snapshots / 需要安装 git")
    if not (vault.root / ".git").exists():
        _git(vault, "init", "-q")
    _git(vault, "add", "-A")
    _git(vault, "commit", "-q", "--allow-empty", "-m", message)
    sha = _git(vault, "rev-parse", "HEAD")
    snaps = snapshots()
    snaps.append({"sha": sha, "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                  "message": message, "vault": str(vault.root)})
    _state().parent.mkdir(parents=True, exist_ok=True)
    _state().write_text(json.dumps(snaps, indent=1, ensure_ascii=False), encoding="utf-8")
    return sha


def rollback(vault: Vault, sha: str) -> str:
    """Restore the vault to snapshot `sha` as a NEW commit (history is kept)."""
    _git(vault, "cat-file", "-e", f"{sha}^{{commit}}")
    _git(vault, "add", "-A")
    _git(vault, "commit", "-q", "--allow-empty", "-m", f"memrelay: state before rollback to {sha[:10]}")
    _git(vault, "restore", f"--source={sha}", "--staged", "--worktree", "--", ".")
    _git(vault, "commit", "-q", "--allow-empty", "-m", f"memrelay: rollback to snapshot {sha[:10]}")
    return _git(vault, "rev-parse", "HEAD")


@dataclass
class DreamReport:
    snapshot: str | None
    merges: list[str] = field(default_factory=list)  # inbox ids
    stale: list[str] = field(default_factory=list)  # vault rels
    long: list[str] = field(default_factory=list)
    reflection: str | None = None


def find_duplicates(vault: Vault, threshold: float = DUP_THRESHOLD) -> list[tuple[str, str, float]]:
    notes = [(vault.rel(p), n) for p, n in vault.iter_notes()
             if n.status == Status.active.value and n.type not in ("profile", "reflection")]
    pairs = []
    used: set[str] = set()
    for i, (ra, a) in enumerate(notes):
        for rb, b in notes[i + 1:]:
            if a.type != b.type or ra in used or rb in used:
                continue
            s = similarity(a, b)
            if s >= threshold:
                keep, drop = (ra, rb) if (a.evidence, a.confidence) >= (b.evidence, b.confidence) else (rb, ra)
                pairs.append((keep, drop, s))
                used |= {ra, rb}
    return pairs


def dream(vault: Vault, inbox, today: dt.date | None = None, take_snapshot: bool = True) -> DreamReport:
    today = today or dt.date.today()
    sha = snapshot(vault, f"memrelay dream: snapshot before consolidation {today.isoformat()}") if take_snapshot else None
    rep = DreamReport(snapshot=sha)
    for keep, drop, s in find_duplicates(vault):
        dn = Note.from_markdown(vault.resolve(drop).read_text(encoding="utf-8"))
        prop = Note(
            title=f"合并 / Merge: {dn.title}", type=dn.type,
            body=f"合并建议：`{drop}` 与 `{keep}` 内容重复（相似度 {s:.2f}）。批准后保留 `{keep}`（证据 +1），"
                 f"`{drop}` 移到 archive/merged/。\n\nMerge proposal: keep `{keep}`, retire `{drop}` to archive.",
            consolidation={"op": "NOOP", "target": keep, "reason": f"duplicate ({s:.2f})", "score": s},
            merge_source=drop, source_agent="memrelay-dream", source_channel="reflection", confidence=0.6,
        )
        r = inbox.propose(prop)
        if not r.duplicate_of:
            rep.merges.append(r.id)
    for p, n in vault.iter_notes():
        if n.status != Status.active.value or n.type in ("profile", "reflection"):
            continue
        if effective_confidence(n, today) < 0.3:
            rep.stale.append(vault.rel(p))
        if len(n.body) > LONG_NOTE:
            rep.long.append(vault.rel(p))
    lines = [f"# Dream {today.isoformat()}", "", f"快照 / Snapshot: `{sha or '-'}`（`memrelay dream rollback {sha[:10] if sha else '<sha>'}` 可回滚）", ""]
    lines += ["## 合并建议 / Merge proposals", ""] + ([f"- inbox/{m}" for m in rep.merges] or ["- （无 / none）"])
    lines += ["", "## 待确认 / Needs confirmation (c_eff < 0.3)", ""] + ([f"- [[{r.removesuffix('.md')}]]" for r in rep.stale] or ["- （无 / none）"])
    lines += ["", "## 建议拆分 / Consider splitting", ""] + ([f"- [[{r.removesuffix('.md')}]]" for r in rep.long] or ["- （无 / none）"])
    refl = Note(title=f"Dream {today.isoformat()}", type="reflection", period="dream", body="\n".join(lines),
                valid_from=today, source_agent="memrelay-dream", source_channel="reflection",
                evidence_refs=rep.stale + rep.long, confidence=0.7, importance=3)
    r = inbox.propose(refl)
    rep.reflection = r.id
    return rep
