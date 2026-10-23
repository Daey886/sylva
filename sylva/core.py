"""
Sylva Core: Ultra-lean SQLite WAL storage engine.
Strict ContextManager DB lifecycle, single-database architecture, zero connection leak.
"""

import os
import re
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
    decayed_at REAL,
    consolidated INTEGER DEFAULT 0, -- 0=活躍 1=已昇華歸檔
    embedding BLOB
);

-- 4. FTS5 全文索引（年轮全文搜索）
CREATE VIRTUAL TABLE IF NOT EXISTS rings_fts USING fts5(
    content,
    tokenize='trigram',
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

-- 6. Entity Relations (实体关系图谱)：三元组表，支持多跳推理
CREATE TABLE IF NOT EXISTS entity_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel_subject ON entity_relations(subject);
CREATE INDEX IF NOT EXISTS idx_rel_object ON entity_relations(object);

-- 5. Settings (功能設置)：看板可配置的鍵值對（LLM 配置等）
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_database(db_path: Path | None = None) -> Path:
    """初始化数据库并应用 Schema 与 WAL 模式。"""
    target = db_path or DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(target) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_fts(conn)
        _migrate_embedding(conn)
        _migrate_consolidated(conn)
    return target


def _migrate_fts(conn: sqlite3.Connection) -> None:
    """旧库 rings_fts 若为非 trigram 分词器，重建索引以支持中文子串召回。"""
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='rings_fts';"
    )
    row = cur.fetchone()
    if row and row["sql"] and "trigram" not in row["sql"]:
        conn.executescript(
            "DROP TRIGGER IF EXISTS rings_ai;"
            "DROP TRIGGER IF EXISTS rings_ad;"
            "DROP TRIGGER IF EXISTS rings_au;"
            "DROP TABLE IF EXISTS rings_fts;"
        )
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO rings_fts(rowid, content) SELECT id, content FROM rings;"
        )


def _migrate_embedding(conn: sqlite3.Connection) -> None:
    """舊庫 rings 表補 embedding 列（階段五語義召回新增）。"""
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(rings);")]
    if "embedding" not in cols:
        conn.execute("ALTER TABLE rings ADD COLUMN embedding BLOB;")


