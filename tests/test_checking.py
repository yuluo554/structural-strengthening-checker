"""核查层：规则库加载/门控互斥/门控激活/三级判定兜底/证据子串校验/检查单。"""

from structural_strengthening_checker.checking.checklist_gb55021 import ChecklistStore
from structural_strengthening_checker.checking.engine import check_plan
from structural_strengthening_checker.checking.rules import RuleStore
from structural_strengthening_checker.core.clauses import ClauseStore
from structural_strengthening_checker.parsing.param_card import (
    Evidence,
    MethodItem,
    PlanParamCard,
)


def _rule(rid, category, keywords, check_type="param_range", severity="fail"):
    return {
        "id": rid,
        "name": rid,
        "gate": {"category": category, "only_if_keywords": keywords},
        "check_type": check_type,
        "target": "x",
        "op": ">=",
        "limit_ref": "L-1",
        "severity": severity,
        "message": "m",
        "advice": "a",
        "clause_id": "C-1",
        "status": "待核对",
    }


def test_repo_rules_load_and_mutex_ok(repo_data_dir):
    rules = RuleStore(repo_data_dir / "knowledge")
    assert not rules.issues
    assert rules.check_gate_mutex() == []
    assert len(rules.rules) >= 2


def test_gate_mutex_conflict_detected(make_knowledge):
    rules_json = [
        _rule("R-1", "catA", ["植筋"]),
        _rule("R-2", "catB", ["植筋"]),  # 同关键词跨类目 → 冲突
    ]
    rules = RuleStore(make_knowledge(rules=rules_json))
    conflicts = rules.check_gate_mutex()
    assert len(conflicts) == 1
    assert conflicts[0].keyword == "植筋"
    assert conflicts[0].categories == ["catA", "catB"]


def test_gate_activation_scopes_rules(make_knowledge):
    rules = RuleStore(
        make_knowledge(
            rules=[_rule("R-ADH", "adhesive", ["胶粘剂"]), _rule("R-ANCH", "anchor", ["锚固"])]
        )
    )
    card = PlanParamCard(source_text="本工程采用结构胶粘剂加固", methods=[])
    active = {r.id for r in rules.active_rules(card.full_text())}
    assert active == {"R-ADH"}


def test_check_plan_skeleton_all_needs_confirm(make_knowledge):
    """骨架兜底纪律：解析未实装时只产生 needs_confirm，绝不产生 fail。"""
    rules = RuleStore(make_knowledge(rules=[_rule("R-1", "adhesive", ["胶粘剂"])]))
    card = PlanParamCard(doc_name="方案.docx", source_text="采用胶粘剂")
    store = ClauseStore(make_knowledge(clauses=[]))
    report = check_plan(card, rules, store)
    assert report.summary() == {"fail": 0, "suspicious": 0, "needs_confirm": 1, "pass": 0}
    assert report.findings[0].clause_id == "C-1"


def test_evidence_substring_issue():
    card = PlanParamCard(
        doc_name="x.docx",
        source_text="方案正文：采用碳纤维布加固",
        methods=[MethodItem(name="粘贴碳纤维布", evidence=Evidence(quote="这段话不在原文里"))],
    )
    issues = card.evidence_issues()
    assert len(issues) == 1
    assert "不是原文子串" in issues[0]


def test_repo_checklist_loads(repo_data_dir):
    ckl = ChecklistStore(repo_data_dir / "knowledge")
    assert not ckl.issues
    assert len(ckl.items) >= 2
    assert {i.check_mode for i in ckl.items} <= {"manual", "auto_text"}
