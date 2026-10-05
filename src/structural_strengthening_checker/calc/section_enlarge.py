"""增大截面加固法受弯承载力验算（GB 50367-2013）。

骨架状态：同 cfrp_beam——注册 + schema + 门控，计算体 M2 实装。
"""

from __future__ import annotations

from typing import Any, Dict

from ..core.clauses import ClauseStore
from ..core.engine import register_calc
from .cfrp_beam import _nonneg, _pos


@register_calc(
    module_id="section_enlarge_flexure",
    name="增大截面加固法受弯承载力验算",
    description="GB 50367-2013。新旧混凝土协同工作等公式待条文核对后 M2 实装。",
    required_clauses=["GB50367-2013-SECTION-ENLARGE-FLEXURE"],
    param_schema={
        "b": _pos("mm", "原截面宽度"),
        "h": _pos("mm", "原截面高度"),
        "bf": _pos("mm", "新增截面宽度"),
        "hf": _pos("mm", "新增截面高度"),
        "fc": _pos("MPa", "原混凝土强度"),
        "fc2": _pos("MPa", "新混凝土强度"),
        "As": _pos("mm2", "原受拉钢筋截面面积"),
        "fy": _pos("MPa", "原钢筋抗拉强度设计值"),
        "As2": _pos("mm2", "新增受拉钢筋截面面积"),
        "fy2": _pos("MPa", "新增钢筋抗拉强度设计值"),
        "M0": _nonneg("kN·m", "加固前初始弯矩（0=一次受力）"),
        "M": _pos("kN·m", "设计弯矩（加固后荷载效应）"),
    },
)
def compute_section_enlarge_flexure(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    raise NotImplementedError(
        "section_enlarge_flexure 计算体在 M2 实装（plan/05 §五）；当前骨架仅提供注册与条款门控。"
    )
