"""核查规则库（RuleStore）：加载 data/knowledge/rules/*.json 并做门控互斥校验。

门控纪律（plan/04 §1.5）：
- 每条规则带 gate.category + gate.only_if_keywords；
- 不同类目的关键词集合必须两两不相交（check_gate_mutex 强制），
  且门控对全部 check_type 生效（含 checklist/conditional 分支——系列项目实测踩坑点）；
- 规则 status 纪律同条款库：limit 依据未核对的规则不得产生 fail 判定（M3 强制，骨架先记录 status）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.errors import SSCError

VALID_CHECK_TYPES = ("param_range", "param_required", "checklist", "consistency")
VALID_SEVERITIES = ("fail", "suspicious", "needs_confirm")


@dataclass
class Rule:
    id: str
    name: str
    category: str
    only_if_keywords: List[str]
    check_type: str
    target: str
    op: Optional[str]
    limit_ref: Optional[str]
    severity: str
    message: str
    advice: str
    clause_id: str
    status: str = "待核对"

    def gate_matches(self, text: str) -> bool:
        if not self.only_if_keywords:
            return True
        return any(kw in text for kw in self.only_if_keywords)


@dataclass
class GateConflict:
    keyword: str
    categories: List[str]


class RuleStore:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.rules: List[Rule] = []
        self.issues: List[str] = []
        self._load_all()

    def _load_all(self) -> None:
        rules_dir = self.knowledge_dir / "rules"
        if not rules_dir.is_dir():
            self.issues.append(f"规则目录不存在: {rules_dir}")
            return
        seen_ids = set()
        for path in sorted(rules_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for i, item in enumerate(items):
                rule = self._parse_rule(item, f"{path.name}[{i}]")
                if rule is None:
                    continue
                if rule.id in seen_ids:
                    self.issues.append(f"{path.name}[{i}]: 规则 id 重复 {rule.id}")
                    continue
                seen_ids.add(rule.id)
                self.rules.append(rule)

    def _parse_rule(self, item: Dict[str, Any], locator: str) -> Optional[Rule]:
        for key in ("id", "name", "gate", "check_type", "severity", "message", "clause_id"):
            if key not in item:
                self.issues.append(f"{locator}: 缺少必填字段 {key}")
                return None
        gate = item.get("gate") or {}
        category = gate.get("category")
        keywords = list(gate.get("only_if_keywords") or [])
        if not category or not keywords:
            self.issues.append(f"{locator}: gate.category / gate.only_if_keywords 必填")
            return None
        if item["check_type"] not in VALID_CHECK_TYPES:
            self.issues.append(f"{locator}: 非法 check_type {item['check_type']!r}")
            return None
        if item["severity"] not in VALID_SEVERITIES:
            self.issues.append(f"{locator}: 非法 severity {item['severity']!r}")
            return None
        return Rule(
            id=item["id"],
            name=item["name"],
            category=category,
            only_if_keywords=keywords,
            check_type=item["check_type"],
            target=item.get("target", ""),
            op=item.get("op"),
            limit_ref=item.get("limit_ref"),
            severity=item["severity"],
            message=item["message"],
            advice=item.get("advice", ""),
            clause_id=item["clause_id"],
            status=item.get("status", "待核对"),
        )

    def check_gate_mutex(self) -> List[GateConflict]:
        """不同类目关键词必须互斥；同关键词出现在多个类目即冲突。"""
        kw_map: Dict[str, List[str]] = {}
        for rule in self.rules:
            for kw in rule.only_if_keywords:
                kw_map.setdefault(kw, [])
                if rule.category not in kw_map[kw]:
                    kw_map[kw].append(rule.category)
        return [
            GateConflict(keyword=kw, categories=sorted(cats))
            for kw, cats in sorted(kw_map.items())
            if len(cats) > 1
        ]

    def active_rules(self, text: str) -> List[Rule]:
        return [r for r in self.rules if r.gate_matches(text)]

    def status_summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.rules),
            "verified": sum(1 for r in self.rules if r.status == "已核对"),
            "issues": list(self.issues),
        }
