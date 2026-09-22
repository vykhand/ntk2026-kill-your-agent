"""Act 4 plumbing against an in-memory fake of `beta.memory_stores` (no Azure)."""

import itertools
from types import SimpleNamespace

import pytest
from azure.ai.projects.models import MemoryItem, MemoryItemKind

from lipica import spomin


class FakeMemoryStores:
    def __init__(self):
        self.items: dict[str, MemoryItem] = {}
        self._ids = itertools.count(1)

    async def create_memory(self, *, name, scope, content, kind):
        m = MemoryItem({"memory_id": f"m{next(self._ids)}", "updated_at": 1_700_000_000, "scope": scope, "content": content, "kind": str(getattr(kind, "value", kind))})
        self.items[m.memory_id] = m
        return m

    async def list_memories(self, *, name, scope, kind=None, limit=None):
        for m in list(self.items.values()):
            if m.scope == scope and (kind is None or m.kind == str(getattr(kind, "value", kind))):
                yield m

    async def delete_memory(self, *, name, memory_id):
        return SimpleNamespace(deleted=self.items.pop(memory_id, None) is not None)

    async def delete_scope(self, *, name, scope):
        gone = [k for k, m in self.items.items() if m.scope == scope]
        for k in gone:
            del self.items[k]
        return SimpleNamespace(deleted=True, scope=scope)


@pytest.fixture
def sp(tmp_path, monkeypatch):
    fake = FakeMemoryStores()
    pc = SimpleNamespace(beta=SimpleNamespace(memory_stores=fake))
    monkeypatch.setattr(spomin, "SNAP_DIR", tmp_path)
    return spomin.Spomin(pc, store="test"), fake


async def test_definition_matches_the_plan(sp):
    d = sp[0].definicija().as_dict()
    assert d["chat_model"] == "gpt-5.4-mini" and d["embedding_model"] == "text-embedding-3-large"
    assert d["options"]["procedural_memory_enabled"] is True and d["options"]["default_ttl_seconds"] == 0


async def test_snapshot_clean_restore_round_trip(sp, tmp_path):
    s, fake = sp
    await s.zapisi("referent", spomin.NAVODILO, MemoryItemKind.PROCEDURAL)
    await s.zapisi("ID-TEST-005", "Stranka želi obvestila po e-pošti.", MemoryItemKind.USER_PROFILE)
    data = await s.posnetek("post-coaching", ["referent", "ID-TEST-005"])
    assert (tmp_path / "post-coaching.json").exists()
    assert [d["kind"] for d in data["referent"]] == ["procedural"]

    assert await s.pozabi("ID-TEST-005") and await s.seznam("ID-TEST-005") == []
    assert len(await s.seznam("referent")) == 1  # the office scope is untouched by a citizen's deletion

    await s.pocisti(["referent"])
    assert await s.seznam("referent") == []
    out = await s.obnovi("post-coaching")
    assert [m.content for m in out["referent"]] == [spomin.NAVODILO]
    assert (await s.seznam("ID-TEST-005"))[0].kind == "user_profile"
    assert out["referent"][0].memory_id != data["referent"][0]["memory_id"]  # ids change on restore


async def test_delete_one_item(sp):
    s, _ = sp
    m = await s.zapisi("referent", "x")
    assert await s.izbrisi(m.memory_id) and not await s.izbrisi(m.memory_id)
