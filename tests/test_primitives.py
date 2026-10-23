import tempfile
import time
from pathlib import Path

from sylva.core import SylvaStore
from sylva.primitives import SylvaKernel


def test_kernel_inject_full_spectrum():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_kernel.db"
        store = SylvaStore(db_path)
        kernel = SylvaKernel(store)

        # 1. 注入核心
        store.set_core("developer", "木头 (Daey886)")
        store.set_core("preference", "极简单库 WAL")

        # 2. 注入断点
        store.set_checkpoint("sess_main", "上一次任务停在 primitives 编写")

        # 3. 注入年轮
        kernel.ingest("用户要求禁止裸连接，必须通过上下文管理器访问 SQLite", ring_type="rule", importance=1.0)
        kernel.ingest("系统使用 FTS5 进行毫秒级全文精确匹配", ring_type="fact", importance=0.8)

        # 触发 inject
        result = kernel.inject(query="SQLite FTS5", session_id="sess_main")

        assert result["has_core"] is True
        assert result["has_checkpoint"] is True
        assert result["recalled_count"] >= 1
        assert "[Core Memory]" in result["context"]
        assert "Daey886" in result["context"]
        assert "[Checkpoint]" in result["context"]
        assert "primitives 编写" in result["context"]
        assert "[Relevant Tree Rings]" in result["context"]


def test_kernel_inject_truncation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_kernel.db"
        store = SylvaStore(db_path)
        kernel = SylvaKernel(store)

        store.set_core("huge_text", "A" * 500)
        result = kernel.inject(max_chars=100)

        assert result["char_count"] <= 150
        assert "...[Truncated by Sylva]" in result["context"]


def test_kernel_ingest_and_consolidation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_kernel.db"
        store = SylvaStore(db_path)
        kernel = SylvaKernel(store)

        # 插入高价值事实
        res1 = kernel.ingest("长期规则：禁止裸连接", ring_type="rule", importance=1.0)
        assert res1 is True

        # 重复插入
        res2 = kernel.ingest("长期规则：禁止裸连接", ring_type="rule", importance=1.0)
        assert res2 is False

        # 插入过期临时交互
        old_time = time.time() - (35 * 86400)
        # 直接通过底层插入一条老数据
        from sylva.core import get_connection

        with get_connection(store.db_path) as conn:
            conn.execute(
                "INSERT INTO rings (ring_type, content, hash, importance, created_at) "
                "VALUES ('interaction', '临时会话回声', 'hash_temp_old', 0.2, ?)",
                (old_time,),
            )

        # 执行整理
        report = kernel.ring_consolidate(ttl_days=30.0)
        assert report["decayed_rings"] == 1

        # 验证高价值事实仍在
        assert store.search_fts("禁止裸连接") != []


def test_ring_consolidate_semantic_merge(monkeypatch):
    from sylva import primitives, search

    # ring_consolidate 在 primitives 模組內，須 mock primitives 的綁定引用
    # （from sylva.search import semantic_available 是獨立引用，mock search 模組無效）
    monkeypatch.setattr(primitives, "semantic_available", lambda: True)
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_semantic.db"
        store = SylvaStore(db_path)
        kernel = SylvaKernel(store)

        # 两条语义相似但内容不同的年轮
        kernel.ingest("用户偏好 SQLite 单文件", ring_type="fact", importance=0.6)
        kernel.ingest(
            "用户偏好 SQLite 单文件存储方案", ring_type="fact", importance=0.9
        )

        # 补嵌向量（用 pack 构造，不依赖真实模型）
        for ring in store.get_rings_without_embedding():
            store.set_embedding(ring["id"], search.pack([1.0, 0.0, 0.0]))

        all_rings = store.get_rings_with_embedding()
        id_low = min(r["id"] for r in all_rings)
        id_high = max(r["id"] for r in all_rings)

        # mock 相似对查找，隔离真实模型
        monkeypatch.setattr(
            primitives,
            "find_similar_pairs",
            lambda rings, threshold=0.92: [(id_high, id_low, 0.95)],
        )

        report = kernel.ring_consolidate()
        assert report["merged_rings"] == 1

        remaining_ids = {r["id"] for r in store.get_rings_with_embedding()}
        assert id_high in remaining_ids  # 保留 importance 高者
        assert id_low not in remaining_ids  # 删除 importance 低者
