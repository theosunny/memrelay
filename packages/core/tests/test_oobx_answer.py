from pathlib import Path

import pytest

from memrelay.faces import ensure_default_faces
from memrelay.schema import Note
from memrelay.twin import answer_as_me
from memrelay.vault import Vault


class SearchOnly:
    async def search(self, query: str, limit: int = 10):
        return ["notes/drink.md"]


@pytest.mark.asyncio
async def test_note_is_cited_when_the_model_returns_no_markers(tmp_path: Path):
    vault = Vault(tmp_path)
    vault.init()
    ensure_default_faces(vault)
    path = tmp_path / "notes" / "drink.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        Note(title="饮品", body="偏好：抹茶。", status="active", visibility="private").to_markdown(),
        encoding="utf-8",
    )

    class Bare:
        name = "bare"

        def complete(self, system: str, user: str) -> str:
            return "你喜欢抹茶。"

    result = await answer_as_me(
        "我偏好什么？", vault=vault, backend=SearchOnly(), llm=Bare(), face_id="self"
    )
    titles = [c["title"] for c in result["citations"]]
    assert "饮品" in titles
    assert "AI 分身" in result["disclosure"]
