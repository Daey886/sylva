"""統一訪問認證測試：除 /health 外所有端點需密鑰（Bearer Token）。"""
from __future__ import annotations

from starlette.testclient import TestClient

from sylva.api import create_app


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_requires_token_when_set(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/stats")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_health_exempt_from_auth(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200


def test_root_page_exempt_from_auth(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_accepts_bearer_token(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/stats", headers=_bearer("tok123"))
    assert r.status_code == 200
    assert "rings" in r.json()


def test_accepts_query_key(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/stats?key=tok123")
    assert r.status_code == 200


def test_accepts_x_api_key(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/stats", headers={"X-API-Key": "tok123"})
    assert r.status_code == 200


def test_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app())
    r = client.get("/stats", headers=_bearer("wrong"))
    assert r.status_code == 401


def test_no_token_allows_access(monkeypatch):
    monkeypatch.delenv("SYLVA_AUTH_TOKEN", raising=False)
    client = TestClient(create_app())
    r = client.get("/stats")
    assert r.status_code == 200
