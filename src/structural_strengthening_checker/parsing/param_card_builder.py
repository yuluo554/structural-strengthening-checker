"""解析层：docx/PDF → 参数卡抽取（规则优先，M3 实装完整版）。

骨架保留 build_param_card 入口签名：输入段落列表，输出空参数卡
（全部结论 = 待人工确认兜底，绝不产生 fail——解析未实装时宁缺勿错）。
"""

from __future__ import annotations

from typing import List

from .docx_text import Para
from .param_card import PlanParamCard


def build_param_card(paras: List[Para], doc_name: str = "", doc_sha256: str = None) -> PlanParamCard:
    """M3 实装规则抽取（正则+槽位）。骨架：仅汇总原文供门控与证据校验。"""
    return PlanParamCard(
        doc_name=doc_name,
        doc_sha256=doc_sha256,
        source_text="\n".join(p.text for p in paras),
    )
