"""
Sylva Core: Ultra-lean SQLite WAL storage engine.
Strict ContextManager DB lifecycle, single-database architecture, zero connection leak.
"""

import os
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_DIR = Path(os.environ.get("SYLVA_HOME", Path.home() / ".sylva"))
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "sylva.db"

SCHEMA_SQL = """
-- 1. Core Memory (树心)：常驻结构化核心事实块
CREATE TABLE IF NOT EXISTS core_memory (
    key TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    updated_at REAL NOT NULL
);

-- 2. Checkpoint (断面)：断点上下文
CREATE TABLE IF NOT EXISTS checkpoints (
    session_id TEXT PRIMARY KEY,
    context TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    updated_at REAL NOT NULL
);

-- 3. Tree Rings (年轮)：沉淀的致密事实与交互记录
CREATE TABLE IF NOT EXISTS rings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ring_type TEXT NOT NULL, -- 'fact', 'decision', 'interaction'
    content TEXT NOT NULL,
    hash TEXT UNIQUE NOT NULL, -- SHA256 去重防重复投递
    importance REAL DEFAULT 1.0,
    created_at REAL NOT NULL,
    decayed_at REAL
);

-- 4. FTS5 全文索引（年轮全文搜索）
CREATE VIRTUAL TABLE IF NOT EXISTS rings_fts USING fts5(
    content,
    content='rings',
    content_rowid='id'
);

-- 5. FTS5 触发器：增删改自动同步
CREATE TRIGGER IF NOT EXISTS rings_ai AFTER INSERT ON rings BEGIN
    INSERT INTO rings_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS rings_ad AFTER DELETE ON rings BEGIN
    INSERT INTO rings_fts(rings_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS rings_au AFTER UPDATE ON rings BEGIN
    INSERT INTO rings_fts(rings_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO rings_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


def init_database(db_path: Path | None = None) -> Path:
    """初始化数据库并应用 Schema 与 WAL 模式。"""
    target = db_path or DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(target) as conn:
        conn.executescript(SCHEMA_SQL)
    return target


@contextmanager
def get_connection(
    db_path: Path | None = None, timeout: float = 15.0
) -> Generator[sqlite3.Connection, None, None]:
    """统一安全获取 SQLite 连接，强制开启 WAL 和 NORMAL 同步。"""
    target = str(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(target, timeout=timeout, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


class SylvaStore:
    """极简年轮存储操作原语。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = init_database(db_path)

    def set_core(self, key: str, content: str) -> None:
        """更新核心记忆（树心）。"""
        now = time.time()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO core_memory (key, content, updated_at) VALUES (?, ?, ?);",
                (key, content, now),
            )

    def get_core(self, key: str) -> str | None:
        """获取核心记忆（树心）。"""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT content FROM core_memory WHERE key = ?;", (key,))
            row = cur.fetchone()
            return row["content"] if row else None

    def list_cores(self) -> dict[str, str]:
        """列出所有常驻核心记忆。"""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT key, content FROM core_memory ORDER BY key ASC;")
            return {row["key"]: row["content"] for row in cur.fetchall()}

    def set_checkpoint(self, session_id: str, context: str, metadata: str = "{}") -> None:
        """记录断点上下文。"""
        now = time.time()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints (session_id, context, metadata, updated_at) "
                "VALUES (?, ?, ?, ?);",
                (session_id, context, metadata, now),
            )

    def get_checkpoint(self, session_id: str) -> str | None:
        """获取指定断点。"""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT context FROM checkpoints WHERE session_id = ?;", (session_id,))
            row = cur.fetchone()
            return row["context"] if row else None

    def get_latest_checkpoint(self) -> tuple[str, str] | None:
        """获取最近一次断点 (session_id, context)。"""
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT session_id, context FROM checkpoints ORDER BY updated_at DESC LIMIT 1;"
            )
            row = cur.fetchone()
            return (row["session_id"], row["context"]) if row else None

    def add_ring(
        self,
        ring_type: str,
        content: str,
        ring_hash: str,
        importance: float = 1.0,
    ) -> bool:
        """写入年轮事实。带 Hash 幂等去重（返回 True 表示写入，False 表示已存在）。"""
        now = time.time()
        with get_connection(self.db_path) as conn:
            try:
                conn.execute(
                    "INSERT INTO rings (ring_type, content, hash, importance, created_at) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (ring_type, content, ring_hash, importance, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def search_fts(self, query: str, limit: int = 5) -> list[dict]:
        """基于 SQLite FTS5 的快速毫秒级全文精确检索。"""
        if not query or not query.strip():
            return []
        safe_limit = max(1, min(limit, 50))
        # 简单转义处理特殊字符
        clean_query = "".join([c for c in query if c.isalnum() or c.isspace() or c in "_-"])
        if not clean_query.strip():
            return []

        sql = """
        SELECT r.id, r.ring_type, r.content, r.importance, r.created_at, bm25(rings_fts) as rank
        FROM rings_fts f
        JOIN rings r ON f.rowid = r.id
        WHERE rings_fts MATCH ?
        ORDER BY rank
        LIMIT ?;
        """
        with get_connection(self.db_path) as conn:
            cur = conn.execute(sql, (clean_query, safe_limit))
            return [dict(row) for row in cur.fetchall()]
