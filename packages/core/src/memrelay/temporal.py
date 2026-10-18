"""Temporal validity (persona-design §2.8, after Graphiti's bi-temporal edges).

A note is valid at `as_of` when valid_from <= as_of < valid_to (open ends allowed).
"Now" queries only see `active` notes; point-in-time queries also see `superseded` ones,
because a superseded fact was true during its own window ("where did I live in 2024?").
"""

from __future__ import annotations

import datetime as dt

from .schema import Note, Sensitivity, Status


def parse_date(v: str | dt.date | None) -> dt.date | None:
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


def valid_at(note: Note, as_of: dt.date) -> bool:
    if note.valid_from and as_of < note.valid_from:
        return False
    if note.valid_to and as_of >= note.valid_to:
        return False
    return True


def visible(note: Note, today: dt.date, as_of: dt.date | None = None) -> bool:
    """Gateway read policy: reviewed, not secret, and valid at the requested time."""
    if note.sensitivity == Sensitivity.secret.value:
        return False
    if as_of is None or as_of >= today:
        return note.status == Status.active.value and valid_at(note, today)
    if note.status not in (Status.active.value, Status.superseded.value):
        return False
    if note.valid_from is None and note.captured_at.date() > as_of and note.status == Status.active.value:
        # no stated start: we only know it since we captured it
        return False
    return valid_at(note, as_of)
