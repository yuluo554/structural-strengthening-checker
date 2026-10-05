"""粘贴钢板加固受弯承载力验算（GB 50367-2013）。

M2 实装（公式形态与表值 2026-10-05 以正式出版文本扫描件核对，记录见
data/cases/workings/formula_verification_M2.md；式(9.2.2)/式(9.2.3-1~4)=印刷页 62、
式(9.2.9)+表9.2.9=印刷页 65）：
- 式(9.2.3-1)：M ≤ α1·fc0·b·x·(h−x/2) + f'y0·A's0·(h−a′) + f'sp·A'sp·h − fy0·As0·(h−h0)
  （力矩中心取受拉区边缘，受拉钢板力臂为 0；受压钢板项 A'sp>0 时计入）；
- 式(9.2.3-2)：α1·fc0·b·x = ψsp·fsp·Asp + fy0·As0 − f'y0·A's0 − f'sp·A'sp；
- 式(9.2.3-3)：ψsp = (0.8·εcu·h/x − εcu − εsp,0)/(fsp/Esp)，ψsp>1.0 取 1.0；
- 式(9.2.3-4)：x ≥ 2a′；式(9.2.2)：ξb,sp = 0.85·ξb；
- 式(9.2.9)：εsp,0 = αsp·M0k/(Es·As·h0)，αsp 查表9.2.9（与表10.2.8 数值相同）；
- 式(9.2.11)：加固后受弯承载力提高幅度 ≤ 40%。
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
from .cfrp_beam import _nonneg, _opt_nonneg, _opt_pos, _pos


@register_calc(
    module_id="steel_plate_flexure",
    name="粘贴钢板加固受弯承载力验算",
    description="GB 50367-2013 式(9.2.3-1~4)/式(9.2.9)/式(9.2.2)/式(9.2.11)；"
    "M0>0 激活二次受力（滞后应变 εsp,0）路径。fp 为钢板抗拉强度设计值。",
    required_clauses=[
        "GB50367-2013-9.2.1",
        "GB50367-2013-9.2.2",
        "GB50367-2013-9.2.3",
        "GB50367-2013-9.2.5",
        "GB50367-2013-9.2.6",
        "GB50367-2013-9.2.9",
        "GB50367-2013-9.2.11",
        "GB50367-2013-9.2.12",
    ],
    param_schema={
        "b": _pos("mm", "矩形截面宽度"),
        "h": _pos("mm", "矩形截面高度"),
        "fc": _pos("MPa", "原构件混凝土轴心抗压强度设计值 fc0"),
        "As": _pos("mm2", "原构件受拉钢筋截面面积 As0"),
        "fy": _pos("MPa", "原构件受拉钢筋抗拉强度设计值 fy0"),
        "Ap": _pos("mm2", "受拉钢板截面面积 Asp"),
        "fp": _pos("MPa", "加固钢板抗拉强度设计值 fsp"),
        "M0": _nonneg("kN·m", "加固前弯矩标准值 M0k（0=一次受力，>0=二次受力）"),
        "M": _pos("kN·m", "加固后弯矩设计值"),
        "as": _pos("mm", "受拉钢筋合力点至受拉边缘距离（h0=h−as）"),
        "Apc": _opt_nonneg("mm2", "受压钢板截面面积 A'sp（无则 0）"),
        "ap": _opt_pos("mm", "受压钢筋合力点至受压边缘距离 a′（Asc>0 时必填）"),
        "Asc": _opt_nonneg("mm2", "原构件受压钢筋截面面积 A's0（无则 0）"),
        "fyp": _opt_pos("MPa", "受压钢筋抗压强度设计值 f'y0（默认取 fy）"),
        "xi_b": _opt_nonneg("-", "加固前相对界限受压区高度 ξb（按 GB 50010；缺省则跳过 ξb,sp 检查）"),
        "alpha1": _opt_nonneg("-", "受压区混凝土矩形应力图应力值系数 α1（≤C50 取 1.0）"),
        "Es": _opt_pos("MPa", "原钢筋弹性模量（默认 2.0e5，HRB400 级常用值）"),
        "Esp": _opt_pos("MPa", "钢板弹性模量 Esp（默认 2.06e5，Q235 常用值）"),
        "rho_te": _opt_pos("-", "有效受拉钢筋配筋率 ρte（默认按 Ate=0.5bh 计算）"),
        "rebar_rows": _opt_pos("-", "受拉钢筋排数（1=单排，2=双排，查表9.2.9 用）"),
        "sigma_s0": _opt_pos("MPa", "原构件钢筋应力 σs0（≤150 且 ρte≤0.05 时 αsp×0.9，表9.2.9 注2）"),
    },
)
def compute_steel_plate_flexure(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    warnings: List[str] = []
    b, h, fc = params["b"], params["h"], params["fc"]
    As, fy, Ap, fp = params["As"], params["fy"], params["Ap"], params["fp"]
    M0, M = params["M0"], params["M"]
    a_s = params["as"]
    Asc = params.get("Asc", 0.0)
    Apc = params.get("Apc", 0.0)
    ap = params.get("ap", 0.0)
    fyp = params.get("fyp", fy)
    fpp = params.get("fpp", fp)  # 受压钢板抗压强度设计值（钢材同 fp）
    xi_b = params.get("xi_b")
    alpha1 = params.get("alpha1", 1.0)
    Es = params.get("Es", 2.0e5)
    Esp = params.get("Esp", 2.06e5)
    rebar_rows = int(params.get("rebar_rows", 1))
    rho_te = params.get("rho_te")
    sigma_s0 = params.get("sigma_s0")

    h0 = h - a_s
    if h0 <= 0.0:
        raise ValidationError("几何参数无效: h−as=%s ≤ 0（受拉钢筋合力点必须在截面内）" % h0)
    if (Asc > 0.0 or Apc > 0.0) and ap <= 0.0:
        raise ValidationError("提供受压钢筋 Asc 或受压钢板 Apc 时必须同时提供 ap（a′）")
    if fc > 23.1 and "alpha1" not in params:
        warnings.append(
            "fc=%s 超过 C50 轴心抗压设计值 23.1MPa：α1 应按 C50~C80 线性内插取值，"
            "当前默认 1.0 偏于不安全，请显式提供 alpha1" % fc
        )
    if "Es" not in params:
        warnings.append("Es 未提供，默认取 2.0e5 MPa（HRB400 级常用值），请按实际钢筋牌号复核")
    if "Esp" not in params:
        warnings.append("Esp 未提供，默认取 2.06e5 MPa（Q235 钢板常用值），请按实际钢板牌号复核")

    steps = []
    clauses_used = {"GB50367-2013-9.2.3", "GB50367-2013-9.2.2", "GB50367-2013-9.2.11"}

    # ── 步骤1：二次受力滞后应变 εsp,0（式9.2.9 + 表9.2.9） ──
    eps_sp0 = 0.0
    if M0 > 0.0:
        if rho_te is None:
            rho_te = As / (0.5 * b * h)
            warnings.append("rho_te 未提供，按 GB 50010 有效受拉混凝土截面面积 Ate=0.5bh 计算 ρte")
        alpha_sp, interpolated = lookup_alpha_f(rho_te, rebar_rows)
        if interpolated:
            warnings.append("ρte 落在表9.2.9 分档点之间，αsp 按线性内插取值（实现决策，规范未注明）")
        if sigma_s0 is not None and sigma_s0 <= 150.0 and rho_te <= 0.05:
            alpha_sp *= common.ALPHA_F_ADJUST
            warnings.append("σs0≤150MPa 且 ρte≤0.05，αsp 乘调整系数 0.9（表9.2.9 注2）")
        eps_sp0 = alpha_sp * (M0 * 1.0e6) / (Es * As * h0)
        steps.append(
            step(
                1, "式(9.2.9)+表9.2.9", "εsp,0 = αsp·M0k/(Es·As·h0)",
                {"αsp": alpha_sp, "M0k_kNm": M0, "Es_MPa": Es, "As_mm2": As, "h0_mm": h0, "εsp,0": eps_sp0},
                None, ["GB50367-2013-9.2.9"],
            )
        )
    else:
        steps.append(
            step(
                1, "式(9.2.3) 符号说明", "不考虑二次受力影响，取 εsp,0 = 0",
                {"εsp,0": 0.0}, None, ["GB50367-2013-9.2.3"],
            )
        )

    a_fc_b = alpha1 * fc * b
    t_net = fy * As - fyp * Asc - fpp * Apc

    # ── 步骤2：需求受压区高度 x_M（式9.2.3-1 反算）与可行域判定（式9.2.2） ──
    m_res = M * 1.0e6 + fy * As * (h - h0) - fyp * Asc * (h - ap) - fpp * Apc * h
    x_m = solve_x_from_moment(a_fc_b, m_res, h)
    xi_bsp = 0.85 * xi_b if xi_b is not None else None
    infeasible = False
    if xi_b is not None:
        steps.append(
            step(
                2, "式(9.2.2)+式(9.2.3-1)", "ξb,sp=0.85·ξb；x_M 由 M≤α1·fc0·b·x·(h−x/2)+f'y0·A's0·(h−a′)+f'sp·A'sp·h−fy0·As0·(h−h0) 反算",
                {"ξb": xi_b, "ξb,sp": xi_bsp, "x_M_mm": x_m, "ξb,sp·h0_mm": xi_bsp * h0},
                "mm", ["GB50367-2013-9.2.2", "GB50367-2013-9.2.3"],
            )
        )
        if x_m is None or x_m > xi_bsp * h0:
            infeasible = True
            warnings.append(
                "需求受压区高度超出 ξb,sp·h0=%.2fmm（式9.2.2 限值），粘贴钢板加固不可行，"
                "应增大截面或改用其他加固方法" % (xi_bsp * h0)
            )
    else:
        steps.append(
            step(
                2, "式(9.2.3-1)", "x_M 由力矩平衡反算（未提供 xi_b，跳过式(9.2.2) 可行域检查）",
                {"x_M_mm": x_m}, "mm", ["GB50367-2013-9.2.3"],
            )
        )
        warnings.append("未提供 xi_b（GB 50010 界限相对受压区高度），未执行 ξb,sp=0.85ξb 上限检查")

    # ── 步骤3：提供加固量下的 ULS 受压区高度 x 与强度折减系数 ψsp（式9.2.3-2/3） ──
    k_coupling = Esp * Ap
    f_full = fp * Ap
    x, psi_sp = solve_flexure_x(a_fc_b, t_net, k_coupling, eps_sp0, h, f_full)
    if x > h:
        warnings.append("受压区高度 x=%.2fmm 超过截面高度 h，超出式(9.2.3) 平截面适用范围" % x)
        infeasible = True
    if (Asc > 0.0 or Apc > 0.0) and x < 2.0 * ap:
        warnings.append(
            "x=%.2fmm < 2a′=%.2fmm（式9.2.3-4）：受压钢筋未达屈服，按条文近似取 x=2a′ 重算承载力" % (x, 2.0 * ap)
        )
        x = 2.0 * ap
    steps.append(
        step(
            3, "式(9.2.3-2)+(9.2.3-3)",
            "α1·fc0·b·x = ψsp·fsp·Asp + fy0·As0 − f'y0·A's0 − f'sp·A'sp；ψsp=(0.8·εcu·h/x−εcu−εsp,0)/(fsp/Esp)（>1.0 取 1.0）",
            {"x_mm": x, "ψsp": psi_sp, "εcu": EPS_CU, "εsp,0": eps_sp0},
            "mm", ["GB50367-2013-9.2.3"],
        )
    )

    # ── 步骤4：加固后受弯承载力 Mu（代回式9.2.3-1） ──
    mu = (
        a_fc_b * x * (h - x / 2.0)
        + fyp * Asc * (h - ap)
        + fpp * Apc * h
        - fy * As * (h - h0)
    )
    mu_knm = mu / 1.0e6
    steps.append(
        step(
            4, "式(9.2.3-1)",
            "Mu = α1·fc0·b·x·(h−x/2) + f'y0·A's0·(h−a′) + f'sp·A'sp·h − fy0·As0·(h−h0)",
            {"x_mm": x, "Mu_kNm": mu_knm}, "kN·m", ["GB50367-2013-9.2.3"],
        )
    )

    # ── 步骤5：需求钢板量 Asp,req（式9.2.3-2 反算，设计提示） ──
    ap_req = None
    if x_m is not None and not infeasible:
        psi_m_raw = (0.8 * EPS_CU * h / x_m - EPS_CU - eps_sp0) * Esp / fp
        psi_m = min(max(psi_m_raw, 0.0), 1.0)
        ap_req = max((a_fc_b * x_m - t_net) / (psi_m * fp), 0.0) if psi_m > 0.0 else None
        steps.append(
            step(
                5, "式(9.2.3-2) 反算", "Asp,req = (α1·fc0·b·x_M − fy0·As0 + f'y0·A's0 + f'sp·A'sp)/(ψsp(x_M)·fsp)",
                {"x_M_mm": x_m, "ψsp(x_M)": psi_m, "Asp_req_mm2": ap_req},
                "mm2", ["GB50367-2013-9.2.3"],
            )
        )

    # ── 步骤6：承载力提高幅度检查（式9.2.11，≤40%） ──
    increase = None
    x0 = (fy * As - fyp * Asc) / a_fc_b
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
                6, "式(9.2.11)", "(Mu − Mu0)/Mu0 ≤ 0.40",
                {"Mu0_kNm": mu0_knm, "提高幅度": increase, "限值": CAPACITY_INCREASE_MAX},
                None, ["GB50367-2013-9.2.11"],
            )
        )

    # ── 三态判定 ──
    if infeasible:
        verdict = "不满足"
    elif M > mu_knm:
        verdict = "需调整"
        if ap_req is not None:
            warnings.append("钢板量不足：需求截面面积 Asp,req=%.2fmm² > 提供 %.2fmm²，请增大加固量" % (ap_req, Ap))
    elif xi_b is not None and x > xi_bsp * h0:
        verdict = "需调整"
        warnings.append(
            "加固后受压区高度 x=%.2fmm 超过 ξb,sp·h0=%.2fmm（式9.2.2），加固量过大，请减小" % (x, xi_bsp * h0)
        )
    elif not increase_ok:
        verdict = "需调整"
        warnings.append(
            "承载力提高幅度 %.1f%% 超过 40%%（式9.2.11），请减小加固量并复核受剪承载力" % (increase * 100.0)
        )
    else:
        verdict = "满足"

    metrics = {"Mu_kNm": mu_knm, "x_mm": x, "psi_sp": psi_sp, "ratio": M / mu_knm if mu_knm > 0 else None}
    if M0 > 0.0:
        metrics["alpha_sp"] = alpha_sp
        metrics["epsilon_sp0"] = eps_sp0
    if ap_req is not None:
        metrics["Asp_req_mm2"] = ap_req

    return build_result(
        "steel_plate_flexure", params, steps, mu_knm, "kN·m",
        M / mu_knm if mu_knm > 0 else None, "效应比 M/Mu",
        verdict, sorted(clauses_used), warnings, metrics,
    )
