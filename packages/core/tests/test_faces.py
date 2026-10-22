import pytest

from memrelay.faces import Face, ensure_default_faces, get_face, list_faces, save_face
from memrelay.vault import Vault


def test_ensure_default_self_face(tmp_path):
    v = Vault(tmp_path / "vault")
    v.init()
    faces = ensure_default_faces(v)
    assert any(f.id == "self" for f in faces)
    self_face = get_face(v, "self")
    assert self_face.visibility_ceiling == "private"
    assert "answer" in self_face.capabilities
    assert "draft" in self_face.capabilities
    assert list_faces(v)[0].id == "self"


def test_save_and_reload_face(tmp_path):
    v = Vault(tmp_path / "vault")
    v.init()
    ensure_default_faces(v)
    f = Face(
        id="work",
        name="工作",
        kind="expression",
        visibility_ceiling="work",
        capabilities=["answer", "draft"],
    )
    save_face(v, f)
    loaded = get_face(v, "work")
    assert loaded.name == "工作"
    assert loaded.visibility_ceiling == "work"


def test_face_id_rejects_traversal(tmp_path):
    v = Vault(tmp_path / "vault")
    v.init()
    ensure_default_faces(v)
    with pytest.raises((KeyError, ValueError)):
        get_face(v, "../config")
    with pytest.raises(ValueError):
        save_face(v, Face(id="a/b", name="x", visibility_ceiling="public"))
