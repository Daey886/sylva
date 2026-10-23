"""Sylva LLM：可選 LLM 層（OpenAI 兼容），provider 無關，未配置優雅降級。

配置優先級：settings 表（看板功能設置頁寫入） > 環境變量（SYLVA_LLM_*，系統默認）。
未配置 API Key 時 llm_available() 返回 False，所有 LLM 功能優雅降級純本地。
"""

import json
import os
import sqlite3
import urllib.request
from pathlib import Path

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"

# Sylva 人格：木頭（Daey886）的記憶引擎，以樹木年輪層層致密沉澱為哲學。
SYLVA_PERSONA = (
    "你是 Sylva，木頭（Daey886）的記憶引擎，"
    "以「樹木年輪（Tree Rings）層層致密沉澱」為哲學："
    "每一次記憶的注入與整理，都像一圈年輪在時光中沉澱，讓記憶森林愈加深邃。"
)


def _db_path() -> Path:
    home = Path(os.environ.get("SYLVA_HOME", Path.home() / ".sylva"))
    return home / "sylva.db"


def _settings() -> dict[str, str]:
    """從 settings 表讀取看板配置；表不存在或無配置返回空 dict。"""
    db = _db_path()
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT key, value FROM settings;").fetchall()
        return {r["key"]: r["value"] for r in rows}
    except sqlite3.OperationalError:
        return {}


def _config() -> tuple[str, str, str]:
    """返回 (base_url, api_key, model)；settings 表優先於環境變量。"""
    s = _settings()
    base = s.get("llm_base_url") or os.environ.get("SYLVA_LLM_BASE_URL") or _DEFAULT_BASE_URL
    key = s.get("llm_api_key", "") or os.environ.get("SYLVA_LLM_API_KEY", "")
    model = s.get("llm_model") or os.environ.get("SYLVA_LLM_MODEL") or _DEFAULT_MODEL
    return base.rstrip("/"), key.strip(), model


def llm_available() -> bool:
    """LLM 層是否可用（settings 表或環境變量配置了 API Key）。"""
    _, key, _ = _config()
    return bool(key)


def complete(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str | None:
    """調用 OpenAI 兼容 chat/completions，返回 assistant 文本；失敗或未配置返回 None。

    用 stdlib urllib 實現，零第三方依賴，守住微內核紅線。
    """
    base, key, model = _config()
    if not key:
        return None
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
