"""Sylva Instant Reflexion: 即時反思與因果歸因引擎。
當前置執行報錯、遭遇阻斷或用戶批評糾正時，觸發即時反思 (Instant Reflexion)：
1. 分析背景 (context) 與錯誤/批評 (mistake)。
2. 推導核心根因 (root_cause)。
3. 提煉處事紅線或準則 (redline/preference)，當場寫入 mental_models，使下一輪對話立即前置生效。
"""

import json
from typing import Any

from sylva.core import SylvaStore
from sylva.llm import complete, llm_available

_REFLECT_PROMPT = """你是一個頂級 AI 智能體自省與反思模組。
用戶或系統剛剛指出了當前執行過程中的錯誤、批評、禁忌或踩坑教訓：

【執行場景/上下文】
{context}

【錯誤現象/用戶糾正批評】
{mistake}

請進行深度反思與因果歸因分析，提煉一條可落地的行為準則或紅線，供智能體未來前置避坑。
只輸出嚴格的 JSON 物件，嚴禁多餘文字：
{{
  "module": "redline" | "preference" | "boundary",
  "topic": "主題關鍵詞(如 actual_budget, git_push, query_style)",
  "principle": "未來必須嚴格遵守的具體原則或行為約束",
  "rationale": "該原則建立的根本原因與歷史教訓（20-50字）"
}}
"""


def _parse_reflect_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1].lstrip("json").strip() if len(parts) >= 2 else cleaned
    try:
        data = json.loads(cleaned)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def reflect_and_learn(
    store: SylvaStore,
    mistake: str,
    context: str = "",
    module_override: str | None = None,
    topic_override: str | None = None,
    auto_apply: bool = True,
) -> dict[str, Any]:
    """執行即時反思並沉澱為心智模型。
    若未配置 LLM，則按默認規約降級為本地純文本紅線。
    """
    clean_mistake = mistake.strip()
    if not clean_mistake:
        return {"success": False, "error": "mistake cannot be empty"}

    module = module_override or "redline"
    topic = topic_override or "rule_correction"
    principle = clean_mistake
    rationale = f"基於用戶糾偏或運行異常即時沉澱：{context[:100]}" if context else "用戶即時糾偏反思"

    if llm_available():
        prompt = _REFLECT_PROMPT.format(
            context=context or "（無特定上下文）",
            mistake=clean_mistake,
        )
        res_raw = complete([{"role": "user", "content": prompt}], temperature=0.1)
        if res_raw:
            parsed = _parse_reflect_json(res_raw)
            if parsed.get("principle"):
                module = module_override or parsed.get("module") or module
                topic = topic_override or parsed.get("topic") or topic
                principle = parsed.get("principle") or principle
                rationale = parsed.get("rationale") or rationale

    model_id = None
    if auto_apply:
        model_id = store.add_mental_model(
            module=module,
            topic=topic,
            principle=principle,
            rationale=rationale,
            is_active=True,
        )

    return {
        "success": True,
        "id": model_id,
        "module": module,
        "topic": topic,
        "principle": principle,
        "rationale": rationale,
    }
