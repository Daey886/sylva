"""Sylva Search: 雙軌檢索（FTS5 關鍵詞 + FastEmbed 語義向量）。

語義召回為可選增強：未安裝 `fastembed` 時，`hybrid_search` 優雅降級為純 FTS5
關鍵詞召回，不影響核心功能。向量以 float32 BLOB 存於 SQLite 單庫，召回時
內存暴力餘弦（個人記憶規模毫秒級），不引入重型向量數據庫。
"""

import struct

from sylva.core import SylvaStore

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
_embedder = None


def semantic_available() -> bool:
    """檢查 FastEmbed 可選依賴是否已安裝。"""
    try:
        import fastembed  # noqa: F401

        return True
    except ImportError:
        return False


def _get_embedder():
    """懶加載 FastEmbed 嵌入器（首次調用才初始化，模型常駐記憶體）。"""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(model_name=MODEL_NAME)
    return _embedder


def encode(texts: list[str]) -> list[list[float]]:
    """批量嵌入文本，返回 float 向量列表。"""
    return [vec.tolist() for vec in _get_embedder().embed(texts)]


def pack(vec: list[float]) -> bytes:
    """float32 向量序列化為 BLOB。"""
    return struct.pack(f"{len(vec)}f", *vec)


def unpack(blob: bytes) -> list[float]:
    """BLOB 反序列化為 float 向量。"""
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def cosine(a: list[float], b: list[float]) -> float:
    """餘弦相似度，含零向量保護。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _ensure_embeddings(store: SylvaStore) -> None:
    """懶索引：為尚未嵌入向量的年輪批量補嵌。"""
    pending = store.get_rings_without_embedding()
    if not pending:
        return
    vecs = encode([ring["content"] for ring in pending])
    for ring, vec in zip(pending, vecs):
        store.set_embedding(ring["id"], pack(vec))


def hybrid_search(store: SylvaStore, query: str, limit: int = 5) -> list[dict]:
    """雙軌召回：FTS5 關鍵詞命中優先，語義相近補充，按 id 去重。"""
    results = store.search_fts(query, limit=limit)
    if not query.strip() or not semantic_available():
        return results
    try:
        _ensure_embeddings(store)
        qvec = encode([query])[0]
        scored = sorted(
            (
                (cosine(qvec, unpack(ring["embedding"])), ring)
                for ring in store.get_rings_with_embedding()
            ),
            key=lambda pair: -pair[0],
        )
        seen = {m["id"] for m in results}
        for _sim, ring in scored:
            if len(results) >= limit:
                break
            if ring["id"] not in seen:
                ring.pop("embedding", None)
                results.append(ring)
                seen.add(ring["id"])
    except (OSError, RuntimeError, ImportError, ValueError):
        # 語義軌道為 best-effort 增強：模型缺失、下載失敗、推理錯誤均降級為純關鍵詞召回
        return results
    return results
