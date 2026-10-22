"""Review policy: auto / assist / strict (persona-design + product default = automatic).

Default ``auto``: trusted local capture and allowlisted MCP agents auto-approve into the
vault when confidence is high enough and safety rails pass. Quarantine (stay in inbox as
``needs_attention``): secrets/PII redaction, injection flags, low confidence,
sensitivity personal/secret (not mere visibility=private — that is the default),
notes about other people, SUPERSEDE contradictions.

``assist``: same auto path for trusted+high-conf only; everything else waits in inbox.
``strict``: never auto-approve (legacy behaviour).

Never auto-sends. Never exposes forget/delete. ``draft_as_me`` stays draft-only.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import ReviewConfig, data_dir
from .schema import Note, Sensitivity

log = logging.getLogger(__name__)

MODES = ("auto", "assist", "strict")


def normalized_mode(cfg: ReviewConfig) -> str:
    m = (cfg.mode or "auto").strip().lower()
    return m if m in MODES else "auto"


@dataclass
class Decision:
    action: str  # "auto_approve" | "needs_attention" | "pending"
    reasons: list[str] = field(default_factory=list)

    @property
    def auto(self) -> bool:
        return self.action == "auto_approve"


def _agent_allowed(name: str, allow: list[str]) -> bool:
    if "*" in allow:
        return True
    return name in allow


def is_trusted_source(note: Note, cfg: ReviewConfig) -> bool:
    """Whether this proposal is eligible for auto under assist/auto (before safety rails)."""
    agent = note.source_agent or ""
    channel = note.source_channel or ""
    if channel == "local-capture" and agent in cfg.trusted_capture_agents:
        return True
    if channel == "mcp" and _agent_allowed(agent, cfg.trusted_mcp_agents):
        return True
    if normalized_mode(cfg) == "auto":
        if cfg.auto_memrelay_generated and agent.startswith("memrelay-"):
            return True
        if cfg.auto_export_import and channel == "export-import":
            return note.confidence >= cfg.export_min_confidence
    return False


def safety_holds(note: Note, vault=None) -> list[str]:
    """Return hold reasons; empty means safety rails pass."""
    reasons: list[str] = []
    if note.confidence < 0:  # defensive
        reasons.append("invalid_confidence")
    flags = set(note.flags or [])
    if "redacted" in flags or note.sensitivity == Sensitivity.secret.value:
        reasons.append("secret_or_redacted")
    if note.sensitivity == Sensitivity.personal.value:
        reasons.append("sensitivity_personal")
    # private visibility alone is OK for auto (most memories are private); secret/personal held above
    if any(f.startswith("possible_injection") or f == "possible_injection" for f in flags) or "injection" in flags:
        reasons.append("injection_flag")
    if str(note.type) == "person":
        reasons.append("about_other_people")
    # SUPERSEDE would change another memory's validity — always ask a human
    if vault is not None:
        try:
            from .consolidate import Op, RuleJudge, neighbors

            plan = RuleJudge().decide(note, neighbors(vault, note))
            if plan.op == Op.SUPERSEDE:
                reasons.append("would_supersede")
        except Exception as e:  # never block propose on judge failure
            log.debug("supersede check skipped: %s", e)
    # Profile-file replacements: always human (can overwrite style card / principles)
    extra = note.model_extra or {}
    if extra.get("profile_file"):
        reasons.append("profile_file_replace")
    if extra.get("consolidation", {}).get("op") == "SUPERSEDE":
        reasons.append("would_supersede")
    return reasons


def decide(note: Note, cfg: ReviewConfig, vault=None) -> Decision:
    mode = normalized_mode(cfg)
    if mode == "strict":
        return Decision("pending", ["strict_mode"])
    floor = cfg.min_confidence
    if note.source_channel == "export-import" and mode == "auto":
        floor = max(floor, cfg.export_min_confidence)
    holds = safety_holds(note, vault)
    if holds:
        return Decision("needs_attention", holds)
    if note.confidence < floor:
        return Decision("needs_attention", ["low_confidence"])
    if not is_trusted_source(note, cfg):
        return Decision("pending", ["untrusted_source"])
    return Decision("auto_approve", ["trusted_high_confidence"])


# ----- auto-applied log + notifications --------------------------------------
def _log_path() -> Path:
    return data_dir() / "state" / "auto-applied.jsonl"


def record_auto(item_id: str, note: Note, dest: str, reasons: list[str]) -> None:
    p = _log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "id": item_id,
        "title": note.title,
        "type": note.type,
        "source_agent": note.source_agent,
        "source_channel": note.source_channel,
        "dest": dest,
        "reasons": reasons,
        "confidence": note.confidence,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def iter_auto(since: dt.datetime | None = None) -> list[dict]:
    p = _log_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since:
            try:
                ts = dt.datetime.fromisoformat(rec["ts"])
            except (KeyError, ValueError):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=dt.UTC)
            if ts < since:
                continue
        out.append(rec)
    return out


def notify(title: str, body: str) -> bool:
    """Best-effort desktop notification; never raises."""
    try:
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "--app-name=MemRelay", title, body],
                           capture_output=True, timeout=5)
            return True
        if shutil.which("osascript"):
            script = f'display notification {json.dumps(body)} with title {json.dumps(title)}'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return True
    except (OSError, subprocess.SubprocessError):
        return False
    return False


@dataclass
class AutoResult:
    status: str  # duplicate | pending_review | needs_attention | auto_approved
    id: str
    path: Path | None = None
    dest: str | None = None
    reasons: list[str] = field(default_factory=list)
    duplicate_of: str | None = None
    redacted: list[str] | None = None
    flags: list[str] | None = None

    def as_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if v is not None and k != "path"}
        if self.path is not None:
            d["path"] = str(self.path)
        return d


def apply_policy(inbox, note: Note, propose_result, cfg: ReviewConfig) -> AutoResult:
    """Run after inbox.propose. May approve immediately or mark needs_attention."""
    if propose_result.duplicate_of:
        return AutoResult("duplicate", propose_result.id, propose_result.path,
                          duplicate_of=propose_result.duplicate_of,
                          redacted=propose_result.redacted, flags=propose_result.flags)
    # Re-load note as stored (flags/sensitivity may have been updated by propose)
    stored = inbox.get(propose_result.id)
    decision = decide(stored, cfg, vault=inbox.vault)
    if decision.action == "auto_approve":
        dest = inbox.approve(propose_result.id, trusted=True)
        rel = inbox.vault.rel(dest)
        record_auto(propose_result.id, stored, rel, decision.reasons)
        if cfg.notify:
            notify("MemRelay 已自动写入记忆", f"{stored.title} → {rel}")
        return AutoResult("auto_approved", propose_result.id, dest, dest=rel, reasons=decision.reasons,
                          redacted=propose_result.redacted, flags=propose_result.flags)
    if decision.action == "needs_attention":
        flags = sorted(set((stored.flags or []) + ["needs_attention"]))
        updated = Note(**{**stored.model_dump(), "flags": flags,
                          "hold_reason": ", ".join(decision.reasons)}, body=stored.body)
        propose_result.path.write_text(updated.to_markdown(), encoding="utf-8")
        return AutoResult("needs_attention", propose_result.id, propose_result.path,
                          reasons=decision.reasons, redacted=propose_result.redacted, flags=flags)
    return AutoResult("pending_review", propose_result.id, propose_result.path,
                      reasons=decision.reasons, redacted=propose_result.redacted, flags=propose_result.flags)


def propose_with_policy(inbox, note: Note, cfg) -> AutoResult:
    """Single entry: propose then apply review.mode policy."""
    review = cfg.review if hasattr(cfg, "review") else ReviewConfig()
    return apply_policy(inbox, note, inbox.propose(note), review)


def weekly_auto_digest(days: int = 7) -> str:
    since = dt.datetime.now().astimezone() - dt.timedelta(days=days)
    rows = iter_auto(since)
    if not rows:
        return f"过去 {days} 天没有自动写入的记忆。 / No auto-applied memories in the last {days} days."
    lines = [f"# 自动写入摘要 / Auto-applied digest ({days}d)", "",
             f"共 {len(rows)} 条。可用 `memrelay inbox` 查看仍待审核的条目；"
             f"严格模式：`review.mode = \"strict\"`。", ""]
    for r in rows[-50:]:
        lines.append(f"- {r.get('ts', '')[:16]}  **{r.get('title', '')}** → `{r.get('dest', '')}` "
                     f"({r.get('source_agent')}/{r.get('source_channel')}, conf {r.get('confidence')})")
    return "\n".join(lines) + "\n"
