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


DEMO_PARAMS = {
    "cfrp_beam_flexure": {
        "b": 250.0, "h": 500.0, "fc": 14.3, "As": 1520.0, "fy": 360.0,
        "Afe": 101.0, "Ecf": 240000.0, "M0": 0.0, "M": 180.0,
        "ff": 2300.0, "ef": 0.01, "as": 35.0, "xi_b": 0.518, "Es": 200000.0,
    },
    "steel_plate_flexure": {
        "b": 250.0, "h": 500.0, "fc": 14.3, "As": 1520.0, "fy": 360.0,
        "Ap": 600.0, "fp": 215.0, "M0": 0.0, "M": 190.0,
        "as": 35.0, "xi_b": 0.518, "Es": 200000.0, "Esp": 206000.0,
    },
    "section_enlarge_flexure": {
        "b": 250.0, "h": 500.0, "bf": 250.0, "hf": 100.0, "fc": 14.3, "fc2": 16.7,
        "As": 1520.0, "fy": 360.0, "As2": 628.0, "fy2": 360.0,
        "as": 35.0, "as2": 45.0, "M0": 0.0, "M": 220.0, "Es": 200000.0,
    },
    "post_rebar_anchor": {
        "fc": 30.0, "fy": 360.0, "d": 16.0, "ld": 600.0,
        "alpha_spt": 0.9, "fbd": 3.0, "psi_br": 1.5, "psi_w": 1.1, "psi_T": 1.0, "psi_ae": 1.0,
    },
}


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_repo_verified_clauses_open_gate(module_id, repo_data_dir):
    """M2 起仓库条款已核对且计算体实装：门控放行 → 返回 CalcResult（三态之一）。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    result = run_calc(module_id, DEMO_PARAMS[module_id], store)
    assert result["module"] == module_id
    assert result["verdict"] in ("满足", "不满足", "需调整")
    assert result["steps"] and result["clauses_used"]


@pytest.mark.parametrize("module_id", sorted(EXPECTED_MODULES))
def test_after_verified_reaches_compute(module_id, make_knowledge):
    """条款全部已核对时放行到计算体（M2 实装后返回 CalcResult 形状 dict）。"""
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
    result = run_calc(module_id, DEMO_PARAMS[module_id], store)
    # CalcResult 形状（plan/04 §1.3 + M2 metrics 增补）
    for key in ("module", "inputs", "steps", "capacity", "ratio", "verdict", "clauses_used", "warnings", "metrics"):
        assert key in result, key
    for st in result["steps"]:
        assert st["formula_ref"] and st["clause_ids"]


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
