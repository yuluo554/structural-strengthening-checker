"""基准骨架：算例 schema 守门（无来源拒收）+ 门控阻塞如实报告。"""

import json

from structural_strengthening_checker.bench.calc_bench import load_cases, run_calc_bench
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
