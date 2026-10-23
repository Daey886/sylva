"""Sylva 唯讀看板端點測試。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from sylva.api import create_app


def _client() -> TestClient:
    app = create_app(Path(tempfile.mktemp(suffix=".db")))
    return TestClient(app)


def test_dashboard_html():
    c = _client()
    r = c.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Sylva" in r.text and "年輪" in r.text


def test_stats_endpoint():
    c = _client()
    r = c.get("/stats")
    assert r.status_code == 200
    data = r.json()
    assert {"rings", "cores", "checkpoints", "db_bytes"} <= set(data)


def test_rings_endpoint_lists_ingested():
    c = _client()
    c.post("/ingest", json={"content": "測試年輪", "ring_type": "fact", "importance": 0.8})
    r = c.get("/rings")
    assert r.status_code == 200
    rings = r.json()["rings"]
    assert len(rings) == 1
    assert rings[0]["content"] == "測試年輪"
    assert rings[0]["ring_type"] == "fact"


def test_checkpoint_endpoint_latest():
    c = _client()
    c.post("/checkpoint", json={"session_id": "s1", "context": "測試斷點"})
    r = c.get("/checkpoint")
    assert r.status_code == 200
    assert r.json()["session_id"] == "s1"
    assert r.json()["context"] == "測試斷點"


def test_existing_endpoints_unaffected():
    c = _client()
    assert c.get("/health").status_code == 200
    assert c.post("/inject", json={"query": "測試"}).status_code == 200
    assert c.post("/ring", json={}).status_code == 200
