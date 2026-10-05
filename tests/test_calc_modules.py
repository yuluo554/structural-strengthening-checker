"""M2 公式引擎模块测试：代码表值↔条款库一致性 / 查表函数 / CalcResult 形状 / 三态判定。

纪律锚点：
- calc/common.py 的表值是"代码出处"，条款库 JSON limits 是"数据出处"——两处必须一致（本测试锁死）；
- 三态判定口径见 data/cases/workings/formula_verification_M2.md §六.7。
"""

import json

from structural_strengthening_checker.calc import common
from structural_strengthening_checker.calc.common import (
    alpha_spt_from_table,
    fbd_from_table,
    lookup_alpha_f,
)
from structural_strengthening_checker.core.clauses import ClauseStore
from structural_strengthening_checker.core.errors import ValidationError
from structural_strengthening_checker.core.engine import CALC_REGISTRY, run_calc

from test_engine_gating import DEMO_PARAMS

# ---------------------------------------------------------------------------
# 代码表值 ↔ 条款库 JSON 一致性（单一事实来源的双出口守门）
# ---------------------------------------------------------------------------


def _gb50367_limits(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    return {c.clause_no: c.limits for c in store.all_clauses()
            if c.standard == "GB 50367-2013"}


def test_code_tables_match_clause_json(repo_data_dir):
    limits = _gb50367_limits(repo_data_dir)

    t8 = limits["10.2.8"]["table_10_2_8"]
    assert t8["rho_te_bands"] == list(common.ALPHA_F_RHO_TE_BANDS)
    assert t8["single_row"] == list(common.ALPHA_F_SINGLE_ROW)
    assert t8["double_row"] == list(common.ALPHA_F_DOUBLE_ROW)
    t9 = limits["9.2.9"]["table_9_2_9"]
    assert t9["rho_te_bands"] == list(common.ALPHA_F_RHO_TE_BANDS)
    assert t9["single_row"] == list(common.ALPHA_F_SINGLE_ROW)
    assert t9["double_row"] == list(common.ALPHA_F_DOUBLE_ROW)

    t = limits["15.2.3"]["table_15_2_3"]
    assert t["le20"] == list(common.ALPHA_SPT_ROWS["le20"])
    assert t["d25"] == list(common.ALPHA_SPT_ROWS["d25"])
    assert t["d32"] == list(common.ALPHA_SPT_ROWS["d32"])

    rows = limits["15.2.4"]["table_15_2_4"]
    assert len(rows) == len(common.FBD_TABLE)
    for j_row, c_row in zip(rows, common.FBD_TABLE):
        assert j_row["values"] == c_row["values"]
    assert limits["15.2.4"]["fast_cure_above_C30_factor"] == common.FBD_FAST_CURE_FACTOR

    # 新增表值条款与 CFRP 模块使用一致性（表4.3.4/4.3.5 全量在库，模块按输入取值）
    assert "table_4_3_4_1_carbon" in limits["4.3.4"]
    assert limits["4.3.5"]["table_4_3_5"]["carbon"]["fabric_Ef"]["I"] == 2.3e5


# ---------------------------------------------------------------------------
# 查表函数单元行为
# ---------------------------------------------------------------------------


def test_lookup_alpha_f_bands_and_interpolation():
    # 精确档点（浮点边界用容差断言：档点命中走内插路径 t=1.0）
    v, flag = lookup_alpha_f(0.007, 1)
    assert abs(v - 0.70) < 1e-9 and not flag
    v, _ = lookup_alpha_f(0.010, 1)
    assert abs(v - 0.90) < 1e-9
    v, _ = lookup_alpha_f(0.060, 1)
    assert abs(v - 1.30) < 1e-9
    # 首末开区间
    v, flag = lookup_alpha_f(0.001, 1)
    assert v == 0.70 and not flag
    v, flag = lookup_alpha_f(0.10, 2)
    assert v == 1.40 and not flag
    # 档间线性内插（0.02432 → 1.15 + 0.432×0.05 = 1.1716）
    v, flag = lookup_alpha_f(0.02432, 1)
    assert flag is True
    assert abs(v - 1.1716) < 1e-9
    # 双排
    v2, _ = lookup_alpha_f(0.010, 2)
    assert abs(v2 - 1.00) < 1e-9


def test_alpha_spt_from_table_cells_and_interpolation():
    # 精确单元格：c=30/φ8/d=25 → 第4列 d25 行 = 1.00；c=25/φ6/d=32 → 第1列 = 1.25
    v, w = alpha_spt_from_table(30.0, 8.0, 25.0)
    assert v == 1.00 and w == []
    v, w = alpha_spt_from_table(25.0, 6.0, 32.0)
    assert v == 1.25 and w == []
    # d 内插（表注允许）：c=25/φ6，d=22 → 1.00 + (2/5)×0.10 = 1.04
    v, w = alpha_spt_from_table(25.0, 6.0, 22.0)
    assert abs(v - 1.04) < 1e-9 and w == []
    # c 档间保守取更小保护层列（实现决策）：c=28 → c25 列并附 warning
    v, w = alpha_spt_from_table(28.0, 6.0, 32.0)
    assert v == 1.25  # c25/φ6 列 d32 = 1.25（比 c30 列 1.15 更保守）
    assert w and "保守" in w[0]


def test_fbd_from_table_row_selection():
    # A 级胶满足最严条件 → 取最高档行
    v, _ = fbd_from_table("A", 180.0, 90.0, 25.0, "C30")
    assert v == 4.5  # s1=7.2d≥7d, s2=3.6d≥3.5d
    # A 级胶仅满足中档 → 第二行
    v, _ = fbd_from_table("A", 160.0, 80.0, 25.0, "C30")
    assert v == 4.0
    # B 级胶仅可用第一行（即使间距满足更严条件）
    v, _ = fbd_from_table("B", 200.0, 100.0, 20.0, "C40")
    assert v == 4.0
    # C60 列（s1=5.5d、s2=2.75d 仅满足第一行条件）
    v, _ = fbd_from_table("A", 110.0, 55.0, 20.0, "C60")
    assert v == 4.5
    # 条件边界含等号：s2=3.0d 精确命中第二行
    v, _ = fbd_from_table("A", 150.0, 60.0, 20.0, "C60")
    assert v == 5.0


# ---------------------------------------------------------------------------
# CalcResult 形状与三态判定
# ---------------------------------------------------------------------------


def test_calcresult_shape_and_clause_trace(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    result = run_calc("cfrp_beam_flexure", DEMO_PARAMS["cfrp_beam_flexure"], store)
    for key in ("module", "inputs", "steps", "capacity", "ratio", "verdict",
                "clauses_used", "warnings", "metrics"):
        assert key in result
    assert result["capacity"]["unit"] == "kN·m"
    assert result["ratio"]["meaning"] == "效应比 M/Mu"
    module = CALC_REGISTRY["cfrp_beam_flexure"]
    assert set(result["clauses_used"]) <= set(module.required_clauses)
    for st in result["steps"]:
        assert st["no"] and st["formula_ref"] and st["clause_ids"]
        assert isinstance(st["values"], dict)
    assert json.dumps(result, ensure_ascii=False)  # 可 JSON 序列化（CLI 输出面）


def test_three_states_cfrp(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    base = DEMO_PARAMS["cfrp_beam_flexure"]
    assert run_calc("cfrp_beam_flexure", base, store)["verdict"] == "满足"
    # 需调整：加固量不足（CF-003-R 口径）
    r = run_calc("cfrp_beam_flexure", dict(base, M=260.0, Afe=50.0), store)
    assert r["verdict"] == "需调整"
    assert r["metrics"]["Afe_req_mm2"] > 50.0
    # 不满足：需求受压区高度超出 0.85·ξb·h0（方法不可行）
    r = run_calc("cfrp_beam_flexure", dict(base, M=350.0), store)
    assert r["verdict"] == "不满足"


def test_post_rebar_table_path_and_mutex(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    # 查表路径（PR-004 口径）
    params = {
        "fc": 14.3, "fy": 360.0, "d": 25.0, "ld": 520.0,
        "cover": 30.0, "stirrup_dia": 8.0,
        "adhesive_grade": 1, "s1": 160.0, "s2": 80.0, "fc_grade": 30,
        "psi_br": 1.0, "psi_w": 1.1, "psi_T": 1.0, "psi_ae": 1.0,
    }
    r = run_calc("post_rebar_anchor", params, store)
    assert r["verdict"] == "满足"
    assert r["metrics"]["alpha_spt"] == 1.0
    assert r["metrics"]["fbd_used_MPa"] == 4.0
    assert abs(r["metrics"]["ls_mm"] - 450.0) < 1e-9
    # 互斥：直接系数与查表路径同给 → ValidationError
    bad = dict(params, alpha_spt=0.9)
    try:
        run_calc("post_rebar_anchor", bad, store)
        raise AssertionError("应当拒绝 alpha_spt 与查表路径同给")
    except ValidationError as exc:
        assert "互斥" in str(exc)
    # 缺失：两路都不给 → ValidationError
    bad2 = {k: v for k, v in params.items()
            if k not in ("cover", "stirrup_dia", "adhesive_grade", "s1", "s2", "fc_grade")}
    try:
        run_calc("post_rebar_anchor", bad2, store)
        raise AssertionError("应当拒绝 αspt/fbd 两路皆缺")
    except ValidationError as exc:
        assert "缺少 alpha_spt" in str(exc)


def test_section_enlarge_sigma_s0_path(repo_data_dir):
    """式(5.2.5)：x/h01 > ξb0 时以 σs0 替代 fy0 重新验算（ξb0 场景输入取小值触发）。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    params = dict(DEMO_PARAMS["section_enlarge_flexure"], M0=100.0, As2=804.0, xi_b0=0.40)
    r = run_calc("section_enlarge_flexure", params, store)
    assert "sigma_s0_MPa" in r["metrics"]
    # σs0 计算值超过 fy0 时按 fy0 封顶（本场景 382.9 → 360）并附 warning
    assert r["metrics"]["sigma_s0_MPa"] == 360.0
    assert any("封顶" in w for w in r["warnings"])
    assert r["verdict"] == "满足"
    assert "GB50367-2013-5.2.5" in r["clauses_used"]


def test_km_multi_layer_optional(repo_data_dir):
    """式(10.2.4-2)：nf/tf 同时提供时输出 km 与实际面积 Af=Afe/km。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    params = dict(DEMO_PARAMS["cfrp_beam_flexure"], nf=3, tf=0.167)
    r = run_calc("cfrp_beam_flexure", params, store)
    km = None
    for st in r["steps"]:
        if "km" in st["values"]:
            km = st["values"]["km"]
    assert km is not None
    # km = 1.16 − 3×240000×0.167/308000 = 0.7696（<0.90 不触发封顶）
    assert abs(km - 0.7696103896103895) < 1e-9
    assert "GB50367-2013-10.2.4" in r["clauses_used"]


def test_es_default_warns_but_computes(repo_data_dir):
    """Es 未提供时取默认 2.0e5 并附 warning（M0=0 时不涉及 Es，改用 M0>0 触发）。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    params = {k: v for k, v in DEMO_PARAMS["cfrp_beam_flexure"].items() if k != "Es"}
    params["M0"] = 80.0
    r = run_calc("cfrp_beam_flexure", params, store)
    assert any("Es 未提供" in w for w in r["warnings"])
    assert r["verdict"] in ("满足", "需调整", "不满足")
