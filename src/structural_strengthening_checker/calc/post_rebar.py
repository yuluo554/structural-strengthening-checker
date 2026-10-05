"""植筋锚固深度验算（GB 50367-2013 / JGJ 145-2013）。

骨架状态：注册 + schema + 门控；计算体 M2 实装。
两本规范的条款适用选择（GB 50367 或 JGJ 145）是 M2 的设计点之一。
"""

from __future__ import annotations

from typing import Any, Dict

from ..core.clauses import ClauseStore
from ..core.engine import register_calc
from .cfrp_beam import _pos


@register_calc(
    module_id="post_rebar_anchor",
    name="植筋锚固深度验算",
    description="GB 50367-2013 / JGJ 145-2013。基准锚固深度与修正项待条文核对后 M2 实装。",
    required_clauses=[
        "GB50367-2013-15.2.1",
        "GB50367-2013-15.2.2",
        "GB50367-2013-15.2.3",
        "GB50367-2013-15.2.4",
        "GB50367-2013-15.2.5",
        "GB50367-2013-15.2.6",
    ],
    param_schema={
        "fc": _pos("MPa", "基材混凝土强度"),
        "fy": _pos("MPa", "植筋抗拉强度设计值"),
        "d": _pos("mm", "植筋直径"),
        "ld": _pos("mm", "提供的锚固深度"),
    },
)
def compute_post_rebar_anchor(params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    raise NotImplementedError(
        "post_rebar_anchor 计算体在 M2 实装（plan/05 §五）；当前骨架仅提供注册与条款门控。"
    )
