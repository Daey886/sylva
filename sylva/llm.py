"""Sylva LLM：可選 LLM 層（OpenAI 兼容），provider 無關，未配置優雅降級。

環境變量：
- SYLVA_LLM_BASE_URL  預設 https://api.deepseek.com/v1（大平台，可換任意 OpenAI 兼容地址）
- SYLVA_LLM_API_KEY   API 密鑰
- SYLVA_LLM_MODEL     預設 deepseek-chat
- SYLVA_LLM_TIMEOUT   預設 15 秒

未配置 API Key 時 llm_available() 返回 False，所有 LLM 功能（實體抽取、睡眠昇華）
優雅降級為純本地行為，不阻塞核心記憶閉環。
"""

import json
import os
import urllib.request

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"


def llm_available() -> bool:
    """LLM 層是否可用（僅依賴是否配置 API Key）。"""
    return bool(os.environ.get("SYLVA_LLM_API_KEY", "").strip())


def _config() -> tuple[str, str, str]:
    base = os.environ.get("SYLVA_LLM_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    key = os.environ.get("SYLVA_LLM_API_KEY", "").strip()
    model = os.environ.get("SYLVA_LLM_MODEL", _DEFAULT_MODEL)
    return base, key, model


def complete(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str | None:
    """調用 OpenAI 兼容 chat/completions，返回 assistant 文本；失敗或未配置返回 None。

    用 stdlib urllib 實現，零第三方依賴，守住微內核紅線。
    """
    if not llm_available():
        return None
    base, key, model = _config()
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    timeout = float(os.environ.get("SYLVA_LLM_TIMEOUT", "15"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
