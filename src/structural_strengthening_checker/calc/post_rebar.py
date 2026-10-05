"""植筋锚固深度验算（GB 50367-2013 §15.2，已全部以正式出版文本核对）。

M2 实装（公式形态与表值 2026-10-05 以正式出版文本扫描件核对，记录见
data/cases/workings/formula_verification_M2.md；式(15.2.2-1/-2)+ψae=印刷页 128、
式(15.2.3)+表15.2.3+表15.2.4=印刷页 129、式(15.2.5)=印刷页 130）：
- 式(15.2.2-2)：ld ≥ ψN·ψae·ls（终判组合式，M1 熔断项已解除）；
- 式(15.2.3)：ls = 0.2·αspt·d·fy/fbd；
- 式(15.2.5)：ψN = ψbr·ψw·ψT；
- 式(15.2.4)：基材>C30 且快固型胶粘剂时 fbd 乘 0.8（表15.2.4 为强制性条文取值）。

αspt/fbd 两条输入路径：
- 直接给定（场景系数，M1 三例口径）；
- 查表路径：cover/stirrup_dia → 表15.2.3 查 αspt；adhesive_grade/s1/s2/fc_grade →
  表15.2.4 查 fbd（两表均已核对，代码表值与条款库 JSON 由测试锁死一致）。
ψae 不自动取值（需抗震设防烈度/场地条件输入），缺省 1.00 并附提示。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.clauses import ClauseStore
from ..core.errors import ValidationError
from ..core.engine import register_calc
from .common import (
    FBD_FAST_CURE_FACTOR,
    PSI_AE_DEFAULT,
    alpha_spt_from_table,
    build_result,
    fbd_from_table,
    step,
)
from .cfrp_beam import _nonneg, _opt_nonneg, _opt_pos, _pos


@register_calc(
    module_id="post_rebar_anchor",
    name="植筋锚固深度验算",
    description="GB 50367-2013 式(15.2.2-2)/式(15.2.3)/式(15.2.5)；终判 ld ≥ ψN·ψae·ls。"
    "αspt/fbd 可直接给定或走查表路径（cover+stirrup_dia / adhesive_grade+s1+s2+fc_grade）。",
    required_clauses=[
        "GB50367-2013-15.2.1",
        "GB50367-2013-15.2.2",
        "GB50367-2013-15.2.3",
        "GB50367-2013-15.2.4",
        "GB50367-2013-15.2.5",
        "GB50367-2013-15.2.6",
    ],
    param_schema={
        "fc": _pos("MPa", "基材混凝土轴心抗压强度设计值（快固型调整按基材等级>C30 判定）"),
        "fy": _pos("MPa", "植筋用钢筋抗拉强度设计值"),
        "d": _pos("mm", "植筋公称直径"),
        "ld": _pos("mm", "提供的植筋锚固深度设计值"),
        "alpha_spt": _opt_pos("-", "劈裂影响计算系数 αspt（直接给定；与查表路径互斥）"),
        "fbd": _opt_pos("MPa", "胶粘剂粘结抗剪强度设计值（直接给定；与查表路径互斥）"),
        "cover": _opt_pos("mm", "混凝土保护层厚度 c（查表15.2.3 路径）"),
        "stirrup_dia": _opt_pos("mm", "箍筋直径（查表15.2.3 路径；锚固深度范围内间距不应大于 100mm）"),
        "adhesive_grade": _opt_nonneg("-", "胶粘剂等级 1=A 级 / 2=B 级（查表15.2.4 路径）"),
        "s1": _opt_pos("mm", "植筋间距 s1（查表15.2.4 路径）"),
        "s2": _opt_pos("mm", "植筋边距 s2（查表15.2.4 路径）"),
        "fc_grade": _opt_nonneg("-", "基材混凝土强度等级代码（查表15.2.4 路径：20/25/30/40/60→C20~C60）"),
        "psi_br": _opt_pos("-", "构件受力状态影响系数（1.50 悬挑 / 1.15 非悬挑重要构件接长 / 1.00 其他；默认 1.00）"),
        "psi_w": _opt_pos("-", "孔壁潮湿影响系数（耐潮湿型按产品说明书且 ≥1.1；默认 1.1）"),
        "psi_T": _opt_pos("-", "使用环境温度影响系数（T≤60℃ 取 1.0；默认 1.0）"),
        "psi_ae": _opt_pos("-", "位移延性要求修正系数（抗震设防区按 15.2.2 取 1.10/1.25；默认 1.00）"),
        "fast_cure": _opt_nonneg("-", "快固型胶粘剂（1=是，0=否；基材>C30 时 fbd×0.8）"),
    },
)
def compute_post_rebar_anchor(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    warnings: List[str] = []
    fc, fy, d, ld = params["fc"], params["fy"], params["d"], params["ld"]

    # ── αspt：直接给定 或 查表15.2.3 ──
    alpha_spt = params.get("alpha_spt")
    has_table_aspt = params.get("cover") is not None or params.get("stirrup_dia") is not None
    if alpha_spt is not None and has_table_aspt:
        raise ValidationError("alpha_spt 与查表路径（cover/stirrup_dia）互斥，只能二选一")
    if alpha_spt is None:
        if params.get("cover") is None or params.get("stirrup_dia") is None:
            raise ValidationError("缺少 alpha_spt：请直接给定，或同时提供 cover 与 stirrup_dia 走表15.2.3 查表路径")
        alpha_spt, tw = alpha_spt_from_table(params["cover"], params["stirrup_dia"], d)
        warnings.extend(tw)

    # ── fbd：直接给定 或 查表15.2.4 ──
    fbd = params.get("fbd")
    has_table_fbd = params.get("adhesive_grade") is not None or params.get("s1") is not None
    if fbd is not None and has_table_fbd:
        raise ValidationError("fbd 与查表路径（adhesive_grade/s1/s2/fc_grade）互斥，只能二选一")
    if fbd is None:
        need = ("adhesive_grade", "s1", "s2", "fc_grade")
        if any(params.get(k) is None for k in need):
            raise ValidationError(
                "缺少 fbd：请直接给定，或同时提供 adhesive_grade/s1/s2/fc_grade 走表15.2.4 查表路径"
            )
        grade_code = int(params["adhesive_grade"])
        if grade_code not in (1, 2):
            raise ValidationError("adhesive_grade 仅支持 1（A 级胶）或 2（B 级胶）")
        fcg = int(params["fc_grade"])
        if fcg not in (20, 25, 30, 40, 60):
            raise ValidationError("fc_grade 仅支持表15.2.4 列值: 20/25/30/40/60（≥C60 记 60）")
        fbd, tw = fbd_from_table(
            "A" if grade_code == 1 else "B", params["s1"], params["s2"], d, "C%d" % fcg
        )
        warnings.extend(tw)

    # ── 修正系数 ──
    psi_br = params.get("psi_br", 1.0)
    psi_w = params.get("psi_w", 1.1)
    psi_T = params.get("psi_T", 1.0)
    psi_ae = params.get("psi_ae", PSI_AE_DEFAULT)
    if "psi_br" not in params:
        warnings.append("psi_br 未提供，默认 1.00（其他构件）；悬挑结构构件必须取 1.50、非悬挑重要构件接长取 1.15")
    if "psi_w" not in params:
        warnings.append("psi_w 未提供，默认 1.1（耐潮湿型胶粘剂下限）")
    if "psi_T" not in params:
        warnings.append("psi_T 未提供，默认 1.0（使用环境温度 T≤60℃）")
    if "psi_ae" not in params:
        warnings.append(
            "psi_ae 未提供，默认 1.00（非抗震设防区或基材高于 C30）；"
            "抗震设防区按第15.2.2条：基材≤C30 时 6 度区及 7 度区一、二类场地取 1.10，"
            "7 度区三、四类场地及 8 度区取 1.25"
        )

    steps = []
    clauses_used = {
        "GB50367-2013-15.2.2",
        "GB50367-2013-15.2.3",
        "GB50367-2013-15.2.4",
        "GB50367-2013-15.2.5",
    }

    # ── 步骤1：fbd 快固型调整（式15.2.4，按基材强度等级>C30 判定） ──
    fbd_used = fbd
    fc_grade = params.get("fc_grade")
    if params.get("fast_cure"):
        if fc_grade is not None and int(fc_grade) > 30:
            fbd_used = FBD_FAST_CURE_FACTOR * fbd
            warnings.append(
                "基材混凝土强度等级大于 C30 且采用快固型胶粘剂，fbd 乘调整系数 0.8（第15.2.4条）"
            )
        elif fc_grade is None:
            warnings.append(
                "声明了快固型胶粘剂但未提供 fc_grade，无法判定基材是否大于 C30，"
                "未做 fbd×0.8 调整（如基材>C30，直接给定 fbd 时应自行折减后提供）"
            )
    steps.append(
        step(
            1, "第15.2.4条（表15.2.4）", "fbd 取值（快固型且基材等级>C30 时 ×0.8）",
            {"fbd_MPa": fbd, "fbd_used_MPa": fbd_used, "快固型": bool(params.get("fast_cure"))},
            "MPa", ["GB50367-2013-15.2.4"],
        )
    )

    # ── 步骤2：基本锚固深度 ls（式15.2.3） ──
    ls = 0.2 * alpha_spt * d * fy / fbd_used
    steps.append(
        step(
            2, "式(15.2.3)", "ls = 0.2·αspt·d·fy/fbd",
            {"αspt": alpha_spt, "d_mm": d, "fy_MPa": fy, "fbd_MPa": fbd_used, "ls_mm": ls},
            "mm", ["GB50367-2013-15.2.3"],
        )
    )

    # ── 步骤3：锚固深度修正系数 ψN（式15.2.5） ──
    psi_n = psi_br * psi_w * psi_T
    steps.append(
        step(
            3, "式(15.2.5)", "ψN = ψbr·ψw·ψT",
            {"ψbr": psi_br, "ψw": psi_w, "ψT": psi_T, "ψN": psi_n},
            None, ["GB50367-2013-15.2.5"],
        )
    )

    # ── 步骤4：锚固深度设计值终判（式15.2.2-2：ld ≥ ψN·ψae·ls） ──
    ld_req = psi_n * psi_ae * ls
    steps.append(
        step(
            4, "式(15.2.2-2)", "ld ≥ ψN·ψae·ls",
            {"ψN": psi_n, "ψae": psi_ae, "ls_mm": ls, "ld_req_mm": ld_req, "ld_mm": ld},
            "mm", ["GB50367-2013-15.2.2"],
        )
    )

    verdict = "满足" if ld >= ld_req else "需调整"
    if verdict == "需调整":
        warnings.append(
            "锚固深度不足：ld=%.2fmm < ψN·ψae·ls=%.2fmm（式15.2.2-2），请加大锚固深度" % (ld, ld_req)
        )

    metrics = {
        "ls_mm": ls,
        "psi_N": psi_n,
        "ld_required_mm": ld_req,
        "alpha_spt": alpha_spt,
        "fbd_used_MPa": fbd_used,
        "ratio": ld / ld_req,
    }
    return build_result(
        "post_rebar_anchor", params, steps, ld_req, "mm",
        ld / ld_req, "提供锚固深度/所需锚固深度 ld/(ψN·ψae·ls)",
        verdict, sorted(clauses_used), warnings, metrics,
    )
