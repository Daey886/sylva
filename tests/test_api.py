"""REST API 测试：覆盖 /health /inject /ingest /ring /core /checkpoint。"""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from sylva.api import create_app


def _client(tmpdir: str) -> TestClient:
    db = Path(tmpdir) / "api_test.db"
    return TestClient(create_app(db))


def test_health():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["service"] == "sylva"


def test_ingest_then_inject_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)

        r = c.post("/ingest", json={"content": "核心约束：数据库单文件 SQLite", "ring_type": "rule"})
        assert r.status_code == 200
        assert r.json()["written"] is True

        r = c.post("/inject", json={"query": "SQLite", "recall_limit": 5})
        assert r.status_code == 200
        assert "SQLite" in r.json()["context"]


def test_ingest_rejects_bad_type():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)
        r = c.post("/ingest", json={"content": "x", "ring_type": "bogus"})
        assert r.status_code == 422


def test_ingest_requires_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)
        r = c.post("/ingest", json={"content": ""})
        assert r.status_code == 422


def test_core_endpoints():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)

        r = c.post("/core", json={"key": "developer", "content": "木头"})
        assert r.status_code == 200

        r = c.get("/core")
        assert r.status_code == 200
        assert r.json()["cores"]["developer"] == "木头"


def test_checkpoint_endpoints():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)

        r = c.post("/checkpoint", json={"session_id": "s1", "context": "断点内容"})
        assert r.status_code == 200

        r = c.get("/checkpoint/s1")
        assert r.status_code == 200
        assert r.json()["context"] == "断点内容"

        r = c.get("/checkpoint/不存在")
        assert r.status_code == 404


def test_ring_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = _client(tmpdir)
        c.post("/ingest", json={"content": "临时交互", "ring_type": "interaction", "importance": 0.1})
        r = c.post("/ring", json={"ttl_days": 0})
        assert r.status_code == 200
        assert "decayed_rings" in r.json()
