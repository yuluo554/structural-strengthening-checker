"""内置基准（零 API 依赖，M4 达标）：验算算例通过率 + 方案核查检出率/误报率。

M2 实装验算真值比对：
- 算例库加载与 schema 守门（case_id/module/input/expected/source 必填，无来源报错）；
- 算例执行走 run_calc 同一门控（未核对条款 → blocked_by_clauses，如实报告不虚报）；
- 真值比对：expected.verdict 严格相等；expected 其余数值键逐项对 result.metrics，
  容差 expected.tolerance（默认 ±0.5%，工程量纲相对容差），口径见 plan/05 §三。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.clauses import ClauseStore
from ..core.engine import CALC_REGISTRY, run_calc
from ..core.errors import ClauseNotVerifiedError

REQUIRED_CASE_KEYS = ("case_id", "module", "input", "expected", "source")
DEFAULT_TOLERANCE = 0.005
# expected 内不作数值比对的元数据键（verdict 单独严格比对）
NON_NUMERIC_KEYS = frozenset({"tolerance", "note", "verdict"})


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


def compare_case(case: Dict[str, Any], result: Dict[str, Any]) -> List[str]:
    """真值比对（±tolerance 相对容差；verdict 严格相等）。返回问题列表（空=通过）。"""
    expected = case.get("expected") or {}
    problems: List[str] = []
    tol = float(expected.get("tolerance", DEFAULT_TOLERANCE))
    exp_verdict = expected.get("verdict")
    if exp_verdict is not None and result["verdict"] != exp_verdict:
        problems.append(f"verdict 期望 {exp_verdict!r} 实得 {result['verdict']!r}")
    metrics = result.get("metrics") or {}
    for key, want in expected.items():
        if key in NON_NUMERIC_KEYS:
            continue
        if key not in metrics:
            problems.append(
                f"真值引用的指标 {key!r} 不在结果 metrics 中（可用: {sorted(metrics)}）"
            )
            continue
        got = metrics[key]
        if got is None or abs(float(got) - float(want)) > tol * max(abs(float(want)), 1e-9):
            problems.append(f"{key} 期望 {want} 实得 {got}（容差 ±{tol:.2%}）")
    return problems


def run_calc_bench(data_dir: Path, store: Optional[ClauseStore] = None) -> Dict[str, Any]:
    """验算基准：加载算例 → 逐例 run_calc（同门控）→ 真值比对 → 如实统计。"""
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
            calc_result = run_calc(case["module"], case["input"], store)
        except ClauseNotVerifiedError as exc:
            result["blocked_by_clauses"] += 1
            result["details"].append({"case_id": case["case_id"], "blocked": str(exc)})
            continue
        except Exception as exc:  # noqa: BLE001  基准不得因单例崩溃
            result["failed"] += 1
            result["details"].append({"case_id": case["case_id"], "error": str(exc)})
            continue
        problems = compare_case(case, calc_result)
        if problems:
            result["failed"] += 1
            result["details"].append(
                {"case_id": case["case_id"], "verdict": calc_result["verdict"], "problems": problems}
            )
        else:
            result["passed"] += 1
            result["details"].append(
                {"case_id": case["case_id"], "verdict": calc_result["verdict"], "ok": True}
            )
    return result
