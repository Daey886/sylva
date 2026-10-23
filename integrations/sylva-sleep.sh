#!/usr/bin/env python3
"""Sylva 夜間記憶鞏固觸發器（systemd.timer 凌晨喚醒）。

呼叫 /sleep 端點執行睡眠昇華：把低頻年輪碎片聚類昇華為語義記憶，
原碎片標記 consolidated 歸檔。由 sylva-sleep.timer 每日凌晨觸發，
帶密鑰認證（與 API 相同的密鑰來源）。

stdout : 昇華結果摘要（寫入 systemd journal）
exit   : 0 成功；非零失敗（systemd 標記 failed）

配置（環境變量，均有默認值）：
  SYLVA_URL     服務地址，默認 http://127.0.0.1:8420
  SYLVA_TIMEOUT 單次 HTTP 超時秒數，默認 120
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ.get("SYLVA_URL", "http://127.0.0.1:8420")
TIMEOUT = float(os.environ.get("SYLVA_TIMEOUT", "120"))


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


def main() -> int:
    headers = {"Content-Type": "application/json"}
    token = _auth_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{URL}/sleep", data=b"", headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.load(resp)
    except urllib.error.URLError as exc:
        sys.stderr.write(f"[sylva-sleep] FAILED url={URL}/sleep ({exc})\n")
        return 1
    sys.stdout.write(f"[sylva-sleep] OK url={URL}/sleep result={body}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
