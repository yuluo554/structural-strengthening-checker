"""基准骨架：算例 schema 守门（无来源拒收）+ 门控阻塞如实报告 + M4 核查基准指标门槛。

M4 纪律（plan/05 §五）：指标门槛（检出率 1.0 / 误报 0 / 判定准确率 1.0）是基准常量，
不达标必须回修实现、不得放宽门槛——这些常量在此处与 CLI 输出双向锁死。
"""

import json

import pytest

from structural_strengthening_checker.bench.calc_bench import load_cases, run_calc_bench
from structural_strengthening_checker.bench.check_bench import (
    MAX_FALSE_POSITIVES,
    REQUIRED_DETECTION_RATE,
    REQUIRED_VERDICT_ACCURACY,
    reconcile_doc,
    run_check_bench,
    thresholds_met,
)
from structural_strengthening_checker.checking.engine import (
    VERDICT_FAIL,
    CheckFinding,
    CheckReport,
)
from structural_strengthening_checker.core.clauses import ClauseStore


def _case(**overrides):
    case = {
        "case_id": "C-001",
        "module": "cfrp_beam_flexure",
        "input": {"b": 250, "h": 500},
        "expected": {"capacity": 200.0, "tolerance": 0.005},
        "source": {"title": "规范条文说明例题", "locator": "p.123 例 8-1"},
    }
    case.update(overrides)
    return case


def test_case_without_source_rejected(tmp_path):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    # source 字段存在但无 title/channel（即"提供了来源字段却无可考来源"）→ 无来源拒收
    (cases_dir / "a.json").write_text(
        json.dumps([_case(source={"note": "网络资料"})]), encoding="utf-8"
    )
    cases, issues = load_cases(cases_dir)
    assert cases == []
    assert any("无来源" in i for i in issues)


def test_case_missing_keys_rejected(tmp_path):
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "a.json").write_text(json.dumps([{"case_id": "C-2"}]), encoding="utf-8")
    cases, issues = load_cases(cases_dir)
    assert cases == []
    assert any("缺少必填字段" in i for i in issues)


def test_repo_cases_dir_m2_batch(repo_data_dir):
    """M2 回填后：14 例（5 植筋 + 9 受弯）全部带来源（手工计算书），pending/ 已删除。"""
    cases, issues = load_cases(repo_data_dir / "cases")
    assert issues == []
    assert len(cases) == 14
    expected_ids = {"PR-001", "PR-002", "PR-003", "PR-004", "PR-005"}
    flexure_ids = {f"CF-00{i}-{s}" for i, s in ((1, "P"), (2, "S"), (3, "R"))}
    flexure_ids |= {f"SP-00{i}-{s}" for i, s in ((1, "P"), (2, "S"), (3, "R"))}
    flexure_ids |= {f"SE-00{i}-{s}" for i, s in ((1, "P"), (2, "S"), (3, "R"))}
    assert {c["case_id"] for c in cases} == expected_ids | flexure_ids
    for case in cases:
        # 真值必有来源：来源指向仓库内可复核的手工计算书
        assert "workings" in case["source"]["locator"]
    assert not (repo_data_dir / "cases" / "pending").exists()


def test_bench_blocks_on_unverified_clauses(tmp_path):
    """算例走 run_calc 同一门控：条款未核对 → blocked_by_clauses，不虚报通过。"""
    from structural_strengthening_checker.core.engine import CALC_REGISTRY

    module = CALC_REGISTRY["cfrp_beam_flexure"]
    kdir = tmp_path / "knowledge"
    (kdir / "clauses").mkdir(parents=True)
    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "0.0.0",
            "title": "t",
            "gist": "g",
            "status": "待核对",
            "source": {"channel": None, "checked_date": None},
        }
        for cid in module.required_clauses
    ]
    (kdir / "clauses" / "c.json").write_text(json.dumps(clauses), encoding="utf-8")
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "a.json").write_text(json.dumps([_case()]), encoding="utf-8")
    result = run_calc_bench(tmp_path, store=ClauseStore(kdir))
    assert result["total"] == 1
    assert result["blocked_by_clauses"] == 1
    assert result["passed"] == 0


