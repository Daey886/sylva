"""
Sylva Primitives: The three foundational operations.
1. inject  - assemble structured context (Core + Checkpoint + Recall) before LLM call.
2. ingest  - atomic write facts/interactions into tree rings with idempotency.
3. ring    - consolidate memories, decay old ephemeral rings, and resolve conflicts.
"""

import hashlib
import time
from typing import Any

from sylva.core import SylvaStore, get_connection


class SylvaKernel:
    """Sylva 认知微内核。"""

    def __init__(self, store: SylvaStore | None = None):
        self.store = store or SylvaStore()

    def inject(
        self,
        query: str = "",
        session_id: str | None = None,
        max_chars: int = 4000,
        recall_limit: int = 5,
    ) -> dict[str, Any]:
        """原语一：请求前组装上下文。
        包含：CoreMemory (树心) + Checkpoint (断点) + Rings (召回相关年轮)。
        输出硬性字符截断约束，严防打爆 Prompt。
        """
        blocks: list[str] = []

        # 1. Core Memory (树心常驻)
        cores = self.store.list_cores()
        if cores:
            core_lines = ["[Core Memory]"]
            for k, v in cores.items():
                core_lines.append(f"- {k}: {v}")
            blocks.append("\n".join(core_lines))

        # 2. Checkpoint (断点恢复)
        cp_context = None
        if session_id:
            cp_context = self.store.get_checkpoint(session_id)
        if not cp_context:
            latest = self.store.get_latest_checkpoint()
            if latest:
                cp_context = f"[Last Session: {latest[0]}]\n{latest[1]}"

        if cp_context:
            blocks.append(f"[Checkpoint]\n{cp_context}")

        # 3. Rings Recall (年轮检索)
        matches: list[dict] = []
        if query and query.strip():
            matches = self.store.search_fts(query, limit=recall_limit)
            if matches:
                ring_lines = ["[Relevant Tree Rings]"]
                for m in matches:
                    ring_lines.append(f"- ({m['ring_type']}) {m['content']}")
                blocks.append("\n".join(ring_lines))

        full_context = "\n\n".join(blocks).strip()

        # 硬性截断约束
        if len(full_context) > max_chars:
            full_context = full_context[:max_chars] + "\n...[Truncated by Sylva]"

        return {
            "context": full_context,
            "char_count": len(full_context),
            "has_core": bool(cores),
            "has_checkpoint": bool(cp_context),
            "recalled_count": len(matches),
        }

    def ingest(
        self,
        content: str,
        ring_type: str = "fact",
        importance: float = 1.0,
    ) -> bool:
        """原语二：原子写入年轮。
        返回 True 表示成功写入，False 表示已存在（防重复）。
        """
        clean_content = content.strip()
        if not clean_content:
            return False

        ring_hash = hashlib.sha256(clean_content.encode("utf-8")).hexdigest()
        return self.store.add_ring(
            ring_type=ring_type,
            content=clean_content,
            ring_hash=ring_hash,
            importance=importance,
        )

    def ring_consolidate(self, ttl_days: float = 30.0) -> dict[str, int]:
        """原语三：年轮整理 (Consolidate)。
        清理过期低权重临时交互，保持年轮致密。
        """
        now = time.time()
        ttl_seconds = ttl_days * 86400.0
        cutoff_time = now - ttl_seconds

        with get_connection(self.store.db_path) as conn:
            # 软清理/标记衰减超期的低重要度交互年轮
            cur = conn.execute(
                """
                DELETE FROM rings
                WHERE ring_type = 'interaction'
                  AND importance < 0.5
                  AND created_at < ?;
                """,
                (cutoff_time,),
            )
            deleted_count = cur.rowcount

        return {
            "decayed_rings": max(0, deleted_count),
        }
