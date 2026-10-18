"""Run capture -> extract -> inbox, once or as a file watcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..extract.base import Extractor
from ..inbox import Inbox
from .base import CaptureSource, CursorState


@dataclass
class CaptureReport:
    messages: int = 0
    candidates: int = 0
    proposed: list[str] = field(default_factory=list)
    duplicates: int = 0


def run_once(source: CaptureSource, extractor: Extractor, inbox: Inbox,
             state: CursorState | None = None) -> CaptureReport:
    state = state or CursorState(source.id)
    report = CaptureReport()
    msgs = list(source.iter_new_messages(state))
    report.messages = len(msgs)
    for cand in extractor.extract(msgs):
        report.candidates += 1
        note = cand.to_note(source_agent=source.id, source_channel="local-capture",
                            extractor=extractor.name)
        r = inbox.propose(note)
        if r.duplicate_of:
            report.duplicates += 1
        else:
            report.proposed.append(r.id)
    state.save()  # only after candidates are safely in the inbox
    return report


def watch(source, extractor: Extractor, inbox: Inbox, root: Path, on_report=None,
          stop_event=None) -> None:
    """Re-run capture whenever transcript files change (watchfiles, cross-platform)."""
    from watchfiles import watch as _watch

    state = CursorState(source.id)
    rep = run_once(source, extractor, inbox, state)
    if on_report:
        on_report(rep)
    root.mkdir(parents=True, exist_ok=True)
    for changes in _watch(root, stop_event=stop_event, debounce=2000):
        if any(str(p).endswith(".jsonl") for _, p in changes):
            rep = run_once(source, extractor, inbox, state)
            if on_report:
                on_report(rep)
