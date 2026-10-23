"""夜間睡眠昇華測試：碎片掃描、歸檔標記與 LLM 降級/昇華。"""
from __future__ import annotations

import hashlib

import pytest

from sylva.consolidate import sleep_consolidate
from sylva.core import SylvaStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("SYLVA_LLM_API_KEY", raising=False)
    return SylvaStore(tmp_path / "test.db")


def _add_interaction(store, content, importance=0.3):
    store.add_ring(
        ring_type="interaction",
        content=content,
        ring_hash=hashlib.sha256(content.encode()).hexdigest(),
        importance=importance,
    )


def test_get_low_frequency_rings(store):
    _add_interaction(store, "中午吃了蘇二娃", importance=0.3)
    _add_interaction(store, "通勤40分鐘", importance=0.4)
    store.add_ring("fact", "開發Sylva", hashlib.sha256(b"x").hexdigest(), 1.0)
    rings = store.get_low_frequency_rings()
    contents = [r["content"] for r in rings]
    assert "中午吃了蘇二娃" in contents
    assert "通勤40分鐘" in contents
    assert "開發Sylva" not in contents


def test_mark_consolidated(store):
    _add_interaction(store, "碎片A")
    _add_interaction(store, "碎片B")
    ids = [r["id"] for r in store.get_low_frequency_rings()]
    assert store.mark_consolidated(ids) == 2
    assert store.get_low_frequency_rings() == []


def test_sleep_consolidate_no_llm_returns_zero(store):
    _add_interaction(store, "碎片A")
    result = sleep_consolidate(store)
    assert result == {"fragments": 0, "sublimated": 0, "consolidated": 0}


def test_sleep_consolidate_with_llm(store, monkeypatch):
    monkeypatch.setenv("SYLVA_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SYLVA_LLM_MODEL", "test-model")
    _add_interaction(store, "中午吃蘇二娃")
    _add_interaction(store, "通勤40分鐘")

    import sylva.consolidate as mod

    monkeypatch.setattr(
        mod,
        "complete",
        lambda messages, **kw: '[{"content": "用戶常去蘇二娃用餐"}]',
    )

    result = sleep_consolidate(store)
    assert result["fragments"] == 2
    assert result["sublimated"] == 1
    assert result["consolidated"] == 2
    facts = [r for r in store.list_rings() if r["ring_type"] == "fact"]
    assert any("蘇二娃" in r["content"] for r in facts)
