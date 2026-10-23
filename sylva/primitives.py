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
from sylva.search import find_similar_pairs, hybrid_search, semantic_available


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

        # 3. Rings Recall (年輪檢索)
        matches: list[dict] = []
        if query and query.strip():
            matches = hybrid_search(self.store, query, limit=recall_limit)
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

    def ring_consolidate(
        self,
        ttl_days: float = 30.0,
        similarity_threshold: float = 0.92,
    ) -> dict[str, int]:
        """原語三：年輪整理 (Consolidate)。遺忘衰減 + 語義去重合併，保持年輪緻密。"""
        cutoff = time.time() - ttl_days * 86400.0
        merged_count = 0

        # 1. 遺忘衰減：清理過期低權重交互年輪
        with get_connection(self.store.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM rings WHERE ring_type='interaction' "
                "AND importance < 0.5 AND created_at < ?;",
                (cutoff,),
            )
            decayed_count = max(0, cur.rowcount)

        # 2. 語義去重合併：相似年輪保留權重高/更新者
        if semantic_available():
            try:
                rings = self.store.get_rings_with_embedding()
                by_id = {r["id"]: r for r in rings}
                merged: set[int] = set()
                for id_a, id_b, _sim in sorted(
                    find_similar_pairs(rings, threshold=similarity_threshold),
                    key=lambda p: -p[2],
                ):
                    if id_a in merged or id_b in merged:
                        continue
                    a, b = by_id[id_a], by_id[id_b]
                    loser = id_b if (a["importance"], a["created_at"]) >= (
                        b["importance"], b["created_at"]) else id_a
                    with get_connection(self.store.db_path) as conn:
                        conn.execute("DELETE FROM rings WHERE id = ?;", (loser,))
                    merged.add(loser)
                    merged_count += 1
            except (OSError, RuntimeError, ImportError, ValueError):
                pass  # 語義去重失敗降級：只做遺忘衰減

        return {"decayed_rings": decayed_count, "merged_rings": merged_count}
