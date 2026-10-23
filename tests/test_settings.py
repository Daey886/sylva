"""功能設置測試：settings 表讀寫、LLM 配置優先級、人格與 /settings API 脫敏。"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from sylva.api import create_app
from sylva.core import SylvaStore
from sylva.llm import SYLVA_PERSONA, _config, llm_available


@pytest.fixture
def store(tmp_path, monkeypatch):
    for k in ("SYLVA_LLM_API_KEY", "SYLVA_LLM_BASE_URL", "SYLVA_LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SYLVA_HOME", str(tmp_path))
    return SylvaStore(tmp_path / "sylva.db")  # 显式 db，与 llm._db_path 一致


def test_settings_get_set(store):
    assert store.get_setting("llm_model", "d") == "d"
    store.set_setting("llm_model", "cbai/deepseek-v4.1-flash")
    assert store.get_setting("llm_model") == "cbai/deepseek-v4.1-flash"
    store.set_setting("llm_model", "updated")  # UPSERT
    assert store.get_setting("llm_model") == "updated"


def test_llm_config_from_settings(store):
    store.set_setting("llm_api_key", "sk-test-12345678")
    store.set_setting("llm_model", "m-test")
    _base, key, model = _config()
    assert key == "sk-test-12345678"
    assert model == "m-test"
    assert llm_available() is True


def test_sylva_persona():
    assert "Sylva" in SYLVA_PERSONA
    assert "木頭" in SYLVA_PERSONA
    assert "年輪" in SYLVA_PERSONA


def test_settings_api_masks_key(tmp_path, monkeypatch):
    for k in ("SYLVA_LLM_API_KEY", "SYLVA_LLM_BASE_URL", "SYLVA_LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SYLVA_HOME", str(tmp_path))
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    client = TestClient(create_app(db_path=tmp_path / "sylva.db"))
    headers = {"Authorization": "Bearer tok123"}

    r = client.get("/settings", headers=headers)
    assert r.status_code == 200
    assert r.json()["has_key"] is False
    assert r.json()["llm_available"] is False

    r = client.post(
        "/settings",
        json={
            "llm_base_url": "http://192.168.10.88:20127/v1",
            "llm_model": "cbai/deepseek-v4.1-flash",
            "api_key": "sk-2010abcd",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["llm_available"] is True

    d = client.get("/settings", headers=headers).json()
    assert d["has_key"] is True
    assert d["api_key_masked"].startswith("sk-2")
    assert "sk-2010abcd" not in d["api_key_masked"]  # 不泄露完整 key
