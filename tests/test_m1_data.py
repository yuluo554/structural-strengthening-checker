"""M1 数据先行守门：条款库/规则库/检查单/算例库的入库纪律与 M1 交付面。"""

import json

from structural_strengthening_checker.checking.checklist_gb55021 import ChecklistStore
from structural_strengthening_checker.checking.rules import RuleStore
from structural_strengthening_checker.core.clauses import ClauseStore


def test_repo_clauses_batch_coverage(repo_data_dir):
    """首批入库覆盖 4 本规范；占位 ID（M0 骨架用）必须清零。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    standards = {c.standard for c in store.all_clauses()}
    assert standards == {"GB 50367-2013", "GB 55021-2021", "GB 50728-2011", "JGJ 145-2013"}
    all_text = " ".join(store._clauses)
    for placeholder in ("CFRP-FLEXURE", "STEEL-PLATE-FLEXURE", "SECTION-ENLARGE", "POST-REBAR-ANCHOR"):
        assert placeholder not in all_text


def test_repo_rules_all_verified_with_real_clause_refs(repo_data_dir):
    rules = RuleStore(repo_data_dir / "knowledge")
    assert not rules.issues
    assert len(rules.rules) == 4
    store = ClauseStore(repo_data_dir / "knowledge")
    for rule in rules.rules:
        assert rule.status == "已核对", rule.id
        assert rule.clause_id in store, rule.id
        assert store.get(rule.clause_id).status == "已核对", rule.id
    assert rules.check_gate_mutex() == []


def test_repo_rules_categories_distinct(repo_data_dir):
    """四个核查类目（胶粘剂/锚固/鉴定先行/卸载构造）齐备且关键词互斥。"""
    rules = RuleStore(repo_data_dir / "knowledge")
    assert {r.category for r in rules.rules} == {"adhesive", "anchoring", "appraisal", "unloading"}


def test_repo_checklist_all_verified_with_clause_no(repo_data_dir):
    ckl = ChecklistStore(repo_data_dir / "knowledge")
    assert not ckl.issues
    assert len(ckl.items) == 11
    for item in ckl.items:
        assert item.status == "已核对", item.item_id
        assert item.clause_no, item.item_id  # M1 按原文回填真实条号
        assert item.clause_no in item.item_id  # item_id 与条号一致（GB55021-<条号>）


def test_repo_case_truths_computable_and_sourced(repo_data_dir):
    """M1 真值算例：手工计算书来源 + 真值可独立复核（±0.5% 容差口径）。"""
    from structural_strengthening_checker.bench.calc_bench import load_cases

    cases, issues = load_cases(repo_data_dir / "cases")
    assert issues == []
    truths = {
        "PR-001": (230.4, 1.1),
        "PR-002": (282.24, 1.1),
        "PR-003": (345.6, 1.65),
    }
    for case in cases:
        ls_expected, psi_expected = truths[case["case_id"]]
        inp = case["input"]
        # 式(15.2.3)（文本已核对）独立复算
        ls = 0.2 * inp["alpha_spt"] * inp["d"] * inp["fy"] / inp["fbd"]
        assert abs(ls - ls_expected) <= 0.005 * ls_expected
        # 式(15.2.5)（文本已核对）独立复算
        psi = inp["psi_br"] * inp["psi_w"] * inp["psi_T"]
        assert abs(psi - psi_expected) <= 0.005 * psi_expected


def test_pending_cases_not_loaded_by_bench(repo_data_dir):
    """pending/ 骨架不得进入基准评测（load_cases 只扫顶层 *.json）。"""
    from structural_strengthening_checker.bench.calc_bench import load_cases

    cases, _ = load_cases(repo_data_dir / "cases")
    ids = {c["case_id"] for c in cases}
    pending = json.loads(
        (repo_data_dir / "cases" / "pending" / "flexure_pending_cases.json").read_text(
            encoding="utf-8"
        )
    )
    pending_ids = {c["case_id"] for c in pending["cases"]}
    assert len(pending_ids) == 9
    assert not (ids & pending_ids)
