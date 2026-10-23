"""Sylva API: 轻量 FastAPI 服务，将三大原语暴露为 REST 接口。

启动:
    uvicorn sylva.api:app --host 127.0.0.1 --port 8420

接口:
    GET  /health     健康检查
    POST /inject     请求前组装上下文
    POST /ingest     原子写入年轮
    POST /ring       整理年轮
    POST /core       写入核心记忆
    GET  /core       列出核心记忆
    POST /checkpoint 记录断点
    GET  /checkpoint/{session_id} 读取断点
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from sylva.consolidate import sleep_consolidate
from sylva.core import SylvaStore
from sylva.dashboard import mount_dashboard
from sylva.llm import llm_available
from sylva.primitives import SylvaKernel

RING_TYPES = ("fact", "rule", "decision", "interaction")


def _extract_token(request: Request) -> str:
    """從請求提取密鑰：Bearer header / X-API-Key header / ?key= query。"""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    key = request.headers.get("x-api-key", "")
    if key:
        return key.strip()
    return request.query_params.get("key", "").strip()


class _AuthMiddleware(BaseHTTPMiddleware):
    """所有請求（除 /health 健康檢查）需密鑰（Bearer Token）認證，含本機 hook。

    密鑰由環境變量 SYLVA_AUTH_TOKEN 提供（systemd EnvironmentFile），
    未設置時放行（向後兼容，開發 / 測試環境）。接受三種傳遞方式：
    Authorization: Bearer <token>、X-API-Key: <token>、URL ?key=<token>。
    hook 從同一密鑰來源讀取並用 Bearer 攜帶，同機其他進程無法免密讀寫記憶。
    """

    async def dispatch(self, request: Request, call_next):
        # /health 健康檢查與 / 看板 HTML 頁面免密（HTML 本身無數據，數據在唯讀端點）
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        token = os.environ.get("SYLVA_AUTH_TOKEN", "")
        if not token:
            return await call_next(request)

        provided = _extract_token(request)
        if provided and hmac.compare_digest(provided, token):
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "需要密鑰"},
            headers={"WWW-Authenticate": 'Bearer realm="Sylva"'},
        )


class InjectRequest(BaseModel):
    query: str = ""
    session_id: str | None = None
    max_chars: int = Field(default=4000, ge=100, le=200_000)
    recall_limit: int = Field(default=5, ge=1, le=50)


class IngestRequest(BaseModel):
    content: str = Field(min_length=1)
    ring_type: str = "fact"
    importance: float = Field(default=1.0, ge=0.0, le=1.0)


class RingRequest(BaseModel):
    ttl_days: float = Field(default=30.0, ge=0.0)


class CoreRequest(BaseModel):
    key: str = Field(min_length=1)
    content: str


class CheckpointRequest(BaseModel):
    session_id: str = Field(min_length=1)
    context: str
    metadata: str = "{}"


class SettingsRequest(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    api_key: str | None = None


def _mask_key(key: str) -> str:
    """API Key 脫敏：只暴露前 4 後 4 位。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * 12}{key[-4:]}"


def create_app(db_path: Path | None = None) -> FastAPI:
    """构造一个绑定到指定数据库的 Sylva API 实例。"""
    kernel = SylvaKernel(SylvaStore(db_path) if db_path else None)

    app = FastAPI(
        title="Sylva",
        version="0.1.0",
        description="Ultra-lean agent memory engine — Inject / Ingest / Ring.",
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "sylva", "db": str(kernel.store.db_path)}

    @app.post("/inject")
    def inject(req: InjectRequest) -> dict:
        return kernel.inject(
            query=req.query,
            session_id=req.session_id,
            max_chars=req.max_chars,
            recall_limit=req.recall_limit,
        )

    @app.post("/ingest")
    def ingest(req: IngestRequest) -> dict:
        if req.ring_type not in RING_TYPES:
            raise HTTPException(status_code=422, detail=f"ring_type 必须是 {RING_TYPES} 之一")
        written = kernel.ingest(
            content=req.content, ring_type=req.ring_type, importance=req.importance
        )
        return {"written": written, "ring_type": req.ring_type}

    @app.post("/ring")
    def ring(req: RingRequest) -> dict:
        return kernel.ring_consolidate(ttl_days=req.ttl_days)

    @app.post("/sleep")
    def sleep_consolidation() -> dict:
        """夜間睡眠昇華：掃描低頻碎片，LLM 歸納為語義記憶並歸檔。"""
        return sleep_consolidate(kernel.store)

    @app.get("/settings")
    def get_settings() -> dict:
        """看板功能設置：返回 LLM 配置（API Key 脫敏）。"""
        store = kernel.store
        key = store.get_setting("llm_api_key", "")
        return {
            "llm_base_url": store.get_setting("llm_base_url", ""),
            "llm_model": store.get_setting("llm_model", ""),
            "api_key_masked": _mask_key(key),
            "has_key": bool(key),
            "llm_available": llm_available(),
        }

    @app.post("/settings")
    def update_settings(req: SettingsRequest) -> dict:
        """看板功能設置：更新 LLM 配置（api_key 留空則保持原值）。"""
        store = kernel.store
        if req.llm_base_url is not None:
            store.set_setting("llm_base_url", req.llm_base_url.strip())
        if req.llm_model is not None:
            store.set_setting("llm_model", req.llm_model.strip())
        if req.api_key:
            store.set_setting("llm_api_key", req.api_key.strip())
        return {"ok": True, "llm_available": llm_available()}

    @app.get("/relations")
    def list_relations() -> dict:
        """看板圖譜：返回全部三元組（節點+邊）。"""
        return {"relations": kernel.store.all_relations()}

    @app.post("/core")
    def set_core(req: CoreRequest) -> dict:
        kernel.store.set_core(req.key, req.content)
        return {"key": req.key, "updated": True}

    @app.get("/core")
    def list_core() -> dict:
        return {"cores": kernel.store.list_cores()}

    @app.post("/checkpoint")
    def set_checkpoint(req: CheckpointRequest) -> dict:
        kernel.store.set_checkpoint(req.session_id, req.context, req.metadata)
        return {"session_id": req.session_id, "updated": True}

    @app.get("/checkpoint/{session_id}")
    def get_checkpoint(session_id: str) -> dict:
        ctx = kernel.store.get_checkpoint(session_id)
        if ctx is None:
            raise HTTPException(status_code=404, detail=f"断点 [{session_id}] 不存在")
        return {"session_id": session_id, "context": ctx}

    app.add_middleware(_AuthMiddleware)

    mount_dashboard(app, kernel)

    return app


# 默认实例，供 `uvicorn sylva.api:app` 直接启动。
app = create_app()
