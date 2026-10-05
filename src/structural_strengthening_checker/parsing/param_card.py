"""方案参数卡（PlanParamCard）：解析层与核查层之间的统一中间表示（plan/04 §1.4）。

纪律：每个抽取值必须带 evidence；quote 非原文子串 → 该项丢弃并计入 needs_confirm（防幻觉，FR-B5）。

M3 实装增补（plan/06 决策表）：
- ValueItem 增加 label 字段（牌号/等级等原文字符串，value 保留数值部分）；
- 新增 design_params 槽位：植筋锚固筛查用的设计参数（直径/牌号/混凝土强度等级/胶粘剂等级/
  钢筋强度设计值），与 materials（材料等级总表）分列，避免把设计参数混进材料清单。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    page: Optional[int] = None
    para: Optional[int] = None
    quote: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MethodItem:
    name: str
    evidence: Evidence = field(default_factory=Evidence)


@dataclass
class ValueItem:
    kind: str
    value: Optional[float] = None
    unit: Optional[str] = None
    label: Optional[str] = None  # 原文字符串（牌号/等级/构件名/方式名）
    confidence: float = 0.0
    evidence: Evidence = field(default_factory=Evidence)


@dataclass
class PlanParamCard:
    doc_name: str = ""
    doc_sha256: Optional[str] = None
    source_text: str = ""  # 方案原文全文（证据子串校验基准）
    methods: List[MethodItem] = field(default_factory=list)
    materials: List[ValueItem] = field(default_factory=list)  # kind=混凝土|钢材|碳纤维|胶粘剂
    adhesive_indices: List[ValueItem] = field(default_factory=list)  # kind=指标名
    anchor_depths: List[ValueItem] = field(default_factory=list)  # kind=构件名(label)，value=深度mm
    design_params: List[ValueItem] = field(default_factory=list)  # kind=植筋直径|钢筋牌号|混凝土强度等级|胶粘剂等级|钢筋强度设计值
    unloading: List[ValueItem] = field(default_factory=list)  # kind=卸载|支撑
    crack_repairs: List[ValueItem] = field(default_factory=list)  # kind=修补方式
    appraisal_first: Optional[Evidence] = None  # "先鉴定后加固"环节证据；None=未见
    notes: List[str] = field(default_factory=list)  # 抽取留痕（丢弃项/降级原因，FR-B5 审计）

    def full_text(self) -> str:
        """门控匹配用文本：全部证据原文摘录 + 方法名拼接。"""
        parts = [self.source_text]
        parts.extend(m.name for m in self.methods)
        return "\n".join(p for p in parts if p)

    def _all_quoted(self) -> List[Any]:
        items: List[Any] = list(self.methods)
        items.extend(self.materials)
        items.extend(self.adhesive_indices)
        items.extend(self.anchor_depths)
        items.extend(self.design_params)
        items.extend(self.unloading)
        items.extend(self.crack_repairs)
        return items

    def evidence_issues(self) -> List[str]:
        """证据子串校验：quote 不是原文子串的项列出位置描述（防幻觉总闸，M3 覆盖全部槽位）。"""
        issues: List[str] = []
        for item in self._all_quoted():
            quote = getattr(item, "evidence", None) and item.evidence.quote
            if quote and quote not in self.source_text:
                name = getattr(item, "name", None) or getattr(item, "kind", "?")
                issues.append(f"{type(item).__name__}[{name}]: 摘录不是原文子串")
        if self.appraisal_first and self.appraisal_first.quote:
            if self.appraisal_first.quote not in self.source_text:
                issues.append("appraisal_first: 摘录不是原文子串")
        return issues

    def to_dict(self) -> Dict[str, Any]:
        def _conv(items: List[ValueItem]) -> List[Dict[str, Any]]:
            return [
                {**{k: v for k, v in asdict(i).items() if k != "evidence"},
                 "evidence": i.evidence.to_dict()}
                for i in items
            ]

        return {
            "doc": {"name": self.doc_name, "sha256": self.doc_sha256},
            "methods": [
                {"name": m.name, "evidence": m.evidence.to_dict()} for m in self.methods
            ],
            "materials": _conv(self.materials),
            "adhesive_indices": _conv(self.adhesive_indices),
            "anchor_depths": _conv(self.anchor_depths),
            "design_params": _conv(self.design_params),
            "unloading": _conv(self.unloading),
            "crack_repairs": _conv(self.crack_repairs),
            "appraisal_first": self.appraisal_first.to_dict() if self.appraisal_first else None,
            "notes": list(self.notes),
        }