def _migrate_consolidated(conn: sqlite3.Connection) -> None:
    """舊庫 rings 表補 consolidated 列（睡眠昇華歸檔新增）。"""
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(rings);")]
    if "consolidated" not in cols:
        conn.execute("ALTER TABLE rings ADD COLUMN consolidated INTEGER DEFAULT 0;")


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
        """基于 SQLite FTS5 trigram 的毫秒级子串召回。支持中英文与多词 OR。"""
        if not query or not query.strip():
            return []
        safe_limit = max(1, min(limit, 50))
        # trigram 分词器最小匹配长度为 3 字符。
        # 短 token（<=6 字）保留做精准 phrase 匹配；长 token 切 3-gram 窗口，
        # 使整句 query 中的关键词子串（如「数据库」）也能召回。
        grams: list[str] = []
        for tok in re.findall(r"\w+", query, flags=re.UNICODE):
            if len(tok) < 3:
                continue
            if len(tok) <= 6:
                grams.append(tok)
            else:
                grams.extend(tok[i : i + 3] for i in range(len(tok) - 2))
        grams = list(dict.fromkeys(grams))  # 保序去重
        if not grams:
            return []

        # 构造 FTS5 查询：多 gram 间使用 OR 提升召回容错（gram 仅含 \w，无需转义）
        fts_query = " OR ".join(f'"{g}"' for g in grams)

        sql = """
        SELECT r.id, r.ring_type, r.content, r.importance, r.created_at, bm25(rings_fts) as rank
        FROM rings_fts f
        JOIN rings r ON f.rowid = r.id
        WHERE rings_fts MATCH ?
        ORDER BY rank
        LIMIT ?;
        """
        with get_connection(self.db_path) as conn:
            cur = conn.execute(sql, (fts_query, safe_limit))
            return [dict(row) for row in cur.fetchall()]

    def set_embedding(self, ring_id: int, blob: bytes) -> None:
        """寫回年輪的語義向量 BLOB。"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE rings SET embedding = ? WHERE id = ?;",
                (blob, ring_id),
            )

    def get_rings_without_embedding(self) -> list[dict]:
        """返回尚未嵌入向量的年輪（懶索引用）。"""
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id, content FROM rings WHERE embedding IS NULL;"
            )
            return [dict(row) for row in cur.fetchall()]

    def get_rings_with_embedding(self) -> list[dict]:
        """返回已嵌入向量的年輪（語義召回用）。"""
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id, ring_type, content, importance, created_at, embedding "
                "FROM rings WHERE embedding IS NOT NULL;"
            )
            return [dict(row) for row in cur.fetchall()]

    def list_rings(self, limit: int = 500, offset: int = 0) -> list[dict]:
        """列出年輪（倒序，供唯讀看板）。"""
        safe_limit = max(1, min(limit, 2000))
        safe_offset = max(0, offset)
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id, ring_type, content, importance, created_at, decayed_at "
                "FROM rings ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?;",
                (safe_limit, safe_offset),
            )
            return [dict(row) for row in cur.fetchall()]

    def add_relation(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0,
    ) -> bool:
        """寫入實體關係三元組。同三元組冪等去重（返回 True 寫入，False 已存在）。"""
        now = time.time()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id FROM entity_relations "
                "WHERE subject = ? AND predicate = ? AND object = ?;",
                (subject, predicate, object_),
            )
            if cur.fetchone():
                return False
            conn.execute(
                "INSERT INTO entity_relations "
                "(subject, predicate, object, confidence, created_at) "
                "VALUES (?, ?, ?, ?, ?);",
                (subject, predicate, object_, confidence, now),
            )
            return True

    def query_relations(self, subject: str, max_depth: int = 2) -> list[dict]:
        """遞迴 CTE 查詢實體關係，返回最多 max_depth 跳的 (subject, predicate, object, depth)。"""
        safe_depth = max(1, min(max_depth, 3))
        sql = """
        WITH RECURSIVE hops(subject, predicate, object, depth) AS (
            SELECT subject, predicate, object, 1
            FROM entity_relations WHERE subject = ?
            UNION ALL
            SELECT er.subject, er.predicate, er.object, hops.depth + 1
            FROM entity_relations er
            JOIN hops ON er.subject = hops.object
            WHERE hops.depth < ?
        )
        SELECT subject, predicate, object, depth FROM hops;
        """
        with get_connection(self.db_path) as conn:
            cur = conn.execute(sql, (subject, safe_depth))
            return [dict(row) for row in cur.fetchall()]

    def get_low_frequency_rings(
        self,
        max_importance: float = 0.5,
        limit: int = 50,
    ) -> list[dict]:
        """掃描低價值且未歸檔的情景碎片（供夜間睡眠昇華）。"""
        safe_limit = max(1, min(limit, 200))
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id, ring_type, content, importance, created_at "
                "FROM rings "
                "WHERE ring_type = 'interaction' "
                "AND consolidated = 0 "
                "AND importance < ? "
                "AND decayed_at IS NULL "
                "ORDER BY created_at ASC LIMIT ?;",
                (max_importance, safe_limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def mark_consolidated(self, ring_ids: list[int]) -> int:
        """將指定年輪標記為已昇華歸檔，返回標記數。"""
        if not ring_ids:
            return 0
        placeholders = ",".join("?" for _ in ring_ids)
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                f"UPDATE rings SET consolidated = 1 WHERE id IN ({placeholders});",
                tuple(ring_ids),
            )
            return max(0, cur.rowcount)

    def get_setting(self, key: str, default: str = "") -> str:
        """讀取功能設置項；不存在返回 default。"""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?;", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """寫入功能設置項（UPSERT）。"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
                (key, value),
            )

    def stats(self) -> dict:
        """看板統計：各表計數與資料庫大小。"""
        with get_connection(self.db_path) as conn:
            rings = conn.execute("SELECT COUNT(*) FROM rings;").fetchone()[0]
            cores = conn.execute("SELECT COUNT(*) FROM core_memory;").fetchone()[0]
            checkpoints = conn.execute("SELECT COUNT(*) FROM checkpoints;").fetchone()[0]
            relations = conn.execute("SELECT COUNT(*) FROM entity_relations;").fetchone()[0]
        return {
            "rings": rings,
            "cores": cores,
            "checkpoints": checkpoints,
            "relations": relations,
            "db_bytes": self.db_path.stat().st_size,
        }
