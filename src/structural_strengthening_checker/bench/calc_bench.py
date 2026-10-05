"""内置基准（零 API 依赖，M4 达标）：验算算例通过率 + 方案核查检出率/误报率。

骨架已实现的确定性行为：
- 算例库加载与 schema 守门（case_id/module/input/expected/source 必填，无来源报错）；
- 算例执行走 run_calc 同一门控（M2 前全部 blocked_by_clauses，如实报告不虚报通过率）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..core.clauses import ClauseStore
from ..core.engine import CALC_REGISTRY, run_calc
from ..core.errors import ClauseNotVerifiedError

REQUIRED_CASE_KEYS = ("case_id", "module", "input", "expected", "source")


def load_cases(cases_dir: Path) -> "tuple[List[Dict[str, Any]], List[str]]":
    """加载并校验算例库；缺字段/无来源的算例计入 issues（测试锁死）。"""
    cases: List[Dict[str, Any]] = []
    issues: List[str] = []
    cases_dir = Path(cases_dir)
    if not cases_dir.is_dir():
        return cases, [f"算例目录不存在: {cases_dir}"]  # type: ignore[return-value]
    for path in sorted(cases_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for i, item in enumerate(items):
            locator = f"{path.name}[{i}]"
            missing = [k for k in REQUIRED_CASE_KEYS if not item.get(k)]
            if missing:
                issues.append(f"{locator}: 缺少必填字段 {', '.join(missing)}")
                continue
            if not (item["source"].get("title") or item["source"].get("channel")):
                issues.append(f"{locator}: 算例无来源（无来源数值不得作真值）")
                continue
            cases.append(item)
    return cases, issues


def run_calc_bench(data_dir: Path, store: ClauseStore = None) -> Dict[str, Any]:
    """骨架版验算基准：加载算例 → 逐例尝试 run_calc → 如实统计门控阻塞。"""
    cases, issues = load_cases(Path(data_dir) / "cases")
    result: Dict[str, Any] = {
        "total": len(cases),
        "passed": 0,
        "failed": 0,
        "blocked_by_clauses": 0,
        "issues": issues,
        "details": [],
    }
    if store is None:
        store = ClauseStore(Path(data_dir) / "knowledge")
    for case in cases:
        if case["module"] not in CALC_REGISTRY:
            result["failed"] += 1
            result["details"].append({"case_id": case["case_id"], "error": "未注册模块"})
            continue
        try:
            run_calc(case["module"], case["input"], store)
            # M2 前不可能到达这里（条款未核对必先抛门控）；到达说明缺比对逻辑
            result["failed"] += 1
            result["details"].append({"case_id": case["case_id"], "error": "M4 实装真值比对"})
        except ClauseNotVerifiedError as exc:
            result["blocked_by_clauses"] += 1
            result["details"].append({"case_id": case["case_id"], "blocked": str(exc)})
        except Exception as exc:  # noqa: BLE001  基准不得因单例崩溃
            result["failed"] += 1
            result["details"].append({"case_id": case["case_id"], "error": str(exc)})
    return result
