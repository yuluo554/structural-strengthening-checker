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
    assert len(store) >= 1
    summary = store.status_summary()
    assert summary["pending"] >= 1
    # 骨架期纪律：无一条款是"已核对"（M1 起按核对流程逐条转正）
    assert summary["verified"] == 0


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
