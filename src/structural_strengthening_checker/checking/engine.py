"""核查引擎：参数卡 × 规则库 → 三级判定报告（M3 实装判定逻辑）。

骨架已实现的确定性行为：
- 类目门控过滤（only_if_keywords 不命中的规则不激活）；
- 兜底纪律：解析未实装/证据不足时一律 needs_confirm，绝不产生 fail（宁缺勿错）；
- 结论必须挂依据条款（clause_id）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..core.clauses import ClauseStore
from ..parsing.param_card import PlanParamCard
from .rules import RuleStore

VERDICT_FAIL = "fail"
VERDICT_SUSPICIOUS = "suspicious"
VERDICT_NEEDS_CONFIRM = "needs_confirm"
VERDICT_PASS = "pass"


@dataclass
class CheckFinding:
    rule_id: str
    rule_name: str
    verdict: str
    message: str
    clause_id: str
    advice: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckReport:
    doc_name: str
    findings: List[CheckFinding] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"fail": 0, "suspicious": 0, "needs_confirm": 0, "pass": 0}
        for f in self.findings:
            counts[f.verdict] = counts.get(f.verdict, 0) + 1
        return counts


def check_plan(card: PlanParamCard, rules: RuleStore, store: ClauseStore) -> CheckReport:
    """骨架：门控激活的规则全部输出 needs_confirm（判定逻辑 M3 实装）。"""
    report = CheckReport(doc_name=card.doc_name)
    for rule in rules.active_rules(card.full_text()):
        report.findings.append(
            CheckFinding(
                rule_id=rule.id,
                rule_name=rule.name,
                verdict=VERDICT_NEEDS_CONFIRM,
                message=f"{rule.message}（核查判定 M3 实装；规则 status={rule.status}）",
                clause_id=rule.clause_id,
                advice=rule.advice,
            )
        )
    return report
