"""統一訪問認證測試：除 /health 外所有端點需 Basic Auth，密碼由環境變量控制。"""
from __future__ import annotations

import base64

from starlette.testclient import TestClient

from sylva.api import create_app


def _auth(user: str, pw: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def test_requires_auth_when_password_set(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_PASSWORD", "secret123")
    client = TestClient(create_app())
    r = client.get("/stats")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_health_exempt_from_auth(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_PASSWORD", "secret123")
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200


def test_accepts_valid_credentials(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_PASSWORD", "secret123")
    client = TestClient(create_app())
    r = client.get("/stats", headers={"Authorization": _auth("sylva", "secret123")})
    assert r.status_code == 200
    assert "rings" in r.json()


def test_rejects_wrong_password(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_PASSWORD", "secret123")
    client = TestClient(create_app())
    r = client.get("/stats", headers={"Authorization": _auth("sylva", "wrong")})
    assert r.status_code == 401


def test_rejects_wrong_user(monkeypatch):
    monkeypatch.setenv("SYLVA_AUTH_PASSWORD", "secret123")
    client = TestClient(create_app())
    r = client.get("/stats", headers={"Authorization": _auth("admin", "secret123")})
    assert r.status_code == 401


def test_no_password_allows_access(monkeypatch):
    monkeypatch.delenv("SYLVA_AUTH_PASSWORD", raising=False)
    client = TestClient(create_app())
    r = client.get("/stats")
    assert r.status_code == 200
