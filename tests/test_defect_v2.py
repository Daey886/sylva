"""针对 sylva-defect-report-v2 报告中缺陷修复的专项回归测试。"""

import pytest
from unittest.mock import patch
from sylva.api import create_app
from sylva.core import SylvaStore
from sylva.primitives import SylvaKernel
from sylva.reflexion import reflect_and_learn
from fastapi.testclient import TestClient


@pytest.fixture
def store(tmp_path):
    return SylvaStore(tmp_path / "test.db")


@pytest.fixture
def kernel(store):
    return SylvaKernel(store)


def test_fts_short_token_fallback(store):
    """测试 1~2 字符的中文或短词能通过 LIKE 回退机制正确召回。"""
    store.add_ring(ring_type="fact", content="跑步爱好者每天早上跑步", ring_hash="h1")
    store.add_ring(ring_type="fact", content="游泳是一项很好的有氧运动", ring_hash="h2")

    # "跑步" 为 2 个字，trigram 分词器提取不出 3-gram
    results = store.search_fts("跑步", limit=5)
    assert len(results) >= 1
    assert any("跑步" in r["content"] for r in results)

    # 特殊符号安全转义（不会抛 SQLite FTS 语法错误）
    res_special = store.search_fts("跑步 OR NOT * : () ' \"", limit=5)
    assert isinstance(res_special, list)


def test_consolidated_rings_excluded_from_search(store):
    """测试已归档/整合 (consolidated=1) 的年轮不应在 FTS 或语义候选向量中召回。"""
    store.add_ring(ring_type="fact", content="活跃的知识年轮内容", ring_hash="h1")
    store.add_ring(ring_type="fact", content="已被归档整合的历史年轮内容", ring_hash="h2")

    rings_all = store.list_rings(limit=10)
    r1 = [r for r in rings_all if r["content"] == "活跃的知识年轮内容"][0]["id"]
    r2 = [r for r in rings_all if r["content"] == "已被归档整合的历史年轮内容"][0]["id"]

    # 将 r2 标记为已整合归档
    store.mark_consolidated([r2])

    # 1. 验证 FTS 检索过滤
    results = store.search_fts("活跃的知识", limit=5)
    assert any(r["id"] == r1 for r in results)

    results_archived = store.search_fts("历史年轮", limit=5)
    assert not any(r["id"] == r2 for r in results_archived)

    # 2. 验证向量检索候选列表过滤
    fake_vec = b"\x00" * 1536
    store.set_embedding(r1, fake_vec)
    store.set_embedding(r2, fake_vec)

    rings_with_emb = store.get_rings_with_embedding()
    assert any(r["id"] == r1 for r in rings_with_emb)
    assert not any(r["id"] == r2 for r in rings_with_emb)


def test_mental_hit_count_float_accumulation(store):
    """测试心智模型命中计数使用浮点累加与衰减权重支持。"""
    mid = store.add_mental_model(
        module="redline",
        topic="test_topic",
        principle="测试红线准则",
        rationale="测试原因",
        is_active=True,
    )

    models_init = store.list_mental_models()
    init_hit = [m for m in models_init if m["id"] == mid][0]["hit_count"]
    assert init_hit == 0.0

    # 模拟一次命中
    store.record_mental_hit(mid, weight=1.0)
    models_1 = store.list_mental_models()
    hit_1 = [m for m in models_1 if m["id"] == mid][0]["hit_count"]
    assert hit_1 == 1.0

    # 验证多次命中保持浮点精度与累加正确
    store.record_mental_hit(mid, weight=0.5)
    models_2 = store.list_mental_models()
    hit_2 = [m for m in models_2 if m["id"] == mid][0]["hit_count"]
    assert hit_2 == 1.5


def test_checkpoint_session_isolation(kernel, store):
    """测试断点恢复（Checkpoint）严格隔离会话，不跨会话串透。"""
    store.set_checkpoint("session_A", "这是会话 A 的最后执行断点")

    # 1. 指定 session_B 查询，查不到断点，不得回退串入 session_A 的断点
    res_b = kernel.inject("查询测试", session_id="session_B")
    assert "[Checkpoint]" not in res_b["context"]
    assert "会话 A" not in res_b["context"]
    assert res_b["has_checkpoint"] is False

    # 2. 指定 session_A 查询，正确注入 session_A 断点
    res_a = kernel.inject("查询测试", session_id="session_A")
    assert "[Checkpoint]" in res_a["context"]
    assert "会话 A 的最后执行断点" in res_a["context"]
    assert res_a["has_checkpoint"] is True

    # 3. 未传 session_id 时，作为通用恢复机制允许取全局最新断点
    res_none = kernel.inject("查询测试", session_id=None)
    assert "[Checkpoint]" in res_none["context"]
    assert "[Last Session: session_A]" in res_none["context"]
    assert res_none["has_checkpoint"] is True


def test_reflect_fallback_safe_pending(store):
    """测试在未配置 LLM 时，reflect_and_learn 降级为待审队列（is_active=False），不直接常驻拦截。"""
    with patch("sylva.reflexion.llm_available", return_value=False):
        res = reflect_and_learn(
            store=store,
            mistake="用户批评了某种不规范行为",
            context="上下文详情",
        )
        assert res["success"] is True

        # 检查是否未直接激活到常驻前置拦截规则
        active_models = store.list_mental_models(only_active=True)
        assert not any("用户批评了某种不规范行为" in m["principle"] for m in active_models)

        # 检查是否以非激活状态完整落盘留档
        all_models = store.list_mental_models(only_active=False)
        pending = [m for m in all_models if "用户批评了某种不规范行为" in m["principle"]]
        assert len(pending) == 1
        assert pending[0]["is_active"] == 0


def test_dashboard_no_hardcoded_probe_meta(tmp_path):
    """测试 Dashboard 探针状态卡片移除假数据硬编码，展示真实指标。"""
    app = create_app(tmp_path / "test.db")
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    # 不应出现报告指出的假数据硬编码
    assert "RAM: 31.4MB · EVAL: 2.8ms" not in html
    assert "probe-meta" in html
    assert "RAM:" in html
    assert "EVAL:" in html
