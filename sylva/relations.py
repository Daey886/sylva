"""Sylva Relations：實體關係抽取與多跳召回。

抽取為可選 LLM 增強：未配置 LLM 時 extract_relations 返回空列表，圖譜存儲與
查詢仍可用（關係可經 CLI / API 手動注入）。多跳召回純 SQL 遞迴 CTE，零 LLM。
"""

import json

from sylva.core import SylvaStore, get_connection
from sylva.llm import SYLVA_PERSONA, complete, llm_available

_EXTRACT_PROMPT = """從以下文本抽取實體關係三元組，僅輸出 JSON 陣列，每個元素為
{{"subject": "...", "predicate": "...", "object": "..."}}。只抽取明確陳述的關係，
不要臆測；沒有明確關係則輸出 []。

文本：
{text}
"""


def extract_relations(text: str) -> list[dict]:
    """從文本抽取三元組（可選 LLM）。未配置 LLM 或失敗返回空列表。"""
    if not llm_available() or not text.strip():
        return []
    raw = complete(
        [
            {"role": "system", "content": SYLVA_PERSONA + "此刻你作為根系梳理者，從記憶碎片中辨識實體與關係，編織記憶森林的地下根系。只輸出 JSON 陣列。"},
            {"role": "user", "content": _EXTRACT_PROMPT.format(text=text)},
        ],
        temperature=0.2,
        max_tokens=512,
    )
    if not raw:
        return []
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1].lstrip("json").strip() if len(parts) >= 2 else cleaned
    try:
        data = json.loads(cleaned)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [
        d
        for d in data
        if isinstance(d, dict)
        and all(k in d for k in ("subject", "predicate", "object"))
    ]


def ingest_relations(store: SylvaStore, text: str) -> int:
    """抽取並寫入三元組，返回新寫入條數（冪等去重）。"""
    count = 0
    for rel in extract_relations(text):
        subject = str(rel.get("subject", "")).strip()
        predicate = str(rel.get("predicate", "")).strip()
        object_ = str(rel.get("object", "")).strip()
        if not (subject and predicate and object_):
            continue
        confidence = float(rel.get("confidence", 1.0))
        if store.add_relation(subject, predicate, object_, confidence):
            count += 1
    return count


def relation_recall(
    store: SylvaStore,
    query: str,
    max_depth: int = 2,
    limit: int = 5,
) -> list[str]:
    """多跳關係召回：query 中命中的實體為起點，展開 2 跳關係，返回可讀關係句。

    起點判定為子串匹配（零 LLM）：entity_relations 中任一 subject 出現在 query 即展開。
    """
    if not query.strip():
        return []
    with get_connection(store.db_path) as conn:
        cur = conn.execute("SELECT DISTINCT subject FROM entity_relations;")
        all_subjects = [row["subject"] for row in cur.fetchall()]
    starts = [s for s in all_subjects if s and s in query]
    if not starts:
        return []

    out: list[str] = []
    seen: set[tuple] = set()
    for s in starts:
        for rel in store.query_relations(s, max_depth=max_depth):
            key = (rel["subject"], rel["predicate"], rel["object"], rel["depth"])
            if key in seen:
                continue
            seen.add(key)
            out.append(
                f"{rel['subject']} -{rel['predicate']}-> {rel['object']}"
                f"（{rel['depth']} 跳）"
            )
        if len(out) >= limit:
            break
    return out[:limit]
