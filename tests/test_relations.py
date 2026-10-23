"""實體關係圖譜測試：三元組存儲、遞迴 CTE 多跳、召回與抽取降級。"""
from __future__ import annotations

import pytest

from sylva.core import SylvaStore
from sylva.primitives import SylvaKernel
from sylva.relations import extract_relations, ingest_relations, relation_recall


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.delenv("SYLVA_LLM_API_KEY", raising=False)
    monkeypatch.setenv("SYLVA_HOME", str(tmp_path))  # 隔离 settings 表，避免读到生产库 LLM 配置
    return SylvaStore(tmp_path / "test.db")


def test_add_relation_idempotent(store):
    assert store.add_relation("甲", "朋友", "乙") is True
    assert store.add_relation("甲", "朋友", "乙") is False


def test_query_relations_two_hops(store):
    store.add_relation("甲", "朋友", "乙")
    store.add_relation("乙", "借車給", "丙")
    store.add_relation("丙", "住在", "玉環")
    rels = store.query_relations("甲", max_depth=2)
    depths = {r["depth"] for r in rels}
    assert depths == {1, 2}
    assert all(r["depth"] <= 2 for r in rels)
    # 3 跳關係不應出現
    assert not any(r["object"] == "玉環" for r in rels)


def test_relation_recall(store):
    store.add_relation("木頭", "開發", "Sylva")
    store.add_relation("Sylva", "使用", "SQLite")
    out = relation_recall(store, "木頭的項目")
    assert any("木頭" in r and "Sylva" in r for r in out)
    assert relation_recall(store, "今天天氣") == []


def test_inject_includes_relations(store):
    store.add_relation("木頭", "開發", "Sylva")
    kernel = SylvaKernel(store)
    result = kernel.inject(query="木頭最近在做什麼")
    assert result["relation_count"] >= 1
    assert "[Entity Relations]" in result["context"]


def test_extract_relations_no_llm_returns_empty(store):
    assert extract_relations("木頭開發了Sylva") == []
    assert ingest_relations(store, "木頭開發了Sylva") == 0

def test_all_relations(store):
    store.add_relation("甲", "朋友", "乙")
    store.add_relation("乙", "借車給", "丙")
    rels = store.all_relations()
    assert len(rels) == 2
    assert {r["predicate"] for r in rels} == {"朋友", "借車給"}


def test_relations_api(tmp_path, monkeypatch):
    monkeypatch.delenv("SYLVA_LLM_API_KEY", raising=False)
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    from starlette.testclient import TestClient

    from sylva.api import create_app

    db = tmp_path / "sylva.db"
    store = SylvaStore(db)
    store.add_relation("木頭", "開發", "Sylva")
    store.add_relation("Sylva", "使用", "SQLite")
    client = TestClient(create_app(db_path=db))
    d = client.get("/relations", headers={"Authorization": "Bearer tok123"}).json()
    assert len(d["relations"]) == 2
    assert {r["predicate"] for r in d["relations"]} == {"開發", "使用"}


def test_state_predicate_invalidates_old(store):
    """狀態類謂詞（價格）同 (s,p) 不同 o → 舊關係自動失效，保留歷史。"""
    assert store.add_relation("商品", "價格為", "10元") is True
    assert store.add_relation("商品", "價格為", "12元") is True
    rels = store.all_relations()
    assert len(rels) == 1
    assert rels[0]["object"] == "12元"
    all_rels = store.all_relations(include_invalid=True)
    assert len(all_rels) == 2
    invalid = [r for r in all_rels if r["invalid_at"] is not None]
    assert len(invalid) == 1
    assert invalid[0]["object"] == "10元"


def test_multi_value_predicate_not_invalidated(store):
    """多值謂詞（使用）不同 o → 不失效，並列事實保留。"""
    assert store.add_relation("Sylva", "使用", "SQLite") is True
    assert store.add_relation("Sylva", "使用", "Python") is True
    assert len(store.all_relations()) == 2


def test_query_relations_skips_invalid(store):
    """失效關係不參與多跳召回。"""
    store.add_relation("甲", "朋友", "乙")
    store.add_relation("甲", "價格為", "100元")
    store.add_relation("甲", "價格為", "200元")
    rels = store.query_relations("甲", max_depth=2)
    objs = {r["object"] for r in rels}
    assert "100元" not in objs
    assert "200元" in objs


def test_relations_api_include_invalid(tmp_path, monkeypatch):
    """/relations 預設只返回有效關係，include_invalid=true 含失效歷史。"""
    monkeypatch.delenv("SYLVA_LLM_API_KEY", raising=False)
    monkeypatch.setenv("SYLVA_AUTH_TOKEN", "tok123")
    from starlette.testclient import TestClient

    from sylva.api import create_app

    db = tmp_path / "sylva.db"
    store = SylvaStore(db)
    store.add_relation("商品", "價格為", "10元")
    store.add_relation("商品", "價格為", "12元")
    client = TestClient(create_app(db_path=db))
    h = {"Authorization": "Bearer tok123"}
    valid = client.get("/relations", headers=h).json()
    assert len(valid["relations"]) == 1
    assert valid["relations"][0]["object"] == "12元"
    full = client.get("/relations?include_invalid=true", headers=h).json()
    assert len(full["relations"]) == 2
