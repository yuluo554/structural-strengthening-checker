"""方案参数卡（PlanParamCard）：解析层与核查层之间的统一中间表示（plan/04 §1.4）。

纪律：每个抽取值必须带 evidence；quote 非原文子串 → 该项降级 needs_confirm（防幻觉）。
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
    anchor_depths: List[ValueItem] = field(default_factory=list)  # kind=构件名
    unloading: List[ValueItem] = field(default_factory=list)  # kind=卸载|支撑
    crack_repairs: List[ValueItem] = field(default_factory=list)  # kind=修补方式
    appraisal_first: Optional[Evidence] = None  # "先鉴定后加固"环节证据；None=未见

    def full_text(self) -> str:
        """门控匹配用文本：全部证据原文摘录 + 方法名拼接。"""
        parts = [self.source_text]
        parts.extend(m.name for m in self.methods)
        return "\n".join(p for p in parts if p)

    def evidence_issues(self) -> List[str]:
        """证据子串校验：quote 不是原文子串的项列出位置描述（调用方降级 needs_confirm）。"""
        issues: List[str] = []
        quote_fields = [
            ("methods", m.name, m.evidence.quote) for m in self.methods
        ]
        for name, _, quote in quote_fields:
            if quote and quote not in self.source_text:
                issues.append(f"methods[{name}]: 摘录不是原文子串")
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
            "unloading": _conv(self.unloading),
            "crack_repairs": _conv(self.crack_repairs),
            "appraisal_first": self.appraisal_first.to_dict() if self.appraisal_first else None,
        }
