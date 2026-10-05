"""M1/M2 数据守门：条款库/规则库/检查单/算例库的入库纪律与交付面。"""

from structural_strengthening_checker.checking.checklist_gb55021 import ChecklistStore
from structural_strengthening_checker.checking.rules import RuleStore
from structural_strengthening_checker.core.clauses import ClauseStore


def test_repo_clauses_batch_coverage(repo_data_dir):
    """入库覆盖 5 本规范（M3 新增 GB/T 50010 钢筋强度设计值条款）；占位 ID（M0 骨架用）必须清零。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    standards = {c.standard for c in store.all_clauses()}
    assert standards == {
        "GB 50367-2013",
        "GB 55021-2021",
        "GB 50728-2011",
        "JGJ 145-2013",
        "GB/T 50010-2010（2024年版，混凝土结构设计标准）",
    }
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
    """M1 三例植筋真值：手工计算书来源 + 真值可独立复算（±0.5% 容差口径）。"""
    from structural_strengthening_checker.bench.calc_bench import load_cases

    cases, issues = load_cases(repo_data_dir / "cases")
    assert issues == []
    truths = {
        "PR-001": (230.4, 1.1),
        "PR-002": (282.24, 1.1),
        "PR-003": (345.6, 1.65),
    }
    pr_cases = [c for c in cases if c["case_id"] in truths]
    assert len(pr_cases) == 3
    for case in pr_cases:
        ls_expected, psi_expected = truths[case["case_id"]]
        inp = case["input"]
        # 式(15.2.3)（文本已核对）独立复算
        ls = 0.2 * inp["alpha_spt"] * inp["d"] * inp["fy"] / inp["fbd"]
        assert abs(ls - ls_expected) <= 0.005 * ls_expected
        # 式(15.2.5)（文本已核对）独立复算
        psi = inp["psi_br"] * inp["psi_w"] * inp["psi_T"]
        assert abs(psi - psi_expected) <= 0.005 * psi_expected


def test_repo_cases_m2_backfill_complete(repo_data_dir):
    """M2 回填：pending/ 骨架已按核对公式回填入基准（9 例受弯 + 2 例植筋查表），目录删除。"""
    from structural_strengthening_checker.bench.calc_bench import load_cases

    cases, issues = load_cases(repo_data_dir / "cases")
    assert issues == []
    ids = {c["case_id"] for c in cases}
    flexure_ids = {f"CF-00{i}-{s}" for i, s in ((1, "P"), (2, "S"), (3, "R"))}
    flexure_ids |= {f"SP-00{i}-{s}" for i, s in ((1, "P"), (2, "S"), (3, "R"))}
    flexure_ids |= {f"SE-00{i}-{s}" for i, s in ((1, "P"), (2, "S"), (3, "R"))}
    assert flexure_ids <= ids
    assert {"PR-004", "PR-005"} <= ids
    assert not (repo_data_dir / "cases" / "pending").exists()
