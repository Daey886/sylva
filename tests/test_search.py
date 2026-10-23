import hashlib
import tempfile
from pathlib import Path

import pytest

from sylva import search
from sylva.core import SylvaStore


def test_pack_unpack_roundtrip():
    vec = [0.1, -0.2, 0.3, 0.75]
    assert search.unpack(search.pack(vec)) == pytest.approx(vec)


def test_cosine():
    assert search.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert search.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    # 零向量保护：不得除零
    assert search.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def _store_with_rings(db_path: Path) -> SylvaStore:
    store = SylvaStore(db_path)
    for content, ring_type in [
        ("用户偏好 SQLite WAL 模式，拒绝重型向量数据库", "fact"),
        ("年轮整理需定期去重合并", "decision"),
    ]:
        h = hashlib.sha256(content.encode()).hexdigest()
        store.add_ring(ring_type, content, h)
    return store


def test_hybrid_degrades_to_fts_without_fastembed(monkeypatch):
    monkeypatch.setattr(search, "semantic_available", lambda: False)
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _store_with_rings(Path(tmpdir) / "s.db")
        results = search.hybrid_search(store, "数据库", limit=5)
        # 仅 FTS5 命中一条，无语义补充
        assert len(results) == 1
        assert "SQLite" in results[0]["content"]


def test_hybrid_merges_semantic_and_dedupes(monkeypatch):
    # 所有文本嵌入同一向量（相似度全 1），隔离真实模型
    monkeypatch.setattr(search, "semantic_available", lambda: True)
    monkeypatch.setattr(
        search, "encode", lambda texts: [[1.0, 0.0, 0.0, 0.0] for _ in texts]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _store_with_rings(Path(tmpdir) / "s.db")
        results = search.hybrid_search(store, "数据库", limit=2)
        # FTS5 命中在前，语义补充在后，去重后总数 <= limit
        assert len(results) == 2
        assert "SQLite" in results[0]["content"]
        assert "年轮" in results[1]["content"]
        # 向量 BLOB 不泄漏到上层结果
        assert all("embedding" not in r for r in results)


def test_hybrid_semantic_failure_degrades(monkeypatch):
    def boom(_texts):
        raise RuntimeError("模型下载失败")

    monkeypatch.setattr(search, "semantic_available", lambda: True)
    monkeypatch.setattr(search, "encode", boom)
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _store_with_rings(Path(tmpdir) / "s.db")
        # 语义轨道抛异常时静默降级为纯 FTS5，不阻断主流程
        results = search.hybrid_search(store, "数据库", limit=5)
        assert len(results) == 1
        assert "SQLite" in results[0]["content"]


def test_lazy_embedding_persists(monkeypatch):
    """懒索引：语义召回触发后，无向量的年轮被补嵌写回。"""
    monkeypatch.setattr(search, "semantic_available", lambda: True)
    monkeypatch.setattr(
        search, "encode", lambda texts: [[0.5, 0.5, 0.5, 0.5] for _ in texts]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        store = _store_with_rings(Path(tmpdir) / "s.db")
        assert store.get_rings_without_embedding() != []  # 初始均无向量
        search.hybrid_search(store, "数据库", limit=2)
        # 召回触发懒索引后，全部补嵌
        assert store.get_rings_without_embedding() == []
        assert len(store.get_rings_with_embedding()) == 2


def test_find_similar_pairs():
    pytest.importorskip("numpy")
    rings = [
        {"id": 1, "embedding": search.pack([1.0, 0.0, 0.0])},
        {"id": 2, "embedding": search.pack([1.0, 0.0, 0.0])},  # 与 1 相同
        {"id": 3, "embedding": search.pack([0.0, 1.0, 0.0])},  # 与 1 正交
    ]
    pairs = search.find_similar_pairs(rings, threshold=0.9)
    assert len(pairs) == 1
    assert {pairs[0][0], pairs[0][1]} == {1, 2}
    assert pairs[0][2] > 0.99


def test_find_similar_pairs_trivial():
    assert search.find_similar_pairs([]) == []
    assert search.find_similar_pairs([{"id": 1, "embedding": b""}]) == []
