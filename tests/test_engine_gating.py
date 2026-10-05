"""公式引擎：注册表完整性 + 门控顺序（条款门控先于参数校验先于计算体）。"""

import pytest

from structural_strengthening_checker.calc import EXPECTED_MODULES
from structural_strengthening_checker.core.clauses import ClauseStore
from structural_strengthening_checker.core.engine import CALC_REGISTRY, run_calc
from structural_strengthening_checker.core.errors import (
    ClauseNotVerifiedError,
    ValidationError,
)


def valid_params(module):
    """按模块 schema 生成最小合法参数（range 下限取 1.0，非互斥下限取 0）。"""
    params = {}
    for sym, spec in module.param_schema.items():
        rng = spec.get("range") or {}
        if rng and rng.get("min") == 0 and not rng.get("exclusive"):
            params[sym] = 0
        else:
            params[sym] = 1.0
    return params


def test_registry_has_exactly_four_modules():
    assert set(CALC_REGISTRY) == set(EXPECTED_MODULES)
    assert len(CALC_REGISTRY) == 4


def _pending_store(module_id, make_knowledge):
    """构造"所需条款全部待核对"的临时条款库（门控覆盖：逐模块）。"""
    from structural_strengthening_checker.core.clauses import ClauseStore

    module = CALC_REGISTRY[module_id]
    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "0.0.0",
            "title": "t",
            "gist": "g",
            "status": "待核对",
            "source": {"channel": None, "checked_date": None},
        }
        for cid in module.required_clauses
    ]
    return ClauseStore(make_knowledge(clauses=clauses))


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_gate_blocks_before_compute(module_id, make_knowledge):
    """M1 起仓库条款已核对（门控放行到 M2 stub），门控覆盖改用待核对临时库逐模块断言。"""
    store = _pending_store(module_id, make_knowledge)
    with pytest.raises(ClauseNotVerifiedError):
        run_calc(module_id, valid_params(CALC_REGISTRY[module_id]), store)


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_gate_precedes_param_validation(module_id, make_knowledge):
    """纪律顺序：条款门控优先于参数校验——即使参数也坏，先报条款未核对。"""
    store = _pending_store(module_id, make_knowledge)
    with pytest.raises(ClauseNotVerifiedError):
        run_calc(module_id, {}, store)  # 缺全部参数


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_repo_verified_clauses_open_gate(module_id, repo_data_dir):
    """M1 数据先行：仓库条款库首批已核对 → 门控放行，到达 M2 stub（NotImplementedError）。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    with pytest.raises(NotImplementedError):
        run_calc(module_id, valid_params(CALC_REGISTRY[module_id]), store)


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_after_verified_reaches_stub(module_id, make_knowledge):
    """条款全部已核对时放行到计算体（stub 抛 NotImplementedError=M2 实装点）。"""
    module = CALC_REGISTRY[module_id]
    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "1.0.1",
            "title": "t",
            "gist": "g",
            "status": "已核对",
            "source": {"channel": "t", "checked_date": "2026-10-05"},
        }
        for cid in module.required_clauses
    ]
    store = ClauseStore(make_knowledge(clauses=clauses))
    with pytest.raises(NotImplementedError):
        run_calc(module_id, valid_params(module), store)


def test_param_validation_missing_and_out_of_range(make_knowledge):
    module = CALC_REGISTRY["cfrp_beam_flexure"]
    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "1.0.1",
            "title": "t",
            "gist": "g",
            "status": "已核对",
            "source": {"checked_date": "2026-10-05"},
        }
        for cid in module.required_clauses
    ]
    store = ClauseStore(make_knowledge(clauses=clauses))
    with pytest.raises(ValidationError) as ei:
        run_calc("cfrp_beam_flexure", {}, store)
    assert "缺少参数" in str(ei.value)

    bad = valid_params(module)
    bad["b"] = -1
    with pytest.raises(ValidationError) as ei:
        run_calc("cfrp_beam_flexure", bad, store)
    assert "b=-1" in str(ei.value)

    bad2 = valid_params(module)
    bad2["M0"] = -5  # 非互斥下限 0，-5 越界
    with pytest.raises(ValidationError):
        run_calc("cfrp_beam_flexure", bad2, store)
