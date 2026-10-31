"""Sylva Sleep Consolidation：夜間睡眠記憶昇華（補全 Consolidate 原語的「昇華」環）。

掃描低價值情景碎片（interaction + 低 importance），用 LLM 聚類歸納為穩定的
語義記憶（fact 年輪），原碎片標記 consolidated 歸檔。未配置 LLM 時優雅降級
為空操作，不阻塞核心記憶閉環。
"""

import hashlib
import json
from typing import Any

from sylva.core import SylvaStore
from sylva.llm import SYLVA_PERSONA, complete, llm_available

_SLEEP_PROMPT = """以下是一組低頻情景記憶碎片，請分析並歸納：
1. 提取 1-3 條穩定的語義記憶（客觀事實）。
2. 若發現用戶的糾正、批評、禁忌、踩坑教訓或長期目標/偏好，提煉為心智條目 (mental_models)。

只輸出嚴格的 JSON 物件，格式如下：
{{{{
  "facts": [{{"content": "客觀語義事實"}}],
  "mentals": [
    {{{{
      "module": "preference" | "redline" | "goal" | "boundary",
      "topic": "簡短主題詞(如 actual_budget, code_style)",
      "principle": "核心準則或紅線要求",
      "rationale": "歷史踩坑或由來"
    }}}}
  ]
}}}}
若無可歸納的條目，對應陣列為空 []。不得輸出多餘文字。

碎片：
{fragments}
"""


def _parse_json_dict(raw: str) -> dict | list:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1].lstrip("json").strip() if len(parts) >= 2 else cleaned
    try:
        data = json.loads(cleaned)
    except ValueError:
        return {}
    return data if isinstance(data, (dict, list)) else {}


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
                "content": SYLVA_PERSONA + "此刻你作為夜間沉睡者，讓白天的瑣碎記憶沉澱昇華為新的年輪。只輸出 JSON 陣列。",
            },
            {"role": "user", "content": _SLEEP_PROMPT.format(fragments=fragment_lines)},
        ],
        temperature=0.4,
        max_tokens=1024,
    )
    if not raw:
        return {"fragments": len(fragments), "sublimated": 0, "consolidated": 0, "mentals": 0}

    data = _parse_json_dict(raw)
    facts: list[Any] = []
    mentals: list[Any] = []
    if isinstance(data, list):
        facts = data
    elif isinstance(data, dict):
        facts = data.get("facts", [])
        mentals = data.get("mentals", [])

    sublimated = 0
    for item in facts:
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

    mental_created = 0
    for m in mentals:
        if isinstance(m, dict) and m.get("module") and m.get("principle"):
            mod = str(m.get("module", "preference")).lower()
            if mod not in ("preference", "redline", "goal", "boundary"):
                mod = "preference"
            store.add_mental_model(
                module=mod,
                topic=str(m.get("topic", "general")),
                principle=str(m["principle"]).strip(),
                rationale=str(m.get("rationale", "")).strip(),
            )
            mental_created += 1

    consolidated = store.mark_consolidated([f["id"] for f in fragments])
    return {
        "fragments": len(fragments),
        "sublimated": sublimated,
        "consolidated": consolidated,
        "mentals": mental_created,
    }
