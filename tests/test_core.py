import hashlib
import tempfile
from pathlib import Path

from sylva.core import SylvaStore, get_connection


def test_wal_mode_and_pragmas():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sylva.db"
        store = SylvaStore(db_path)
        assert store.db_path.exists()

        with get_connection(db_path) as conn:
            cur = conn.execute("PRAGMA journal_mode;")
            journal_mode = cur.fetchone()[0]
            assert journal_mode.lower() == "wal"

            cur = conn.execute("PRAGMA synchronous;")
            sync_mode = cur.fetchone()[0]
            # NORMAL is 1
            assert sync_mode == 1


def test_core_memory_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sylva.db"
        store = SylvaStore(db_path)

        assert store.get_core("user_profile") is None
        store.set_core("user_profile", "木头 - 独立开发者")
        assert store.get_core("user_profile") == "木头 - 独立开发者"

        store.set_core("project_sylva", "极简记忆引擎")
        cores = store.list_cores()
        assert len(cores) == 2
        assert cores["project_sylva"] == "极简记忆引擎"


def test_checkpoint_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sylva.db"
        store = SylvaStore(db_path)

        assert store.get_latest_checkpoint() is None
        store.set_checkpoint("sess_01", "正在编写 core.py")
        latest = store.get_latest_checkpoint()
        assert latest is not None
        assert latest[0] == "sess_01"
        assert latest[1] == "正在编写 core.py"

        # 更新
        store.set_checkpoint("sess_02", "编写完成测试通过")
        latest = store.get_latest_checkpoint()
        assert latest[0] == "sess_02"
        assert latest[1] == "编写完成测试通过"


def test_rings_dedup_and_fts():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sylva.db"
        store = SylvaStore(db_path)

        content1 = "用户偏好使用 SQLite WAL 模式，拒绝重型向量数据库"
        hash1 = hashlib.sha256(content1.encode()).hexdigest()

        # 首次插入
        inserted = store.add_ring("fact", content1, hash1)
        assert inserted is True

        # 重复插入被幂等过滤
        inserted_again = store.add_ring("fact", content1, hash1)
        assert inserted_again is False

        # FTS 全文搜索测试
        results = store.search_fts("SQLite WAL")
        assert len(results) == 1
        assert "WAL" in results[0]["content"]

        # 无关搜索
        assert len(store.search_fts("Postgres")) == 0


def test_chinese_fts_substring():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sylva.db"
        store = SylvaStore(db_path)

        content = "用户拒绝使用重型向量数据库，坚持单文件 SQLite 方案"
        h = hashlib.sha256(content.encode()).hexdigest()
        store.add_ring("fact", content, h)

        # 中文子串召回（trigram 分词器，修复前返回空）
        assert len(store.search_fts("向量数据库")) == 1
        assert len(store.search_fts("数据库")) == 1
        assert len(store.search_fts("SQLite")) == 1

        # 短 query（<3 字符）静默返回空，不抛异常
        assert store.search_fts("向量") == []
        assert store.search_fts("数据") == []

        # 无关搜索
        assert store.search_fts("Postgres") == []
