#!/usr/bin/env python3
"""Sylva Hermes Agent `on_session_end` hook（維護線，單進程純 Python）。

會話結束時觸發 ring 整理：遺忘衰減（淘汰過期低權重交互）+ 語義去重合併。
無 LLM 提煉——Sylva 微內核哲學：維護靠確定性算法，不靠模型。

stdin  : Hermes on_session_end payload (JSON)（本 hook 忽略內容）
stdout : {} （維護線只做副作用，不改寫 context）

配置（環境變量，均有默認值）：
  SYLVA_URL          服務地址，默認 http://127.0.0.1:8420
  SYLVA_RING_TIMEOUT 單次 HTTP 超時秒數，默認 10.0（語義去重需載入模型）
  SYLVA_RING_TTL     遺忘衰減天數，默認 30.0
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("SYLVA_URL", "http://127.0.0.1:8420")
TIMEOUT = float(os.environ.get("SYLVA_RING_TIMEOUT", "10.0"))
TTL_DAYS = float(os.environ.get("SYLVA_RING_TTL", "30.0"))


def _post_ring():
    body = json.dumps({"ttl_days": TTL_DAYS}).encode()
    req = urllib.request.Request(
        f"{URL}/ring", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def _selftest():
    try:
        result = _post_ring()
    except Exception as exc:  # noqa: BLE001 — selftest 診斷路徑要抓一切錯誤
        sys.stderr.write(f"[sylva-ring] selftest FAILED url={URL}/ring ({exc})\n")
        return 4
    sys.stderr.write(f"[sylva-ring] selftest OK url={URL}/ring {result}\n")
    return 0


def main():
    if "--selftest" in sys.argv[1:]:
        return _selftest()

    try:
        _post_ring()
    except Exception:  # noqa: BLE001 — 維護線失敗靜默，不影響會話結束
        pass

    print("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
