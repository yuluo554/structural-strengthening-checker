"""条款库（ClauseStore）：机器可读的规范条目库，全部合规判定的唯一出处来源。

schema 见 plan/04 §1.1。入库纪律（引擎级强制）：
- status 取值仅 {"待核对", "已核对"}；
- status=已核对 必须有 source.checked_date 非空（无出处的值不得以确定语气落库）；
- require_verified() 是公式引擎进入计算前的门控（FR-A7）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import ClauseNotVerifiedError

STATUS_PENDING = "待核对"
STATUS_VERIFIED = "已核对"
VALID_STATUS = (STATUS_PENDING, STATUS_VERIFIED)


@dataclass
class Clause:
    clause_id: str
    standard: str
    clause_no: str
    title: str
    gist: str
    status: str = STATUS_PENDING
    excerpt: Optional[str] = None
    formula_ref: Optional[str] = None
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    limits: Dict[str, Any] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


class ClauseStore:
    """加载 data/knowledge/clauses/*.json（每文件单对象或对象数组）。"""

    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self._clauses: Dict[str, Clause] = {}
        self.issues: List[str] = []
        self._load_all()

    # ---------- 加载与校验 ----------

    def _load_all(self) -> None:
        clauses_dir = self.knowledge_dir / "clauses"
        if not clauses_dir.is_dir():
            self.issues.append(f"条款目录不存在: {clauses_dir}")
            return
        for path in sorted(clauses_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for i, item in enumerate(items):
                self._add_entry(item, f"{path.name}[{i}]")

    def _add_entry(self, item: Dict[str, Any], locator: str) -> None:
        for key in ("clause_id", "standard", "clause_no", "title", "gist", "status"):
            if not item.get(key):
                self.issues.append(f"{locator}: 缺少必填字段 {key}")
                return
        if item["status"] not in VALID_STATUS:
            self.issues.append(f"{locator}: 非法 status {item['status']!r}")
            return
        if item["status"] == STATUS_VERIFIED:
            checked_date = (item.get("source") or {}).get("checked_date")
            if not checked_date:
                self.issues.append(
                    f"{locator}: status=已核对 但 source.checked_date 为空（无出处不得落库）"
                )
                return
        clause = Clause(
            clause_id=item["clause_id"],
            standard=item["standard"],
            clause_no=item["clause_no"],
            title=item["title"],
            gist=item["gist"],
            status=item["status"],
            excerpt=item.get("excerpt"),
            formula_ref=item.get("formula_ref"),
            symbols=list(item.get("symbols") or []),
            limits=dict(item.get("limits") or {}),
            source=dict(item.get("source") or {}),
            tags=list(item.get("tags") or []),
        )
        if clause.clause_id in self._clauses:
            self.issues.append(f"{locator}: clause_id 重复 {clause.clause_id}")
            return
        self._clauses[clause.clause_id] = clause

    # ---------- 查询 ----------

    def get(self, clause_id: str) -> Clause:
        if clause_id not in self._clauses:
            raise KeyError(f"条款库中未登记: {clause_id}")
        return self._clauses[clause_id]

    def __contains__(self, clause_id: object) -> bool:
        return clause_id in self._clauses

    def __len__(self) -> int:
        return len(self._clauses)

    def all_clauses(self) -> List[Clause]:
        return list(self._clauses.values())

    def require_verified(self, clause_ids: List[str]) -> None:
        """门控：任一条款未登记或 status=待核对 即抛 ClauseNotVerifiedError。"""
        unregistered = [cid for cid in clause_ids if cid not in self._clauses]
        unverified = [
            cid
            for cid in clause_ids
            if cid in self._clauses and self._clauses[cid].status != STATUS_VERIFIED
        ]
        if unregistered or unverified:
            raise ClauseNotVerifiedError(unverified=unverified, unregistered=unregistered)

    def status_summary(self) -> Dict[str, Any]:
        total = len(self._clauses)
        verified = sum(1 for c in self._clauses.values() if c.status == STATUS_VERIFIED)
        return {
            "total": total,
            "verified": verified,
            "pending": total - verified,
            "issues": list(self.issues),
        }
