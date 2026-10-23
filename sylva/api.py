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

import base64
import hmac
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from sylva.core import SylvaStore
from sylva.dashboard import mount_dashboard
from sylva.primitives import SylvaKernel

RING_TYPES = ("fact", "rule", "decision", "interaction")


class _AuthMiddleware(BaseHTTPMiddleware):
    """所有請求（除 /health 健康檢查）需 HTTP Basic Auth，含本機 hook。

    密碼由環境變量 SYLVA_AUTH_PASSWORD 提供（systemd EnvironmentFile），
    未設置時放行（向後兼容，開發 / 測試環境）。hook 從同一密碼來源讀取，
    用 Basic Auth 攜帶憑證，故同機其他進程也無法免密讀寫記憶。
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        password = os.environ.get("SYLVA_AUTH_PASSWORD", "")
        if not password:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        ok = False
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                user, sep, pw = decoded.partition(":")
                ok = bool(sep) and hmac.compare_digest(user, "sylva") and hmac.compare_digest(pw, password)
            except (ValueError, UnicodeDecodeError):
                ok = False

        if not ok:
            return JSONResponse(
                status_code=401,
                content={"detail": "需要認證"},
                headers={"WWW-Authenticate": 'Basic realm="Sylva"'},
            )
        return await call_next(request)


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