def test_bench_case_passes_with_verified_clauses(tmp_path):
    """条款全核对 + 计算体实装：真值匹配 → passed；verdict 严格相等口径。"""
    module_id = "cfrp_beam_flexure"
    from structural_strengthening_checker.core.engine import CALC_REGISTRY

    module = CALC_REGISTRY[module_id]
    kdir = tmp_path / "knowledge"
    (kdir / "clauses").mkdir(parents=True)
    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "1.0.1",
            "title": "t",
            "gist": "g",
            "status": "已核对",
            "source": {"checked_date": "2026-10-05"},
        }
        for cid in module.required_clauses
    ]
    (kdir / "clauses" / "c.json").write_text(json.dumps(clauses), encoding="utf-8")
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    cf_input = {
        "b": 250.0, "h": 500.0, "fc": 14.3, "As": 1520.0, "fy": 360.0,
        "Afe": 101.0, "Ecf": 240000.0, "M0": 0.0, "M": 180.0,
        "ff": 2300.0, "ef": 0.01, "as": 35.0, "xi_b": 0.518, "Es": 200000.0,
    }
    (cases_dir / "a.json").write_text(
        json.dumps([_case(input=cf_input, expected={"verdict": "满足", "Mu_kNm": 244.02,
                                                    "tolerance": 0.005})]),
        encoding="utf-8",
    )
    result = run_calc_bench(tmp_path, store=ClauseStore(kdir))
    assert result["blocked_by_clauses"] == 0
    assert result["passed"] == 1
    assert result["failed"] == 0


def test_bench_truth_mismatch_counts_failed(tmp_path):
    """真值失配（数值超容差/verdict 不符/指标缺失）→ 如实计 failed 并给出问题明细。"""
    module_id = "cfrp_beam_flexure"
    from structural_strengthening_checker.core.engine import CALC_REGISTRY

    module = CALC_REGISTRY[module_id]
    kdir = tmp_path / "knowledge"
    (kdir / "clauses").mkdir(parents=True)
    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "1.0.1",
            "title": "t",
            "gist": "g",
            "status": "已核对",
            "source": {"checked_date": "2026-10-05"},
        }
        for cid in module.required_clauses
    ]
    (kdir / "clauses" / "c.json").write_text(json.dumps(clauses), encoding="utf-8")
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    cf_input = {
        "b": 250.0, "h": 500.0, "fc": 14.3, "As": 1520.0, "fy": 360.0,
        "Afe": 101.0, "Ecf": 240000.0, "M0": 0.0, "M": 180.0,
        "ff": 2300.0, "ef": 0.01, "as": 35.0, "xi_b": 0.518, "Es": 200000.0,
    }
    bad = _case(case_id="BAD-1", input=cf_input,
                expected={"verdict": "满足", "Mu_kNm": 999.0, "no_such_metric": 1.0})
    (cases_dir / "a.json").write_text(json.dumps([bad]), encoding="utf-8")
    result = run_calc_bench(tmp_path, store=ClauseStore(kdir))
    assert result["failed"] == 1
    problems = result["details"][0]["problems"]
    assert any("Mu_kNm" in p for p in problems)
    assert any("no_such_metric" in p for p in problems)


# ---------------------------------------------------------------------------
# M4：方案核查基准（现场生成 → 对账 → 指标门槛）
# ---------------------------------------------------------------------------

def _finding(rule_id, verdict):
    return CheckFinding(
        rule_id=rule_id, rule_name=rule_id, verdict=verdict,
        message="m", clause_id="c",
    )


