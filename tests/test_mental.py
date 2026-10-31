"""Tests for Sylva Mental Models primitives and API."""

import pytest
from fastapi.testclient import TestClient

from sylva.api import create_app
from sylva.core import SylvaStore
from sylva.primitives import SylvaKernel


@pytest.fixture
def store(tmp_path):
    db_file = tmp_path / "test_mental.db"
    return SylvaStore(db_path=db_file)


@pytest.fixture
def client(tmp_path):
    db_file = tmp_path / "test_api_mental.db"
    app = create_app(db_file)
    return TestClient(app)


def test_mental_models_store_crud(store: SylvaStore):
    # 1. Add
    m_id = store.add_mental_model(
        module="redline",
        topic="actual_budget",
        principle="严禁直接修改 SQLite，任何变更必须走 MCP 工具",
        rationale="直改数据库会破坏实际预算同步机制",
    )
    assert m_id > 0

    # 2. List
    mentals = store.list_mental_models(module="redline")
    assert len(mentals) == 1
    assert mentals[0]["topic"] == "actual_budget"
    assert mentals[0]["is_active"] == 1

    # 3. Hit count
    store.record_mental_hit(m_id)
    updated_mentals = store.list_mental_models(module="redline")
    assert updated_mentals[0]["hit_count"] == 1

    # 4. Update
    ok = store.update_mental_model(m_id, principle="修改后的原则", is_active=False)
    assert ok is True
    active_mentals = store.list_mental_models(only_active=True)
    assert len(active_mentals) == 0

    # 5. Delete
    deleted = store.delete_mental_model(m_id)
    assert deleted is True
    all_mentals = store.list_mental_models(only_active=False)
    assert len(all_mentals) == 0


def test_mental_models_inject(store: SylvaStore):
    kernel = SylvaKernel(store=store)
    store.set_core("developer", "木头")
    store.add_mental_model(
        module="redline",
        topic="git_push",
        principle="严禁未测试直接 push 到 main 分支",
        rationale="保证主干始终处于全绿健康状态",
    )
    store.add_mental_model(
        module="preference",
        topic="reply_style",
        principle="优先以飞书卡片或结构化表格交付",
        is_active=False,  # 停用不注入
    )

    result = kernel.inject(query="怎么提交代码")
    ctx = result["context"]
    assert "[Mental Models & Redlines]" in ctx
    assert "git_push" in ctx
    assert "reply_style" not in ctx  # 停用项不注入
    assert result["mental_model_count"] == 1


def test_mental_models_api(client: TestClient):
    # 1. POST
    res = client.post(
        "/mental",
        json={
            "module": "goal",
            "topic": "fitness",
            "principle": "身高 170cm，体重 85kg -> 70kg 薄肌目标",
            "rationale": "健康管理",
        },
    )
    assert res.status_code == 200
    m_id = res.json()["id"]

    # 2. GET
    res = client.get("/mental")
    assert res.status_code == 200
    items = res.json()["mental_models"]
    assert len(items) == 1
    assert items[0]["id"] == m_id

    # 3. PATCH
    res = client.patch(f"/mental/{m_id}", json={"is_active": False})
    assert res.status_code == 200

    # 4. DELETE
    res = client.delete(f"/mental/{m_id}")
    assert res.status_code == 200

    # 5. POST /reflect
    res = client.post(
        "/reflect",
        json={
            "mistake": "严禁在未经本地单测通过前合并 PR",
            "context": "CI 挂了直接合导致构建失败",
            "topic": "pr_merge",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["topic"] == "pr_merge"
    assert data["module"] == "redline"
    assert data["id"] is not None
