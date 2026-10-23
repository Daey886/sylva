#!/usr/bin/env python3
"""Sylva Hermes Agent `post_llm_call` hook（寫線，單進程純 Python）。

把剛結束這一輪的 user_message 寫入 Sylva 的 interaction 年輪（低權重、
短衰減泳道），供近期召回參考；ring 維護線的遺忘衰減會自然淘汰過期交互。
持久事實 / 規則 / 決策由用戶顯式寫入（fact/rule/decision），寫線不自動提煉。

新增：若 assistant 回覆有實質結論（≥30 字），同步把「Q + A 摘要」寫入，
讓「上次問過什麼、答了什麼」都能被召回（同樣 30 天遺忘，非永久記憶）。

stdin  : Hermes post_llm_call payload (JSON)
stdout : {} （寫線只做副作用寫入，不改寫 context）

配置（環境變量，均有默認值）：
  SYLVA_URL             服務地址，默認 http://127.0.0.1:8420
  SYLVA_TIMEOUT         單次 HTTP 超時秒數，默認 2.0
  SYLVA_MIN_MSG         用戶消息短於 N 字不寫，默認 8
  SYLVA_ASSISTANT_MIN   回覆短於 N 字不併入 Q&A，默認 30
  SYLVA_ASSISTANT_MAX   Q&A 中回覆摘要上限字符，默認 400

設計原則（繼承 aidumem 寫線教訓）：
  - 短消息不寫（「嗯」「好的」無記憶價值）
  - 寫入失敗靜默降級，絕不影響 LLM（讀線才是關鍵路徑）
  - 只寫 user_message + assistant 回覆摘要，不做 LLM 提煉（Sylva 微內核哲學：確定性算法）
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

URL = os.environ.get("SYLVA_URL", "http://127.0.0.1:8420")
TIMEOUT = float(os.environ.get("SYLVA_TIMEOUT", "2.0"))
MIN_MSG = int(os.environ.get("SYLVA_MIN_MSG", "8"))
ASSISTANT_MIN = int(os.environ.get("SYLVA_ASSISTANT_MIN", "30"))
ASSISTANT_MAX = int(os.environ.get("SYLVA_ASSISTANT_MAX", "400"))
RING_TYPE = "interaction"
IMPORTANCE = 0.3  # 低於 0.5，ring 遺忘衰減（默認 30 天）會自然淘汰

_MD_RE = re.compile(r"[*_`>#|]+")


def _clean(text: str) -> str:
    """去掉 Markdown 標記，保留可讀純文本。"""
    return _MD_RE.sub("", text).strip()


def _summarize(text: str) -> str:
    """確定性摘要：去 Markdown + 截斷到上限。"""
    text = _clean(text)
    if len(text) <= ASSISTANT_MAX:
        return text
    return text[: ASSISTANT_MAX - 3] + "…"



def _auth_token() -> str:
    """從環境變量或 /etc/sylva/auth.env 讀取 Sylva 訪問密鑰。"""
    token = os.environ.get("SYLVA_AUTH_TOKEN", "")
    if token:
        return token
    try:
        with open("/etc/sylva/auth.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SYLVA_AUTH_TOKEN="):
                    return line.split("=", 1)[1]
    except OSError:
        pass
    return ""


_AUTH_TOKEN = _auth_token()


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if _AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {_AUTH_TOKEN}"
    return headers


def _post_ingest(content):
    body = json.dumps(
        {"content": content, "ring_type": RING_TYPE, "importance": IMPORTANCE},
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        f"{URL}/ingest", data=body, headers=_headers()
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return bool(json.load(resp).get("written", False))


def _selftest():
    try:
        written = _post_ingest("sylva ingest selftest")
    except Exception as exc:  # noqa: BLE001 — selftest 診斷路徑要抓一切錯誤
        sys.stderr.write(f"[sylva-ingest] selftest FAILED url={URL}/ingest ({exc})\n")
        return 4
    sys.stderr.write(
        f"[sylva-ingest] selftest OK url={URL}/ingest written={written}\n"
    )
    return 0


def main():
    if "--selftest" in sys.argv[1:]:
        return _selftest()

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:  # noqa: BLE001 — 任何異常都必須靜默降級
        print("{}")
        return 0

    extra = payload.get("extra") or {}
    msg = extra.get("user_message") or payload.get("user_message") or ""
    if not isinstance(msg, str):
        msg = ""
    msg = msg.strip()

    # 短消息不寫
    if len(msg) < MIN_MSG:
        print("{}")
        return 0

    # assistant 回覆有實質結論時，併入 Q&A 對一起寫入
    assistant_resp = extra.get("assistant_response") or ""
    if not isinstance(assistant_resp, str):
        assistant_resp = ""
    assistant_resp = assistant_resp.strip()

    if len(assistant_resp) >= ASSISTANT_MIN:
        content = f"{msg}\n→ {_summarize(assistant_resp)}"
    else:
        content = msg

    try:
        _post_ingest(content)
    except Exception:  # noqa: BLE001 — 寫線失敗靜默，不影響 LLM
        pass

    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
