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
