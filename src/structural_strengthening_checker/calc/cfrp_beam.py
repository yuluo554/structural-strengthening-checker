"""碳纤维布加固钢筋混凝土梁正截面受弯承载力验算（GB 50367-2013）。

M2 实装（公式形态与表值 2026-10-05 以正式出版文本扫描件核对，记录见
data/cases/workings/formula_verification_M2.md；式(10.2.3-1~4)=印刷页 76、
式(10.2.8)+表10.2.8=印刷页 79、式(10.2.2)=印刷页 76、式(10.2.4-2)=印刷页 78）：
- 式(10.2.3-1)：M ≤ α1·fc0·b·x·(h−x/2) + f'y0·A's0·(h−a′) − fy0·As0·(h−h0)
  （力矩中心取受拉区边缘，纤维复合材力臂为 0，故式中不含 Afe/ψf）；
- 式(10.2.3-2)：α1·fc0·b·x = fy0·As0 + ψf·ff·Afe − f'y0·A's0；
- 式(10.2.3-3)：ψf = (0.8·εcu·h/x − εcu − εf0)/εf，ψf>1.0 取 1.0；
- 式(10.2.3-4)：x ≥ 2a′；式(10.2.2)：ξb,f = 0.85·ξb；
- 式(10.2.8)：εf0 = αf·M0k/(Es·As·h0)，αf 查表10.2.8；
- 式(10.2.10)：加固后受弯承载力提高幅度 ≤ 40%。

计算流程：①εf0（M0>0 时）→ ②由式(10.2.3-1)反算需求受压区高度 x_M（可行域判定）
→ ③式(10.2.3-2)+(10.2.3-3)联解提供加固量下的 x 与 ψf → ④代回式(10.2.3-1)得 Mu → 三态判定。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.clauses import ClauseStore
from ..core.errors import ValidationError
from ..core.engine import register_calc
from . import common
from .common import (
    CAPACITY_INCREASE_MAX,
    EPS_CU,
    build_result,
    lookup_alpha_f,
    solve_flexure_x,
    solve_x_from_moment,
    step,
)


def _pos(unit: str, meaning: str) -> Dict[str, Any]:
    return {"meaning": meaning, "unit": unit, "range": {"min": 0, "exclusive": True}}


def _nonneg(unit: str, meaning: str) -> Dict[str, Any]:
    return {"meaning": meaning, "unit": unit, "range": {"min": 0, "exclusive": False}}


def _opt_pos(unit: str, meaning: str) -> Dict[str, Any]:
    return {"meaning": meaning, "unit": unit, "range": {"min": 0, "exclusive": True}, "required": False}


def _opt_nonneg(unit: str, meaning: str) -> Dict[str, Any]:
    return {"meaning": meaning, "unit": unit, "range": {"min": 0, "exclusive": False}, "required": False}


@register_calc(
    module_id="cfrp_beam_flexure",
    name="粘贴碳纤维布加固梁正截面受弯承载力验算",
    description="GB 50367-2013 式(10.2.3-1~4)/式(10.2.8)/式(10.2.2)/式(10.2.10)；"
    "M0>0 激活二次受力（滞后应变 εf0）路径。ff/ef 按表4.3.4/表4.3.5 取值（品种/等级/结构类别）。",
    required_clauses=[
        "GB50367-2013-4.3.4",
        "GB50367-2013-4.3.5",
        "GB50367-2013-10.2.1",
        "GB50367-2013-10.2.2",
        "GB50367-2013-10.2.3",
        "GB50367-2013-10.2.4",
        "GB50367-2013-10.2.8",
        "GB50367-2013-10.2.10",
        "GB50367-2013-10.2.11",
    ],
    param_schema={
        "b": _pos("mm", "矩形截面宽度"),
        "h": _pos("mm", "矩形截面高度"),
        "fc": _pos("MPa", "原构件混凝土轴心抗压强度设计值 fc0"),
        "As": _pos("mm2", "原截面受拉钢筋截面面积 As0"),
        "fy": _pos("MPa", "原截面受拉钢筋抗拉强度设计值 fy0"),
        "Afe": _pos("mm2", "碳纤维复合材有效截面面积"),
        "Ecf": _pos("MPa", "碳纤维复合材弹性模量（与 ff/ef 一致性提示用）"),
        "M0": _nonneg("kN·m", "加固前弯矩标准值 M0k（0=一次受力，>0=二次受力）"),
        "M": _pos("kN·m", "加固后弯矩设计值"),
        "ff": _pos("MPa", "纤维复合材抗拉强度设计值（表4.3.4）"),
        "ef": _pos("-", "纤维复合材拉应变设计值 εf（表4.3.5）"),
        "as": _pos("mm", "受拉钢筋合力点至受拉边缘距离（h0=h−as）"),
        "Asc": _opt_nonneg("mm2", "原受压钢筋截面面积 A's0（无则 0）"),
        "ap": _opt_pos("mm", "受压钢筋合力点至受压边缘距离 a′（Asc>0 时必填）"),
        "fyp": _opt_pos("MPa", "受压钢筋抗压强度设计值 f'y0（默认取 fy）"),
        "xi_b": _opt_nonneg("-", "加固前相对界限受压区高度 ξb（按 GB 50010；缺省则跳过 ξb,f 检查）"),
        "alpha1": _opt_nonneg("-", "受压区混凝土矩形应力图应力值系数 α1（≤C50 取 1.0，C50~C80 内插）"),
        "Es": _opt_pos("MPa", "原钢筋弹性模量（默认 2.0e5，HRB400 常用值）"),
        "rho_te": _opt_pos("-", "有效受拉钢筋配筋率 ρte（默认按 Ate=0.5bh 计算）"),
        "rebar_rows": _opt_pos("-", "受拉钢筋排数（1=单排，2=双排，查表10.2.8 用）"),
        "sigma_s0": _opt_pos("MPa", "原构件钢筋应力 σs0（≤150 且 ρte≤0.05 时 αf×0.9，表10.2.8 注2）"),
        "nf": _opt_pos("-", "纤维织物层数（提供 nf 与 tf 时按式(10.2.4-2)折减 km）"),
        "tf": _opt_pos("mm", "纤维织物单层厚度（与 nf 同时提供）"),
    },
)
def compute_cfrp_beam_flexure(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    warnings: List[str] = []
    b, h, fc = params["b"], params["h"], params["fc"]
    As, fy, Afe = params["As"], params["fy"], params["Afe"]
    M0, M = params["M0"], params["M"]
    ff, ef, a_s = params["ff"], params["ef"], params["as"]
    Asc = params.get("Asc", 0.0)
    ap = params.get("ap", 0.0)
    fyp = params.get("fyp", fy)
    xi_b = params.get("xi_b")
    alpha1 = params.get("alpha1", 1.0)
    Es = params.get("Es", 2.0e5)
    rebar_rows = int(params.get("rebar_rows", 1))
    rho_te = params.get("rho_te")
    sigma_s0 = params.get("sigma_s0")

    h0 = h - a_s
    if h0 <= 0.0:
        raise ValidationError("几何参数无效: h−as=%s ≤ 0（受拉钢筋合力点必须在截面内）" % h0)
    if Asc > 0.0 and ap <= 0.0:
        raise ValidationError("提供受压钢筋 Asc 时必须同时提供 ap（a′）")
    if fc > 23.1 and "alpha1" not in params:
        warnings.append(
            "fc=%s 超过 C50 轴心抗压设计值 23.1MPa：α1 应按 C50~C80 线性内插取值，"
            "当前默认 1.0 偏于不安全，请显式提供 alpha1" % fc
        )
    if "Es" not in params:
        warnings.append("Es 未提供，默认取 2.0e5 MPa（HRB400 级常用值），请按实际钢筋牌号复核")

    steps = []
    clauses_used = {
        "GB50367-2013-10.2.3",
        "GB50367-2013-10.2.2",
        "GB50367-2013-10.2.10",
    }

    # ── 步骤1：二次受力滞后应变 εf0（式10.2.8 + 表10.2.8） ──
    eps_f0 = 0.0
    if M0 > 0.0:
        if rho_te is None:
            rho_te = As / (0.5 * b * h)
            warnings.append("rho_te 未提供，按 GB 50010 有效受拉混凝土截面面积 Ate=0.5bh 计算 ρte")
        alpha_f, interpolated = lookup_alpha_f(rho_te, rebar_rows)
        if interpolated:
            warnings.append("ρte 落在表10.2.8 分档点之间，αf 按线性内插取值（实现决策，规范未注明）")
        if sigma_s0 is not None and sigma_s0 <= 150.0 and rho_te <= 0.05:
            alpha_f *= common.ALPHA_F_ADJUST
            warnings.append("σs0≤150MPa 且 ρte≤0.05，αf 乘调整系数 0.9（表10.2.8 注2）")
        eps_f0 = alpha_f * (M0 * 1.0e6) / (Es * As * h0)
        steps.append(
            step(
                1, "式(10.2.8)+表10.2.8", "εf0 = αf·M0k/(Es·As·h0)",
                {"αf": alpha_f, "M0k_kNm": M0, "Es_MPa": Es, "As_mm2": As, "h0_mm": h0, "εf0": eps_f0},
                None, ["GB50367-2013-10.2.8"],
            )
        )
    else:
        steps.append(
            step(
                1, "式(10.2.3) 符号说明", "不考虑二次受力影响，取 εf0 = 0",
                {"εf0": 0.0}, None, ["GB50367-2013-10.2.3"],
            )
        )

    a_fc_b = alpha1 * fc * b
    t_net = fy * As - fyp * Asc

    # ── 步骤2：需求受压区高度 x_M（式10.2.3-1 反算）与可行域判定（式10.2.2） ──
    m_res = M * 1.0e6 + fy * As * (h - h0) - fyp * Asc * (h - ap)
    x_m = solve_x_from_moment(a_fc_b, m_res, h)
    xi_bf = 0.85 * xi_b if xi_b is not None else None
    infeasible = False
    if xi_b is not None:
        steps.append(
            step(
                2, "式(10.2.2)+式(10.2.3-1)", "ξb,f=0.85·ξb；x_M 由 M≤α1·fc0·b·x·(h−x/2)+f'y0·A's0·(h−a′)−fy0·As0·(h−h0) 反算",
                {"ξb": xi_b, "ξb,f": xi_bf, "x_M_mm": x_m, "ξb,f·h0_mm": xi_bf * h0},
                "mm", ["GB50367-2013-10.2.2", "GB50367-2013-10.2.3"],
            )
        )
        if x_m is None or x_m > xi_bf * h0:
            infeasible = True
            warnings.append(
                "需求受压区高度超出 ξb,f·h0=%.2fmm（式10.2.2 限值），粘贴纤维复合材加固不可行，"
                "应增大截面或改用其他加固方法" % (xi_bf * h0)
            )
    else:
        steps.append(
            step(
                2, "式(10.2.3-1)", "x_M 由力矩平衡反算（未提供 xi_b，跳过式(10.2.2) 可行域检查）",
                {"x_M_mm": x_m}, "mm", ["GB50367-2013-10.2.3"],
            )
        )
        warnings.append("未提供 xi_b（GB 50010 界限相对受压区高度），未执行 ξb,f=0.85ξb 上限检查")

    # ── 步骤3：提供加固量下的 ULS 受压区高度 x 与强度利用系数 ψf（式10.2.3-2/3） ──
    k_coupling = ff * Afe / ef
    f_full = ff * Afe
    x, psi_f = solve_flexure_x(a_fc_b, t_net, k_coupling, eps_f0, h, f_full)
    if x > h:
        warnings.append("受压区高度 x=%.2fmm 超过截面高度 h，超出式(10.2.3) 平截面适用范围" % x)
        infeasible = True
    if Asc > 0.0 and x < 2.0 * ap:
        warnings.append(
            "x=%.2fmm < 2a′=%.2fmm（式10.2.3-4）：受压钢筋未达屈服，按条文近似取 x=2a′ 重算承载力" % (x, 2.0 * ap)
        )
        x = 2.0 * ap
    steps.append(
        step(
            3, "式(10.2.3-2)+(10.2.3-3)", "α1·fc0·b·x = fy0·As0 + ψf·ff·Afe − f'y0·A's0；ψf=(0.8·εcu·h/x−εcu−εf0)/εf（>1.0 取 1.0）",
            {"x_mm": x, "ψf": psi_f, "εcu": EPS_CU, "εf0": eps_f0},
            "mm", ["GB50367-2013-10.2.3"],
        )
    )

    # ── 步骤4：加固后受弯承载力 Mu（代回式10.2.3-1） ──
    mu = a_fc_b * x * (h - x / 2.0) + fyp * Asc * (h - ap) - fy * As * (h - h0)
    mu_knm = mu / 1.0e6
    steps.append(
        step(
            4, "式(10.2.3-1)", "Mu = α1·fc0·b·x·(h−x/2) + f'y0·A's0·(h−a′) − fy0·As0·(h−h0)",
            {"x_mm": x, "Mu_kNm": mu_knm}, "kN·m", ["GB50367-2013-10.2.3"],
        )
    )

    # ── 步骤5：需求有效加固量 Afe,req（式10.2.3-2 反算，设计提示） ──
    afe_req = None
    if x_m is not None and not infeasible:
        psi_m_raw = (0.8 * EPS_CU * h / x_m - EPS_CU - eps_f0) / ef
        psi_m = min(max(psi_m_raw, 0.0), 1.0)
        afe_req = max((a_fc_b * x_m - t_net) / (psi_m * ff), 0.0) if psi_m > 0.0 else None
        steps.append(
            step(
                5, "式(10.2.3-2) 反算", "Afe,req = (α1·fc0·b·x_M − fy0·As0 + f'y0·A's0)/(ψf(x_M)·ff)",
                {"x_M_mm": x_m, "ψf(x_M)": psi_m, "Afe_req_mm2": afe_req},
                "mm2", ["GB50367-2013-10.2.3"],
            )
        )

    # ── 步骤6：承载力提高幅度检查（式10.2.10，≤40%） ──
    increase = None
    x0 = t_net / a_fc_b
    increase_ok = True
    if xi_b is not None and x0 > xi_b * h0:
        warnings.append("原截面受压区高度 x0 超过 ξb·h0（原截面超筋），加固前承载力 Mu0 无解析意义，跳过 40% 提高幅度检查")
    elif Asc > 0.0 and x0 < 2.0 * ap:
        warnings.append("原截面 x0 < 2a′，跳过 40% 提高幅度检查（原截面双筋近似不适用）")
    else:
        mu0 = a_fc_b * x0 * (h0 - x0 / 2.0) + fyp * Asc * (h0 - ap)
        mu0_knm = mu0 / 1.0e6
        increase = mu_knm / mu0_knm - 1.0
        increase_ok = increase <= CAPACITY_INCREASE_MAX
        steps.append(
            step(
                6, "式(10.2.10)", "(Mu − Mu0)/Mu0 ≤ 0.40",
                {"Mu0_kNm": mu0_knm, "提高幅度": increase, "限值": CAPACITY_INCREASE_MAX},
                None, ["GB50367-2013-10.2.10"],
            )
        )

    # ── 步骤7（可选）：多层粘贴厚度折减（式10.2.4-2） ──
    nf, tf = params.get("nf"), params.get("tf")
    if nf is not None and tf is not None:
        km = min(1.16 - nf * params["Ecf"] * tf / 308000.0, 0.90)
        af_actual = Afe / km
        steps.append(
            step(
                len(steps) + 1, "式(10.2.4-1)+(10.2.4-2)", "km = 1.16 − nf·Ef·tf/308000（≤0.90）；Af = Afe/km",
                {"nf": nf, "tf": tf, "km": km, "Af_mm2": af_actual},
                "mm2", ["GB50367-2013-10.2.4"],
            )
        )
        clauses_used.add("GB50367-2013-10.2.4")

    # ── 三态判定 ──
    if infeasible:
        verdict = "不满足"
    elif M > mu_knm:
        verdict = "需调整"
        if afe_req is not None:
            warnings.append("加固量不足：需求有效截面面积 Afe,req=%.2fmm² > 提供 %.2fmm²，请增大加固量" % (afe_req, Afe))
    elif xi_b is not None and x > xi_bf * h0:
        verdict = "需调整"
        warnings.append(
            "加固后受压区高度 x=%.2fmm 超过 ξb,f·h0=%.2fmm（式10.2.2），加固量过大，请减小" % (x, xi_bf * h0)
        )
    elif not increase_ok:
        verdict = "需调整"
        warnings.append(
            "承载力提高幅度 %.1f%% 超过 40%%（式10.2.10），请减小加固量并复核受剪承载力" % (increase * 100.0)
        )
    else:
        verdict = "满足"

    metrics = {"Mu_kNm": mu_knm, "x_mm": x, "psi_f": psi_f, "ratio": M / mu_knm if mu_knm > 0 else None}
    if M0 > 0.0:
        metrics["alpha_f"] = alpha_f
        metrics["epsilon_f0"] = eps_f0
    if afe_req is not None:
        metrics["Afe_req_mm2"] = afe_req

    return build_result(
        "cfrp_beam_flexure", params, steps, mu_knm, "kN·m",
        M / mu_knm if mu_knm > 0 else None, "效应比 M/Mu",
        verdict, sorted(clauses_used), warnings, metrics,
    )
