"""M2 公式引擎共享层：已核对公式/表值的唯一代码出处（stdlib only）。

纪律（plan/05 §二、HANDOFF-M2 §三）：
- 本模块内所有系数/表值均来自已核对条款（data/knowledge/clauses/gb50367-2013.json），
  逐项挂条号；表值以正式出版文本扫描件核对（2026-10-05，核对记录见
  data/cases/workings/formula_verification_M2.md）；
- 代码表值与条款库 JSON 由测试锁死一致（tests/test_calc_modules.py::test_code_tables_match_clause_json）；
- 未核对渠道的值一律不得出现在本模块（熔断纪律）。

三态判定口径（plan/04 §1.3，M2 定稿）：
- 满足：加固后承载力/锚固深度 ≥ 需求，且全部构造与限值检查通过；
- 需调整：可通过调整本方法设计参数达标（加固量/新增钢筋量/锚固深度不足或过大、
  提高幅度超限等），结论附调整方向；
- 不满足：在本方法的可行域内无法达标（如受弯加固 x 超出 ξb,f·h0 超筋限值），
  需更换加固方法或加大原截面。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 已核对常数与表值（出处逐项标注）
# ---------------------------------------------------------------------------

EPS_CU = 0.0033  # 混凝土极限压应变（GB 50367-2013 式10.2.3/9.2.3/5.2.4 符号说明，已核对）

# 表10.2.8 计算系数 αf 值 / 表9.2.9 计算系数 αsp 值（两表数值相同，已核对：
# 印刷页 79 / 印刷页 65，正式出版文本扫描件）。ρte 表列分档点；首列 ≤0.007，末列 ≥0.060。
ALPHA_F_RHO_TE_BANDS = (0.007, 0.010, 0.020, 0.030, 0.040, 0.060)
ALPHA_F_SINGLE_ROW = (0.70, 0.90, 1.15, 1.20, 1.25, 1.30)  # 单排钢筋
ALPHA_F_DOUBLE_ROW = (0.75, 1.00, 1.25, 1.30, 1.35, 1.40)  # 双排钢筋
ALPHA_F_ADJUST = 0.9  # σs0≤150MPa 且 ρte≤0.05 时可乘的调整系数（表注 2）

# 表15.2.3 考虑混凝土劈裂影响的计算系数 αspt（印刷页 129，已核对）。
# 列 = 保护层厚度 c 与箍筋直径组合（c=25:φ6 / c=25:φ8或10 / c=30:φ6 / c=30:φ8或10 /
# c=35:≥6 / c≥40:≥6）；行 = 植筋直径 d（≤20 / 25 / 32，表注：介于表列值之间按线性内插）。
ALPHA_SPT_COLUMNS = ("c25_f6", "c25_f810", "c30_f6", "c30_f810", "c35_ge6", "c40_ge6")
ALPHA_SPT_ROWS = {
    "le20": (1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    "d25": (1.10, 1.05, 1.05, 1.00, 1.00, 1.00),
    "d32": (1.25, 1.15, 1.15, 1.10, 1.10, 1.05),
}

# 表15.2.4 粘结抗剪强度设计值 fbd（N/mm²，印刷页 129，已核对；强制性条文 15.2.4）。
# 行 = 胶粘剂等级与构造条件；列 = 基材混凝土强度等级。
FBD_TABLE = (
    {"grade": ("A", "B"), "cond": "s1>=5d;s2>=2.5d", "values": {"C20": 2.3, "C25": 2.7, "C30": 3.7, "C40": 4.0, "C60": 4.5}},
    {"grade": ("A",), "cond": "s1>=6d;s2>=3.0d", "values": {"C20": 2.3, "C25": 2.7, "C30": 4.0, "C40": 4.5, "C60": 5.0}},
    {"grade": ("A",), "cond": "s1>=7d;s2>=3.5d", "values": {"C20": 2.3, "C25": 2.7, "C30": 4.5, "C40": 5.0, "C60": 5.5}},
)
FBD_FAST_CURE_FACTOR = 0.8  # 基材>C30 且快固型胶粘剂时 fbd 乘 0.8（15.2.4 条文，已核对）

# 式(15.2.2-2)：ld ≥ ψN·ψae·ls；ψae 离散取值（15.2.2 条文，已核对）。
PSI_AE_DEFAULT = 1.00  # 非抗震设防区 / 基材高于 C30（用户未提供时的默认，附 warning）

# 表4.3.4-1 碳纤维复合材抗拉强度设计值 ff（MPa，印刷页 14，已核对）：
# {（品种, 等级, 形态, 结构类别）: ff}；仅列常用于梁底加固的碳纤维行。
FF_CFRP_TABLE = {
    ("carbon", "I", "fabric", "important"): 1600.0,
    ("carbon", "I", "fabric", "general"): 2300.0,
    ("carbon", "II", "fabric", "important"): 1400.0,
    ("carbon", "II", "fabric", "general"): 2000.0,
    ("carbon", "III", "fabric", "general"): 1200.0,
    ("carbon", "I", "plate", "important"): 1150.0,
    ("carbon", "I", "plate", "general"): 1600.0,
    ("carbon", "II", "plate", "important"): 1000.0,
    ("carbon", "II", "plate", "general"): 1400.0,
}
# 表4.3.5 纤维复合材弹性模量及拉应变设计值（印刷页 15，已核对）：
# {（品种, 等级, 形态）: (Ef_MPa, εf_重要构件, εf_一般构件)}；仅碳纤维行。
EF_CFRP_TABLE = {
    ("carbon", "I", "fabric"): (2.3e5, 0.007, 0.01),
    ("carbon", "II", "fabric"): (2.0e5, 0.007, 0.01),
    ("carbon", "III", "fabric"): (1.8e5, None, None),
    ("carbon", "I", "plate"): (1.6e5, 0.007, 0.01),
    ("carbon", "II", "plate"): (1.4e5, 0.007, 0.01),
}

CAPACITY_INCREASE_MAX = 0.40  # 受弯承载力提高幅度上限（10.2.10 / 9.2.11，已核对）


# ---------------------------------------------------------------------------
# 通用查表/求解工具
# ---------------------------------------------------------------------------

def lookup_alpha_f(rho_te: float, rebar_rows: int) -> Tuple[float, bool]:
    """查表10.2.8（αf）/表9.2.9（αsp）。

    表列分档点之间的取值规范未注明内插规则，本实现按线性内插处理并在调用侧
    附 warning（实现决策，记录于 formula_verification_M2.md §表值查取）。
    返回 (αf, interpolated)。
    """
    row = ALPHA_F_SINGLE_ROW if rebar_rows <= 1 else ALPHA_F_DOUBLE_ROW
    bands = ALPHA_F_RHO_TE_BANDS
    if rho_te <= bands[0]:
        return row[0], False
    if rho_te >= bands[-1]:
        return row[-1], False
    for i in range(len(bands) - 1):
        lo, hi = bands[i], bands[i + 1]
        if lo <= rho_te <= hi:
            t = (rho_te - lo) / (hi - lo)
            return row[i] + t * (row[i + 1] - row[i]), True
    raise AssertionError("unreachable")


def _alpha_spt_row_key(d: float) -> Tuple[str, bool]:
    """d≤20 取首行；25<d<32 与 20<d<25 表注允许线性内插——返回相邻行键与内插比例。"""
    if d <= 20.0:
        return "le20", 0.0
    if d <= 25.0:
        return "le20", (d - 20.0) / 5.0  # le20 -> d25
    if d <= 32.0:
        return "d25", (d - 25.0) / 7.0  # d25 -> d32
    raise ValueError("表15.2.3 仅覆盖 d≤32（更大直径超出表列范围，请直接给定 alpha_spt）")


def alpha_spt_from_table(cover_mm: float, stirrup_dia: float, d: float) -> Tuple[float, List[str]]:
    """查表15.2.3 求 αspt。

    - d 介于表列值之间：按表注线性内插（已核对表注）；
    - 保护层厚度介于表列列值之间：本实现保守取"不超过实际保护层的最大表列列"
      （更不利、αspt 更大），并附 warning（实现决策，规范未注明 c 向内插规则）。
    返回 (αspt, warnings)。
    """
    warnings: List[str] = []
    row_key, frac = _alpha_spt_row_key(d)
    # 列选择：c 的表列锚点 25/30/35/40；列索引 0/1→c25，2/3→c30，4→c35，5→c≥40。
    # c 介于表列值之间时保守取"更小保护层列"（αspt 更大、锚固更深，偏安全）。
    if cover_mm <= 25.0:
        col = 1 if stirrup_dia >= 8 else 0  # c=25 两列按箍筋直径分
    elif cover_mm < 30.0:
        warnings.append(
            "保护层厚度 %.1fmm 介于表列 25/30 之间，保守取 c=25 列（表15.2.3 未注明 c 向内插规则）" % cover_mm
        )
        col = 1 if stirrup_dia >= 8 else 0
    elif cover_mm <= 30.0:
        col = 3 if stirrup_dia >= 8 else 2
    elif cover_mm < 35.0:
        warnings.append(
            "保护层厚度 %.1fmm 介于表列 30/35 之间，保守取 c=30 列（表15.2.3 未注明 c 向内插规则）" % cover_mm
        )
        col = 3 if stirrup_dia >= 8 else 2
    elif cover_mm <= 35.0:
        col = 4  # c=35 列要求箍筋 ≥6
        if stirrup_dia < 6:
            warnings.append("c=35 列要求箍筋直径 ≥6mm；实际 %.1fmm 超出表列范围，保守取 c=30/φ6 列" % stirrup_dia)
            col = 2
    else:
        col = 5  # c≥40 列要求箍筋 ≥6
        if stirrup_dia < 6:
            warnings.append("c≥40 列要求箍筋直径 ≥6mm；实际 %.1fmm 超出表列范围，保守取 c=35 列" % stirrup_dia)
            col = 4
    lo = ALPHA_SPT_ROWS[row_key][col]
    if frac <= 0.0:
        return lo, warnings
    next_key = "d25" if row_key == "le20" else "d32"
    hi = ALPHA_SPT_ROWS[next_key][col]
    return lo + frac * (hi - lo), warnings


def fbd_from_table(adhesive_grade: str, s1: float, s2: float, d: float, fc_grade: str) -> Tuple[float, List[str]]:
    """查表15.2.4 求 fbd（N/mm²）。s1/s2 为实际间距/边距，按满足的构造条件行选取。

    行选择：从构造条件最严的行向下找第一条"全部满足"的行（条件越严 fbd 越高）；
    B 级胶只允许第一行（A 或 B 级行）。
    """
    warnings: List[str] = []
    grade = adhesive_grade.strip().upper()
    key = fc_grade.strip().upper()
    for row in reversed(FBD_TABLE):  # 最严条件优先
        if grade == "B" and "B" not in row["grade"]:
            continue
        cond = row["cond"]
        need_s1, need_s2 = cond.split(";")
        s1_min = float(need_s1.split(">=")[1].rstrip("d")) * d
        s2_min = float(need_s2.split(">=")[1].rstrip("d")) * d
        if s1 >= s1_min - 1e-9 and s2 >= s2_min - 1e-9:
            if key not in row["values"]:
                raise ValueError("表15.2.4 无该基材强度等级列: %s" % fc_grade)
            return row["values"][key], warnings
    raise ValueError("表15.2.4 无满足的构造条件行（grade=%s, s1=%s, s2=%s, d=%s）" % (grade, s1, s2, d))


def solve_flexure_x(
    a_fc_b: float,
    t_net: float,
    k_coupling: float,
    eps_lag: float,
    h: float,
    f_full: float,
) -> Tuple[float, float]:
    """解粘贴加固正截面 ULS 方程组，返回 (x, psi)。

    统一形式（GB 50367-2013 式(10.2.3-1~3) 与式(9.2.3-1~3) 同构）：
      力平衡:  a_fc_b·x = t_net + psi·k_coupling·(0.8·εcu·h/x − εcu − ε_lag)
      其中 psi = (0.8·εcu·h/x − εcu − ε_lag)/ε_design，psi>1.0 时取 1.0（已核对条文）。
      k_coupling: 纤维布 = ff·Afe/εf；钢板 = Esp·Asp。
      f_full = psi=1.0 时的加固材料拉力设计值（纤维布 ff·Afe；钢板 fp·Asp）。
    未封顶时为 x 的二次方程，解析求解；封顶时力平衡退化为线性。
    """
    b_coef = t_net - k_coupling * (EPS_CU + eps_lag)
    c_coef = 0.8 * k_coupling * EPS_CU * h
    disc = b_coef * b_coef + 4.0 * a_fc_b * c_coef
    x_uncapped = (b_coef + math.sqrt(disc)) / (2.0 * a_fc_b)
    eps_design = f_full / k_coupling
    psi_raw = (0.8 * EPS_CU * h / x_uncapped - EPS_CU - eps_lag) / eps_design
    if psi_raw < 0.0:
        # 中和轴过深导致加固材料应变低于滞后应变：拉力不为负，退化为无加固贡献的力平衡
        return t_net / a_fc_b, 0.0
    if psi_raw <= 1.0:
        return x_uncapped, psi_raw
    x_capped = (t_net + f_full) / a_fc_b
    return x_capped, 1.0


def solve_x_from_moment(a_fc_b: float, m_res: float, h: float) -> Optional[float]:
    """由力矩平衡式（力矩中心取受拉区边缘，加固材料力臂为 0）反算所需受压区高度 x。

    a_fc_b·x·(h − x/2) = m_res  →  x² − 2h·x + 2·m_res/a_fc_b = 0，取较小根。
    m_res 超出截面极限量（h²·a_fc_b/2）时返回 None（本方法不可行）。
    """
    disc = h * h - 2.0 * m_res / a_fc_b
    if disc < 0.0:
        return None
    return h - math.sqrt(disc)


def build_result(
    module_id: str,
    params: Dict[str, Any],
    steps: List[Dict[str, Any]],
    capacity_value: Optional[float],
    capacity_unit: str,
    ratio_value: Optional[float],
    ratio_meaning: str,
    verdict: str,
    clauses_used: List[str],
    warnings: List[str],
    metrics: Dict[str, float],
) -> Dict[str, Any]:
    """组装 CalcResult（plan/04 §1.3 + M2 增补 metrics 字段供基准比对）。"""
    if verdict not in ("满足", "不满足", "需调整"):
        raise ValueError("非法 verdict: %r" % verdict)
    return {
        "module": module_id,
        "inputs": dict(params),
        "steps": steps,
        "capacity": {"value": capacity_value, "unit": capacity_unit},
        "ratio": {"value": ratio_value, "meaning": ratio_meaning},
        "verdict": verdict,
        "clauses_used": clauses_used,
        "warnings": warnings,
        "metrics": metrics,
    }


def step(no: int, formula_ref: str, expr: str, values: Dict[str, Any], unit: Optional[str], clause_ids: List[str]) -> Dict[str, Any]:
    """构造单条计算步骤（逐步骤挂公式编号与依据条款）。"""
    return {
        "no": no,
        "formula_ref": formula_ref,
        "expr": expr,
        "values": values,
        "unit": unit,
        "clause_ids": clause_ids,
    }
