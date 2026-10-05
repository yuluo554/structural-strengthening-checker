"""方案核查基准（M4 实装）：现场生成合成语料 → 逐份核查 → 与 truth 对账 → 指标与门槛。

对账口径（与 M3 端到端一致，plan/05 §四真值语义，改口径=改基准）：
- 期望集合 = truth.expected_non_pass ∪ 该文档全部 injected[].also_expect（v1 恒空，语义保留）；
- 报告集合 = CheckReport.non_pass_rule_ids()（文档全部非 pass 结论，与顺序无关）；
- 多报期望之外的问题算误报（含 EVIDENCE 级证据问题），误报 0 是硬门槛。

指标定义（M4 定稿，plan/06 决策表）：
- 检出率 detection_rate = Σ检出 / Σ期望（按规则实例聚合；基线文档期望为 0，不计入分母）；
- 误报数 false_positives = Σ(报告集合 − 期望集合)；
- 判定准确率 verdict_accuracy = 主期望匹配数 / 注入项总数
  （injected[].expected_verdict 与该 rule_id 在报告中的最重 verdict 严格相等，
  最重 verdict 由 checking.engine.worst_verdict 定义）。

门槛（DoD：指标不达 → 回修不放宽门槛；测试断言锁死这些常量）：
- REQUIRED_DETECTION_RATE = 1.0（全部注入检出）
- MAX_FALSE_POSITIVES = 0（含基线 0 误报）
- REQUIRED_VERDICT_ACCURACY = 1.0

现场生成纪律（M4）：语料由 gen_plan.generate 现场生成（seed 固定，不背产物）；
需 python-docx（extras report/dev），缺失抛 MissingExtraError 由 CLI 友好降级。
生成后逐份校验 docx sha256 与 truth 一致（防生成器/产物漂移）。
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..checking.engine import check_plan, worst_verdict
from ..checking.rules import RuleStore
from ..core.clauses import ClauseStore
from ..core.errors import SSCError
from ..datagen.gen_plan import DEFAULT_SEED
from ..parsing.docx_text import extract_paras
from ..parsing.param_card_builder import build_param_card

# ── 指标门槛（既定口径：改这里=改基准，必须同步测试断言与 README 指标表）──
REQUIRED_DETECTION_RATE = 1.0
MAX_FALSE_POSITIVES = 0
REQUIRED_VERDICT_ACCURACY = 1.0


def _verdicts_by_rule(report) -> Dict[str, str]:
    """报告内每个 rule_id 的最重 verdict（判定准确率对账用）。"""
    acc: Dict[str, List[str]] = {}
    for f in report.findings:
        acc.setdefault(f.rule_id, []).append(f.verdict)
    return {rid: worst_verdict(vs) for rid, vs in acc.items()}


def reconcile_doc(truth_doc: Dict[str, Any], report) -> Dict[str, Any]:
    """单文档对账：truth 期望集合 vs 报告非 pass 集合 + 注入项主期望判定比对。"""
    expected: List[str] = list(truth_doc.get("expected_non_pass") or [])
    injected = list(truth_doc.get("injected") or [])
    for inj in injected:
        for extra in inj.get("also_expect") or []:
            if extra not in expected:
                expected.append(extra)
    got = list(report.non_pass_rule_ids())
    verdict_by_rule = _verdicts_by_rule(report)

    detected = [r for r in expected if r in got]
    missed = [r for r in expected if r not in got]
    false_positives = [r for r in got if r not in expected]
    verdict_matches: List[str] = []
    verdict_mismatches: List[Dict[str, str]] = []
    for inj in injected:
        rid = inj["rule_id"]
        want = inj.get("expected_verdict")
        got_v = verdict_by_rule.get(rid)
        if got_v == want:
            verdict_matches.append(rid)
        else:
            verdict_mismatches.append(
                {"rule_id": rid, "expected": str(want), "got": str(got_v)}
            )
    return {
        "doc_name": truth_doc.get("doc_name", ""),
        "clean_baseline": bool(truth_doc.get("clean_baseline", False)),
        "expected": expected,
        "got": got,
        "detected": detected,
        "missed": missed,
        "false_positives": false_positives,
        "verdict_matches": verdict_matches,
        "verdict_mismatches": verdict_mismatches,
        "ok": not missed and not false_positives and not verdict_mismatches,
    }


def _check_one_doc(path: Path, store: ClauseStore, rules: RuleStore, doc_name: str):
    """单文档核查流水线（与 ssc check 同路径：提取 → 参数卡 → 三级判定）。"""
    paras = extract_paras(path)
    doc_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    card = build_param_card(paras, doc_name=doc_name, doc_sha256=doc_sha256)
    return check_plan(card, rules, store)


def run_check_bench(
    data_dir: Path,
    work_dir: Optional[Path] = None,
    seed: int = DEFAULT_SEED,
    count: int = 5,
    store: Optional[ClauseStore] = None,
    rules: Optional[RuleStore] = None,
) -> Dict[str, Any]:
    """核查基准主入口：现场生成语料 → 逐份核查对账 → 汇总指标。

    work_dir 显式给出时产物保留（调用方管理）；缺省用临时目录并在结束时清理。
    """
    from ..datagen import gen_plan  # 延迟到函数内，保持 bench 包 import 轻量

    data_dir = Path(data_dir)
    issues: List[str] = []
    if store is None:
        store = ClauseStore(data_dir / "knowledge")
    if rules is None:
        rules = RuleStore(data_dir / "knowledge")
    issues.extend(f"规则库问题: {i}" for i in rules.issues)

    tmp_cleanup = work_dir is None
    corpus_dir = Path(work_dir) if work_dir is not None else Path(
        tempfile.mkdtemp(prefix="ssc_check_bench_")
    )
    try:
        truth = gen_plan.generate(corpus_dir, seed=seed, count=count)

        details: List[Dict[str, Any]] = []
        for doc in truth["docs"]:
            path = corpus_dir / doc["doc_name"]
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            if sha != doc.get("doc_sha256"):
                issues.append(f"{doc['doc_name']}: 现场产物 sha256 与 truth 不一致（生成器漂移）")
                continue
            try:
                report = _check_one_doc(path, store, rules, doc["doc_name"])
            except SSCError as exc:
                issues.append(f"{doc['doc_name']}: 核查失败 {exc}")
                continue
            rec = reconcile_doc(doc, report)
            rec["summary"] = report.summary()
            details.append(rec)

        expected_total = sum(len(d["expected"]) for d in details)
        detected_total = sum(len(d["detected"]) for d in details)
        false_total = sum(len(d["false_positives"]) for d in details)
        injected_total = sum(
            len(d["verdict_matches"]) + len(d["verdict_mismatches"]) for d in details
        )
        verdict_ok_total = sum(len(d["verdict_matches"]) for d in details)
        result: Dict[str, Any] = {
            "seed": seed,
            "count": count,
            "docs": len(details),
            "corpus_dir": str(corpus_dir),
            "injected_total": injected_total,
            "expected_total": expected_total,
            "detected_total": detected_total,
            "detection_rate": (detected_total / expected_total) if expected_total else None,
            "false_positives": false_total,
            "verdict_accuracy": (verdict_ok_total / injected_total) if injected_total else None,
            "thresholds": {
                "detection_rate": REQUIRED_DETECTION_RATE,
                "max_false_positives": MAX_FALSE_POSITIVES,
                "verdict_accuracy": REQUIRED_VERDICT_ACCURACY,
            },
            "issues": issues,
            "details": details,
        }
        return result
    finally:
        if tmp_cleanup:
            shutil.rmtree(corpus_dir, ignore_errors=True)


def thresholds_met(result: Dict[str, Any]) -> bool:
    """指标门槛判定（selfcheck/CLI bench/测试共用；指标为 None=语料退化，视为未达）。"""
    if result.get("issues"):
        return False
    if not result.get("docs"):
        return False
    detection = result.get("detection_rate")
    accuracy = result.get("verdict_accuracy")
    if detection is None or accuracy is None:
        return False
    return (
        detection >= REQUIRED_DETECTION_RATE
        and result.get("false_positives", 1 << 30) <= MAX_FALSE_POSITIVES
        and accuracy >= REQUIRED_VERDICT_ACCURACY
    )
