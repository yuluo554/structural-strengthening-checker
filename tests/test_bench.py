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


def test_repo_cases_dir_empty_is_ok(repo_data_dir):
    cases, issues = load_cases(repo_data_dir / "cases")
    assert cases == []
    assert issues == []


def test_bench_blocks_on_unverified_clauses(tmp_path, repo_data_dir):
    """算例走 run_calc 同一门控：条款未核对 → blocked_by_clauses，不虚报通过。"""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "a.json").write_text(json.dumps([_case()]), encoding="utf-8")
    store = ClauseStore(repo_data_dir / "knowledge")
    result = run_calc_bench(tmp_path, store=store)
    assert result["total"] == 1
    assert result["blocked_by_clauses"] == 1
    assert result["passed"] == 0


def test_bench_verified_clause_reaches_stub(tmp_path):
    """条款全核对后算例进入计算体；stub 抛 NotImplementedError → 如实计 failed。"""
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
    (cases_dir / "a.json").write_text(
        json.dumps([_case(input={"b": 250.0, "h": 500.0, "fc": 14.3, "As": 1520.0,
                                  "fy": 360.0, "Afe": 101.0, "Ecf": 240000.0,
                                  "M0": 0.0, "M": 180.0})]),
        encoding="utf-8",
    )
    result = run_calc_bench(tmp_path, store=ClauseStore(kdir))
    assert result["blocked_by_clauses"] == 0
    assert result["failed"] == 1
    assert "M2" in result["details"][0]["error"]
