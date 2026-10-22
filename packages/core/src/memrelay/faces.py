"""N faces on one vault: callable persona configs (expression or task-oriented)."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomlkit

from .vault import Vault

ALLOWED_CEILINGS = frozenset({"public", "friends", "work", "private"})
ALLOWED_KINDS = frozenset({"expression", "task"})


@dataclass
class Face:
    id: str
    name: str
    kind: str = "expression"
    visibility_ceiling: str = "private"
    capabilities: list[str] = field(default_factory=lambda: ["answer", "draft"])
    refusal_extra: str = ""

    def validate(self) -> None:
        if not self.id or "/" in self.id or "\\" in self.id or ".." in self.id or self.id.startswith("."):
            raise ValueError(f"invalid face id: {self.id!r}")
        if self.kind not in ALLOWED_KINDS:
            raise ValueError(f"invalid kind: {self.kind!r}")
        if self.visibility_ceiling not in ALLOWED_CEILINGS:
            raise ValueError(f"invalid ceiling: {self.visibility_ceiling!r}")


def faces_dir(vault: Vault) -> Path:
    return vault.root / ".memrelay" / "faces"


def _path_for(vault: Vault, face_id: str) -> Path:
    """Face files stay inside `.memrelay/faces`. Ids are a single path segment."""
    root = faces_dir(vault).resolve()
    path = (root / f"{face_id}.toml").resolve()
    if path.parent != root:
        raise ValueError(f"invalid face id: {face_id!r}")
    return path


def ensure_default_faces(vault: Vault) -> list[Face]:
    d = faces_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "self.toml").exists():
        save_face(
            vault,
            Face(
                id="self",
                name="自我",
                kind="expression",
                visibility_ceiling="private",
                capabilities=["answer", "draft"],
            ),
        )
    return list_faces(vault)


def list_faces(vault: Vault) -> list[Face]:
    d = faces_dir(vault)
    if not d.is_dir():
        return []
    out: list[Face] = []
    for p in sorted(d.glob("*.toml")):
        out.append(_load(p))
    return out


def get_face(vault: Vault, face_id: str) -> Face:
    try:
        p = _path_for(vault, face_id)
    except ValueError as ex:
        raise KeyError(face_id) from ex
    if not p.is_file():
        raise KeyError(face_id)
    return _load(p)


def save_face(vault: Vault, face: Face) -> Path:
    face.validate()
    d = faces_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    p = _path_for(vault, face.id)
    doc = tomlkit.document()
    for k, v in asdict(face).items():
        doc[k] = v
    p.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return p


def _load(path: Path) -> Face:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    face = Face(
        id=str(data["id"]),
        name=str(data.get("name") or data["id"]),
        kind=str(data.get("kind") or "expression"),
        visibility_ceiling=str(data.get("visibility_ceiling") or "private"),
        capabilities=list(data.get("capabilities") or ["answer", "draft"]),
        refusal_extra=str(data.get("refusal_extra") or ""),
    )
    face.validate()
    return face
