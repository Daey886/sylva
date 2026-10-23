"""REST API 测试：覆盖 /health /inject /ingest /ring /core /checkpoint。"""

import pytest
from fastapi.testclient import TestClient

from sylva.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """隔离 SYLVA_HOME，避免 llm_available() 读到生产库 LLM 配置。"""
    monkeypatch.delenv("SYLVA_LLM_API_KEY", raising=False)
    monkeypatch.setenv("SYLVA_HOME", str(tmp_path))
    return TestClient(create_app(tmp_path / "api_test.db"))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "sylva"


def test_ingest_then_inject_roundtrip(client):
    r = client.post("/ingest", json={"content": "核心约束：数据库单文件 SQLite", "ring_type": "rule"})
    assert r.status_code == 200
    assert r.json()["written"] is True
    # 无 LLM 时关系抽取优雅降级为 0
    assert r.json()["relations_extracted"] == 0

    r = client.post("/inject", json={"query": "SQLite", "recall_limit": 5})
    assert r.status_code == 200
    assert "SQLite" in r.json()["context"]


def test_ingest_rejects_bad_type(client):
    r = client.post("/ingest", json={"content": "x", "ring_type": "bogus"})
    assert r.status_code == 422


def test_ingest_requires_content(client):
    r = client.post("/ingest", json={"content": ""})
    assert r.status_code == 422


def test_core_endpoints(client):
    r = client.post("/core", json={"key": "developer", "content": "木头"})
    assert r.status_code == 200

    r = client.get("/core")
    assert r.status_code == 200
    assert r.json()["cores"]["developer"] == "木头"


def test_checkpoint_endpoints(client):
    r = client.post("/checkpoint", json={"session_id": "s1", "context": "断点内容"})
    assert r.status_code == 200

    r = client.get("/checkpoint/s1")
    assert r.status_code == 200
    assert r.json()["context"] == "断点内容"

    r = client.get("/checkpoint/不存在")
    assert r.status_code == 404


def test_ring_runs(client):
    client.post("/ingest", json={"content": "临时交互", "ring_type": "interaction", "importance": 0.1})
    r = client.post("/ring", json={"ttl_days": 0})
    assert r.status_code == 200
    assert "decayed_rings" in r.json()
