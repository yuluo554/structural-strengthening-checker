"""增大截面加固法（受拉区增设钢筋混凝土层）受弯承载力验算（GB 50367-2013）。

M2 实装（公式形态与表值 2026-10-05 以正式出版文本扫描件核对，记录见
data/cases/workings/formula_verification_M2.md；式(5.2.3-1~3)=印刷页 21/22、
式(5.2.4-1~3)+式(5.2.5)=印刷页 23）：
- 式(5.2.3-1)：M ≤ αs·fy·As·(h0−x/2) + fy0·As0·(h01−x/2) + f'y0·A's0·(x/2−a′)
  （力矩中心取受压区 x/2 处；式中 As/As0 为新增/原受拉钢筋，本模块参数映射
  As2→公式 As、As→公式 As0）；
- 式(5.2.3-2)：α1·fc0·b·x = fy0·As0 + αs·fy·As − f'y0·A's0（对 x 线性，直接解）；
- 式(5.2.3-3)：2a′ ≤ x ≤ ξb·h0；
- 式(5.2.4-1)：ξb = β1/(1 + αs·fy/(εcu·Es) + εs1/εcu)；
- 式(5.2.4-2)：εs1 = (1.6·h0/h01 − 0.6)·εs0；
- 式(5.2.4-3)：εs0 = M0k/(0.85·h01·As0·Es0)（M0=0 时 εs0=εs1=0）；
- 式(5.2.5)：x/h01 > ξb0 时以 σs0=(0.8·h01/x−1)·εcu·Es≤fy0 替代 fy0 重新验算；
- αs = 0.9（新增钢筋强度利用系数，已核对条文）。

条文说明（已核对）：不论一次/二次受力均可近似按一次受力计算，新增钢筋强度统一折减 αs=0.9；
新增混凝土位于受拉区，其强度 fc2 不进入正截面受弯计算（保留参数仅作记录）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from ..core.clauses import ClauseStore
from ..core.errors import ValidationError
from ..core.engine import register_calc
from .common import EPS_CU, build_result, step
from .cfrp_beam import _nonneg, _opt_nonneg, _opt_pos, _pos

ALPHA_S = 0.9  # 新增钢筋强度利用系数（式5.2.3 符号说明，已核对）


@register_calc(
    module_id="section_enlarge_flexure",
    name="增大截面加固法受弯承载力验算（受拉区加固）",
    description="GB 50367-2013 式(5.2.3-1~3)/式(5.2.4-1~3)/式(5.2.5)；αs=0.9；"
    "M0>0 时按式(5.2.4-2/3)计入初始应变 εs0/εs1 对 ξb 的折减。受拉区加固，fc2 不进入正截面计算。",
    required_clauses=[
        "GB50367-2013-5.1.5",
        "GB50367-2013-5.2.3",
        "GB50367-2013-5.2.4",
        "GB50367-2013-5.2.5",
    ],
    param_schema={
        "b": _pos("mm", "原截面宽度"),
        "h": _pos("mm", "原截面高度"),
        "bf": _pos("mm", "新增截面宽度（受拉区加固不进入正截面计算，仅记录）"),
        "hf": _pos("mm", "新增截面高度（受拉侧新增层厚度）"),
        "fc": _pos("MPa", "原构件混凝土轴心抗压强度设计值 fc0"),
        "fc2": _pos("MPa", "新增混凝土强度设计值（受拉区加固不进入正截面计算，仅记录）"),
        "As": _pos("mm2", "原受拉钢筋截面面积 As0"),
        "fy": _pos("MPa", "原钢筋抗拉强度设计值 fy0"),
        "As2": _pos("mm2", "新增受拉钢筋截面面积 As（公式符号）"),
        "fy2": _pos("MPa", "新增钢筋抗拉强度设计值 fy（公式符号）"),
        "as": _pos("mm", "原受拉钢筋合力点至原截面受拉边缘距离（h01=h−as）"),
        "as2": _pos("mm", "新增受拉钢筋合力点至加固后截面受拉边缘距离（h0=h+hf−as2）"),
        "M0": _nonneg("kN·m", "加固前弯矩标准值 M0k（0=一次受力）"),
        "M": _pos("kN·m", "加固后弯矩设计值"),
        "Asc": _opt_nonneg("mm2", "原受压钢筋截面面积 A's0（无则 0）"),
        "ap": _opt_pos("mm", "受压钢筋合力点至受压边缘距离 a′（Asc>0 时必填）"),
        "fyp": _opt_pos("MPa", "原钢筋抗压强度设计值 f'y0（默认取 fy）"),
        "alpha1": _opt_nonneg("-", "受压区混凝土矩形应力图应力值系数 α1（≤C50 取 1.0）"),
        "beta1": _opt_nonneg("-", "计算系数 β1（≤C50 取 0.80，C80 取 0.74，内插）"),
        "Es": _opt_pos("MPa", "钢筋弹性模量（默认 2.0e5，HRB400 级常用值）"),
        "xi_b0": _opt_nonneg("-", "原截面相对界限受压区高度 ξb0（提供时执行式(5.2.5) σs0 复核）"),
    },
)
def compute_section_enlarge_flexure(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    warnings: List[str] = []
    b, h, hf = params["b"], params["h"], params["hf"]
    fc = params["fc"]
    As, fy, As2, fy2 = params["As"], params["fy"], params["As2"], params["fy2"]
    a_s, a_s2 = params["as"], params["as2"]
    M0, M = params["M0"], params["M"]
    Asc = params.get("Asc", 0.0)
    ap = params.get("ap", 0.0)
    fyp = params.get("fyp", fy)
    alpha1 = params.get("alpha1", 1.0)
    beta1 = params.get("beta1", 0.8)
    Es = params.get("Es", 2.0e5)
    xi_b0 = params.get("xi_b0")

    h01 = h - a_s
    h0 = h + hf - a_s2
    if h01 <= 0.0 or h0 <= h01:
        raise ValidationError(
            "几何参数无效: h01=h−as=%.2f, h0=h+hf−as2=%.2f（加固后有效高度必须大于原有效高度）" % (h01, h0)
        )
    if Asc > 0.0 and ap <= 0.0:
        raise ValidationError("提供受压钢筋 Asc 时必须同时提供 ap（a′）")
    if fc > 23.1 and "alpha1" not in params:
        warnings.append(
            "fc=%s 超过 C50 轴心抗压设计值 23.1MPa：α1/β1 应按 C50~C80 线性内插取值，"
            "当前默认 α1=1.0/β1=0.8 偏于不安全，请显式提供" % fc
        )
    if "Es" not in params:
        warnings.append("Es 未提供，默认取 2.0e5 MPa（HRB400 级常用值），请按实际钢筋牌号复核")

    steps = []
    clauses_used = {"GB50367-2013-5.2.3", "GB50367-2013-5.2.4"}

    # ── 步骤1：初始应变 εs0/εs1（式5.2.4-2/3，M0>0 时）与 ξb（式5.2.4-1） ──
    eps_s0 = 0.0
    if M0 > 0.0:
        eps_s0 = (M0 * 1.0e6) / (0.85 * h01 * As * Es)
        steps.append(
            step(
                1, "式(5.2.4-3)", "εs0 = M0k/(0.85·h01·As0·Es0)",
                {"M0k_kNm": M0, "h01_mm": h01, "As0_mm2": As, "Es_MPa": Es, "εs0": eps_s0},
                None, ["GB50367-2013-5.2.4"],
            )
        )
    eps_s1 = (1.6 * h0 / h01 - 0.6) * eps_s0
    xi_b = beta1 / (1.0 + ALPHA_S * fy2 / (EPS_CU * Es) + eps_s1 / EPS_CU)
    steps.append(
        step(
            len(steps) + 1, "式(5.2.4-1)+(5.2.4-2)",
            "εs1=(1.6·h0/h01−0.6)·εs0；ξb=β1/(1+αs·fy/(εcu·Es)+εs1/εcu)",
            {"εs1": eps_s1, "β1": beta1, "αs": ALPHA_S, "ξb": xi_b},
            None, ["GB50367-2013-5.2.4"],
        )
    )

    # ── 步骤2：受压区高度 x（式5.2.3-2 对 x 线性，直接解；x/h01>ξb0 时按式5.2.5 以 σs0 复核） ──
    a_fc_b = alpha1 * fc * b
    sigma_s0 = fy
    sigma_path = False
    x_lin = (fy * As + ALPHA_S * fy2 * As2 - fyp * Asc) / a_fc_b
    if xi_b0 is not None and x_lin / h01 > xi_b0:
        sigma_path = True
        # A·x² − (αs·fy2·As2 − f'y·Asc − As·Es·εcu)·x − 0.8·As·Es·εcu·h01 = 0
        b_coef = ALPHA_S * fy2 * As2 - fyp * Asc - As * Es * EPS_CU
        c_coef = 0.8 * As * Es * EPS_CU * h01
        disc = b_coef * b_coef + 4.0 * a_fc_b * c_coef
        x = (b_coef + math.sqrt(disc)) / (2.0 * a_fc_b)
        sigma_s0 = min((0.8 * h01 / x - 1.0) * EPS_CU * Es, fy)
        if sigma_s0 < (0.8 * h01 / x - 1.0) * EPS_CU * Es:
            warnings.append("式(5.2.5) σs0 计算值超过 fy0，已按 fy0 封顶")
        steps.append(
            step(
                len(steps) + 1, "式(5.2.5)",
                "x/h01>ξb0：以 σs0=(0.8·h01/x−1)·εcu·Es≤fy0 替代 fy0 重新解受压区高度",
                {"ξb0": xi_b0, "σs0_MPa": sigma_s0, "x_mm": x},
                "mm", ["GB50367-2013-5.2.5"],
            )
        )
        clauses_used.add("GB50367-2013-5.2.5")
    else:
        x = x_lin
    steps.append(
        step(
            len(steps) + 1, "式(5.2.3-2)", "α1·fc0·b·x = fy0·As0 + αs·fy·As − f'y0·A's0",
            {"x_mm": x, "αs": ALPHA_S}, "mm", ["GB50367-2013-5.2.3"],
        )
    )

    # ── 步骤3：适用范围检查（式5.2.3-3：2a′ ≤ x ≤ ξb·h0） ──
    infeasible = False
    if x > xi_b * h0:
        warnings.append(
            "受压区高度 x=%.2fmm 超过 ξb·h0=%.2fmm（式5.2.3-3），超筋脆性破坏，"
            "增大截面参数调整无法满足，需增大原截面或提高混凝土强度" % (x, xi_b * h0)
        )
        infeasible = True
    if Asc > 0.0 and x < 2.0 * ap:
        warnings.append(
            "x=%.2fmm < 2a′=%.2fmm（式5.2.3-3）：受压钢筋未达屈服，近似取 x=2a′ 重算承载力" % (x, 2.0 * ap)
        )
        x = 2.0 * ap

    # ── 步骤4：加固后受弯承载力 Mu（式5.2.3-1） ──
    fy0_eff = sigma_s0 if sigma_path else fy
    mu = (
        ALPHA_S * fy2 * As2 * (h0 - x / 2.0)
        + fy0_eff * As * (h01 - x / 2.0)
        + fyp * Asc * (x / 2.0 - ap)
    )
    mu_knm = mu / 1.0e6
    steps.append(
        step(
            len(steps) + 1, "式(5.2.3-1)",
            "Mu = αs·fy·As·(h0−x/2) + fy0·As0·(h01−x/2) + f'y0·A's0·(x/2−a′)",
            {"x_mm": x, "Mu_kNm": mu_knm}, "kN·m", ["GB50367-2013-5.2.3"],
        )
    )

    # ── 三态判定 ──
    if infeasible:
        verdict = "不满足"
    elif M > mu_knm:
        verdict = "需调整"
        warnings.append(
            "新增钢筋量不足：M=%.2fkN·m > Mu=%.2fkN·m，请增大 As2/hf 或提高新增混凝土截面" % (M, mu_knm)
        )
    else:
        verdict = "满足"

    metrics = {"Mu_kNm": mu_knm, "x_mm": x, "xi_b": xi_b, "ratio": M / mu_knm if mu_knm > 0 else None}
    if M0 > 0.0:
        metrics["epsilon_s0"] = eps_s0
        metrics["epsilon_s1"] = eps_s1
    if sigma_path:
        metrics["sigma_s0_MPa"] = sigma_s0

    return build_result(
        "section_enlarge_flexure", params, steps, mu_knm, "kN·m",
        M / mu_knm if mu_knm > 0 else None, "效应比 M/Mu",
        verdict, sorted(clauses_used), warnings, metrics,
    )