def test_reconcile_doc_semantics():
    """对账语义单测：漏检/误报/主期望判定比对/also_expect 并入期望集合。"""
    truth_doc = {
        "doc_name": "t.docx",
        "injected": [
            {"rule_id": "R-ADH-001", "expected_verdict": "fail", "also_expect": ["R-XX-002"]},
            {"rule_id": "R-ANCH-001", "expected_verdict": "suspicious", "also_expect": []},
        ],
        # 生成器真值语义：全部注入 rule_id 都在 expected_non_pass（v1 全 fail；此处演示多档）
        "expected_non_pass": ["R-ADH-001", "R-ANCH-001"],
    }
    # 期望集合 = expected_non_pass ∪ also_expect；报告恰好命中且判定一致 → 全 OK
    report = CheckReport("t.docx", findings=[
        _finding("R-ADH-001", VERDICT_FAIL),
        _finding("R-XX-002", "needs_confirm"),
        _finding("R-ANCH-001", "suspicious"),
    ])
    rec = reconcile_doc(truth_doc, report)
    assert rec["ok"]
    assert rec["expected"] == ["R-ADH-001", "R-ANCH-001", "R-XX-002"]
    assert rec["missed"] == [] and rec["false_positives"] == []
    assert rec["verdict_matches"] == ["R-ADH-001", "R-ANCH-001"]

    # 漏检 + 误报 + 判定不符各一处 → 如实记录，ok=False
    report_bad = CheckReport("t.docx", findings=[
        _finding("R-ADH-001", "suspicious"),   # 判定不符（期望 fail）
        _finding("R-OTHER", "needs_confirm"),  # 误报（期望集合之外）
        # R-ANCH-001 未报告 → 漏检
    ])
    rec_bad = reconcile_doc(truth_doc, report_bad)
    assert not rec_bad["ok"]
    assert rec_bad["missed"] == ["R-ANCH-001", "R-XX-002"]
    assert rec_bad["false_positives"] == ["R-OTHER"]
    assert rec_bad["verdict_mismatches"] == [
        {"rule_id": "R-ADH-001", "expected": "fail", "got": "suspicious"},
        # 漏检的注入项判定比对记 got=None（未报告）
        {"rule_id": "R-ANCH-001", "expected": "suspicious", "got": "None"},
    ]


def test_check_bench_meets_thresholds(repo_data_dir, tmp_path):
    """M4 DoD 门槛锁死：检出率 1.0、误报 0、判定准确率 1.0（现场生成，产物入 tmp）。"""
    result = run_check_bench(repo_data_dir, work_dir=tmp_path / "corpus")
    assert result["issues"] == []
    assert result["docs"] == 6  # 1 基线 + 5 注入（seed 固定语料形态）
    assert result["detection_rate"] >= REQUIRED_DETECTION_RATE
    assert result["false_positives"] <= MAX_FALSE_POSITIVES
    assert result["verdict_accuracy"] >= REQUIRED_VERDICT_ACCURACY
    assert thresholds_met(result)
    # 基线文档显式断言：期望为空、无误报（0 误报口径的基线面）
    baseline = next(d for d in result["details"] if d["clean_baseline"])
    assert baseline["expected"] == [] and baseline["got"] == []


def test_thresholds_met_fails_on_missing_corpus():
    """语料退化（0 文档/带 issues/指标 None）不得判达标——防基准空转。"""
    assert not thresholds_met({"docs": 0, "issues": [], "detection_rate": None,
                               "false_positives": 0, "verdict_accuracy": None})
    assert not thresholds_met({"docs": 1, "issues": ["x"], "detection_rate": 1.0,
                               "false_positives": 0, "verdict_accuracy": 1.0})


def test_check_bench_thresholds_are_dod_values():
    """门槛常量本身是 M4 DoD：检出率 1.0 / 误报 0 / 判定准确率 1.0（改门槛=改 DoD，此处报警）。"""
    assert REQUIRED_DETECTION_RATE == 1.0
    assert MAX_FALSE_POSITIVES == 0
    assert REQUIRED_VERDICT_ACCURACY == 1.0
