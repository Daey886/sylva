"""Sylva Sleep Consolidation：夜間睡眠記憶昇華（補全 Consolidate 原語的「昇華」環）。

掃描低價值情景碎片（interaction + 低 importance），用 LLM 聚類歸納為穩定的
語義記憶（fact 年輪），原碎片標記 consolidated 歸檔。未配置 LLM 時優雅降級
為空操作，不阻塞核心記憶閉環。
"""

import hashlib
import json

from sylva.core import SylvaStore
from sylva.llm import complete, llm_available

_SLEEP_PROMPT = """以下是一組低頻情景記憶碎片，請把它們聚類歸納為 1-3 條穩定的語義記憶（事實或長期偏好）。
只輸出 JSON 陣列，每個元素為 {{"content": "歸納出的語義記憶"}}。沒有可歸納的則輸出 []。

碎片：
{fragments}
"""


def _parse_json_list(raw: str) -> list:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1].lstrip("json").strip() if len(parts) >= 2 else cleaned
    try:
        data = json.loads(cleaned)
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def sleep_consolidate(store: SylvaStore, limit: int = 50) -> dict[str, int]:
    """掃描碎片 → LLM 昇華 → 寫入 fact 年輪 → 標記歸檔。未配置 LLM 返回零統計。"""
    if not llm_available():
        return {"fragments": 0, "sublimated": 0, "consolidated": 0}

    fragments = store.get_low_frequency_rings(limit=limit)
    if not fragments:
        return {"fragments": 0, "sublimated": 0, "consolidated": 0}

    fragment_lines = "\n".join(f"- {f['content']}" for f in fragments)
    raw = complete(
        [
            {
                "role": "system",
                "content": "你是記憶鞏固器，把情景碎片歸納為穩定語義記憶，只輸出 JSON 陣列。",
            },
            {"role": "user", "content": _SLEEP_PROMPT.format(fragments=fragment_lines)},
        ],
        temperature=0.4,
        max_tokens=1024,
    )
    if not raw:
        return {"fragments": len(fragments), "sublimated": 0, "consolidated": 0}

    sublimated = 0
    for item in _parse_json_list(raw):
        content = str(item.get("content", "")).strip() if isinstance(item, dict) else ""
        if not content:
            continue
        ring_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if store.add_ring(
            ring_type="fact",
            content=content,
            ring_hash=ring_hash,
            importance=1.0,
        ):
            sublimated += 1

    consolidated = store.mark_consolidated([f["id"] for f in fragments])
    return {
        "fragments": len(fragments),
        "sublimated": sublimated,
        "consolidated": consolidated,
    }
