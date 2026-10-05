"""GB 55021-2021 全文强制条款检查单（M3 实装交互核对）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

VALID_OPTIONS = ("符合", "不符合", "不适用", "待确认")


@dataclass
class ChecklistItem:
    item_id: str
    clause_no: str
    gist: str
    check_mode: str  # manual | auto_text
    options: List[str] = field(default_factory=lambda: list(VALID_OPTIONS))
    keywords: List[str] = field(default_factory=list)
    advice: str = ""
    status: str = "待核对"


class ChecklistStore:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = Path(knowledge_dir)
        self.items: List[ChecklistItem] = []
        self.issues: List[str] = []
        self._load_all()

    def _load_all(self) -> None:
        path = self.knowledge_dir / "checklist_gb55021.json"
        if not path.is_file():
            self.issues.append(f"检查单文件不存在: {path}")
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for i, item in enumerate(items):
            if not item.get("item_id") or not item.get("gist"):
                self.issues.append(f"checklist_gb55021.json[{i}]: 缺少 item_id/gist")
                continue
            self.items.append(
                ChecklistItem(
                    item_id=item["item_id"],
                    clause_no=item.get("clause_no", ""),
                    gist=item["gist"],
                    check_mode=item.get("check_mode", "manual"),
                    options=list(item.get("options") or VALID_OPTIONS),
                    keywords=list(item.get("keywords") or []),
                    advice=item.get("advice", ""),
                    status=item.get("status", "待核对"),
                )
            )

    def status_summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.items),
            "verified": sum(1 for i in self.items if i.status == "已核对"),
            "issues": list(self.issues),
        }
