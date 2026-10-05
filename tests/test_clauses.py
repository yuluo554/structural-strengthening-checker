"""条款库 ClauseStore：加载/schema 纪律/门控行为。"""

import pytest

from structural_strengthening_checker.core.clauses import ClauseStore
from structural_strengthening_checker.core.errors import ClauseNotVerifiedError


def base_clause(**overrides):
    entry = {
        "clause_id": "X-1",
        "standard": "X 0000-0000",
        "clause_no": "1.0.0",
        "title": "占位条款",
        "gist": "占位要点",
        "status": "待核对",
        "source": {"channel": None, "checked_date": None},
    }
    entry.update(overrides)
    return entry


def test_repo_store_loads(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    assert not store.issues
    # M1 数据先行首批：GB50367×31 + GB55021×16 + GB50728×1 + JGJ145×1（待核对）
    assert len(store) == 49
    summary = store.status_summary()
    assert summary["verified"] == 48
    # 熔断纪律留痕：JGJ 145-2013 §6.3 渠道已试不可达，保持待核对
    assert summary["pending"] == 1
    assert "JGJ145-2013-6.3" in store
    assert store.get("JGJ145-2013-6.3").status == "待核对"


def test_repo_verified_clauses_have_checked_date(repo_data_dir):
    """status=已核对 ⇔ source.checked_date 非空（加载器强制；此处断言仓库数据真实满足）。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    for clause in store.all_clauses():
        if clause.status == "已核对":
            assert clause.source.get("checked_date"), clause.clause_id
            assert clause.source.get("channel"), clause.clause_id
            assert clause.source.get("locator"), clause.clause_id


def test_repo_module_required_clauses_all_verified(repo_data_dir):
    """4 个验算模块的 required_clauses 已替换为真实 clause_id 且全部已核对（M1→M2 交接面）。"""
    from structural_strengthening_checker.core.engine import CALC_REGISTRY

    store = ClauseStore(repo_data_dir / "knowledge")
    for module in CALC_REGISTRY.values():
        assert module.required_clauses, module.module_id
        for cid in module.required_clauses:
            assert cid in store, f"{module.module_id} 所需条款未登记: {cid}"
            assert store.get(cid).status == "已核对", f"{cid} 未核对"
        # 占位 ID 必须已清零
        assert "FLEXURE" not in " ".join(module.required_clauses)
        assert "ANCHOR" not in " ".join(module.required_clauses)


def test_unregistered_clause_rejected(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    with pytest.raises(ClauseNotVerifiedError) as ei:
        store.require_verified(["NOPE-1"])
    assert "未登记" in str(ei.value)


def test_pending_clause_rejected(make_knowledge):
    store = ClauseStore(make_knowledge(clauses=[base_clause()]))
    with pytest.raises(ClauseNotVerifiedError) as ei:
        store.require_verified(["X-1"])
    assert "待核对" in str(ei.value)


def test_verified_requires_checked_date(make_knowledge):
    store = ClauseStore(make_knowledge(clauses=[base_clause(status="已核对")]))
    assert any("checked_date" in i for i in store.issues)
    assert len(store) == 0  # 未通过纪律校验的条目不入库


def test_verified_clause_passes_gate(make_knowledge):
    entry = base_clause(status="已核对", source={"channel": "t", "checked_date": "2026-10-05"})
    store = ClauseStore(make_knowledge(clauses=[entry]))
    store.require_verified(["X-1"])  # 不抛
