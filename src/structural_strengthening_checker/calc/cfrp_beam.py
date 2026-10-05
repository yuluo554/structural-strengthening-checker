"""碳纤维布加固钢筋混凝土梁正截面受弯承载力验算（GB 50367-2013）。

骨架状态：仅完成模块注册、参数 schema、所需条款声明与门控接入；
计算体（含二次受力/应变滞后路径）在 M2 实装（plan/05 §五）。
required_clauses 已于 M1 按 plan/05 §二核对流程入库为真实 clause_id
（data/knowledge/clauses/gb50367-2013.json，status=已核对）；公式本体
（式10.2.3-1~4 图片形态）在 M2 实装前须以正式出版文本补核。
"""

from __future__ import annotations

from typing import Any, Dict

from ..core.clauses import ClauseStore
from ..core.engine import register_calc


def _pos(unit: str, meaning: str) -> Dict[str, Any]:
    return {"meaning": meaning, "unit": unit, "range": {"min": 0, "exclusive": True}}


def _nonneg(unit: str, meaning: str) -> Dict[str, Any]:
    return {"meaning": meaning, "unit": unit, "range": {"min": 0, "exclusive": False}}


@register_calc(
    module_id="cfrp_beam_flexure",
    name="粘贴碳纤维布加固梁正截面受弯承载力验算",
    description="GB 50367-2013；含二次受力/应变滞后影响（M0>0 激活）。公式与限值待条文核对后 M2 实装。",
    required_clauses=[
        "GB50367-2013-10.2.1",
        "GB50367-2013-10.2.2",
        "GB50367-2013-10.2.3",
        "GB50367-2013-10.2.4",
        "GB50367-2013-10.2.8",
        "GB50367-2013-10.2.10",
        "GB50367-2013-10.2.11",
    ],
    param_schema={
        "b": _pos("mm", "截面宽度"),
        "h": _pos("mm", "截面高度"),
        "fc": _pos("MPa", "混凝土强度"),
        "As": _pos("mm2", "原受拉钢筋截面面积"),
        "fy": _pos("MPa", "原受拉钢筋抗拉强度设计值"),
        "Afe": _pos("mm2", "碳纤维布有效截面面积"),
        "Ecf": _pos("MPa", "碳纤维布弹性模量"),
        "M0": _nonneg("kN·m", "加固前初始弯矩（0=一次受力，>0=二次受力）"),
        "M": _pos("kN·m", "设计弯矩（加固后荷载效应）"),
    },
)
def compute_cfrp_beam_flexure(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    raise NotImplementedError(
        "cfrp_beam_flexure 计算体在 M2 实装（plan/05 §五）；当前骨架仅提供注册与条款门控。"
    )
