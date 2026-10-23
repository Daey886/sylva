# Sylva (西爾瓦) 🌲

> **Ultra-lean agent memory engine with SQLite WAL and tree-ring consolidation.**  
> 專為大模型與智慧體生態打造的超輕量自研記憶引擎。年輪沉澱，木木相生。

---

## 核心設計理念

1. **極致精簡 (Ultra-Lean)**：核心邏輯控制在 800 行以內，杜絕冗餘抽象與過度設計。
2. **年輪哲學 (Tree-Ring Philosophy)**：
   - 記憶如樹木年輪般緻密沉澱，拒絕浮腫與上下文雜訊污染。
   - 三大極簡原語：`inject`（請求前注入）、`ingest`（原子寫入）、`ring`（年輪整理）。
3. **單庫 WAL 模式**：
   - 基於單一 SQLite 物理檔案，開啟 WAL 模式併發治理。
   - 內建 FTS5 `trigram` 全文索引，支援中英文子串精準召回。

---

## 三大原語

| 原語 | 動作 | 說明 |
|------|------|------|
| `inject` | 請求前 | 組裝 Core Memory（樹心）+ Checkpoint（斷點）+ Tree Rings（召回年輪），硬性字元截斷保護 |
| `ingest` | 請求後 | 關鍵事實無阻塞原子落盤，SHA256 冪等防重 |
| `ring` | 閒時 | 去重、合併與遺忘衰減，保持年輪緻密 |

---

## 快速開始

```bash
pip install -e .
```

### CLI

```bash
# 寫入一條記憶
sylva ingest "用戶偏好使用 SQLite WAL 模式" --type fact

# 請求前召回上下文
sylva inject "資料庫方案"

# 核心記憶（樹心）管理
sylva core set developer "木頭 Daey886"
sylva core list

# 斷點上下文
sylva checkpoint set sess_main "上次任務停在第四階段"
sylva checkpoint get

# 年輪整理（清理超期低權重交互）
sylva ring --ttl-days 30
```

資料庫預設路徑 `~/.sylva/sylva.db`（可透過環境變數 `SYLVA_HOME` 或 `--db` 覆寫）。

### HTTP API

```bash
uvicorn sylva.api:app --host 127.0.0.1 --port 8420
```

| 方法 | 路徑 | 用途 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `POST` | `/inject` | 請求前組裝上下文 |
| `POST` | `/ingest` | 原子寫入年輪 |
| `POST` | `/ring` | 年輪整理 |
| `POST` / `GET` | `/core` | 核心記憶寫入 / 列出 |
| `POST` / `GET` | `/checkpoint/{session_id}` | 斷點記錄 / 讀取 |

### Hermes Hook 接入

```bash
cp integrations/hermes-hook.sh ~/.hermes/agent-hooks/sylva-hook.sh
chmod +x ~/.hermes/agent-hooks/sylva-hook.sh
~/.hermes/agent-hooks/sylva-hook.sh --selftest   # 自檢
```

於 `~/.hermes/config.yaml` 註冊 `hooks.pre_llm_call` 後，Sylva 會在每輪 LLM 請求前，
將當輪訊息送入 `/inject` 召回相關記憶並注入上下文（Core + Checkpoint + Rings）。

環境變數（均有預設值）：`SYLVA_URL`（服務位址）、`SYLVA_TIMEOUT`（逾時秒數）、`SYLVA_MIN_MSG`（最短注入字元數）。

---

## 專案結構

```
sylva/
├── core.py          # 儲存微內核：SQLite WAL + FTS5 trigram 召回
├── primitives.py    # 三大原語：inject / ingest / ring
├── cli.py           # Typer 命令列入口
└── api.py           # FastAPI HTTP 服務
integrations/
└── hermes-hook.sh   # Hermes Agent pre_llm_call hook
tests/
├── test_core.py
├── test_primitives.py
├── test_cli.py
└── test_api.py
```

## 架構決策與規範

詳見 [ADR-001: Sylva 架構設計與微內核規範](docs/adr/ADR-001-microkernel-architecture.md)。

## 路線圖

- [x] 階段一：骨架 + CI 門禁
- [x] 階段二：`core.py` 儲存微內核（SQLite WAL + FTS5）
- [x] 階段三：`primitives.py` 三大原語
- [x] 階段四：HTTP API / CLI / Hermes Hook 落地接入
- [ ] 階段五：FastEmbed 本地語義向量召回（雙軌第二軌）

## License

MIT License © 2026 Daey886
