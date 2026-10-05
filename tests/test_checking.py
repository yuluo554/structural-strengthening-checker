"""核查层：规则库加载/门控互斥/门控激活/三级判定兜底/证据子串校验/检查单 + M3 判定矩阵。"""

import pytest

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


# ---------------------------------------------------------------------------
# M3 判定矩阵（unit 级：合成参数卡 × 仓库规则库/条款库）
# ---------------------------------------------------------------------------

from structural_strengthening_checker.parsing.param_card import (  # noqa: E402
    Evidence,
    ValueItem,
)
from structural_strengthening_checker.checking.engine import (  # noqa: E402
    ANCHOR_FORMULA_COEF,
    ANCHOR_PSI_AE_MIN,
    ANCHOR_PSI_W_MIN,
    ANCHOR_PSI_BR_MIN,
    ANCHOR_PSI_T_MIN,
    check_plan,
)


def _repo(repo_data_dir):
    return (
        RuleStore(repo_data_dir / "knowledge"),
        ClauseStore(repo_data_dir / "knowledge"),
    )


def _card(source_text, **items):
    return PlanParamCard(doc_name="t.docx", source_text=source_text, **items)


def _adh_item(value, grade):
    return ValueItem(
        kind="钢对钢拉伸抗剪强度标准值", value=value, unit="MPa", label=grade,
        evidence=Evidence(para=1, quote="钢对钢拉伸抗剪强度标准值 %sMPa" % value),
    )


def _depth_item(value):
    return ValueItem(
        kind="植筋", value=value, unit="mm", label="植筋",
        evidence=Evidence(para=2, quote="锚固深度设计值 %smm" % value),
    )


def _anchor_card(depth, dia=12.0, grade_label="HRB400", fc=40.0, adh="A", fy=None):
    design = [
        ValueItem(kind="植筋直径", value=dia, unit="mm"),
        ValueItem(kind="钢筋牌号", label=grade_label),
        ValueItem(kind="混凝土强度等级", value=fc, unit="C", label="C%d" % fc),
        ValueItem(kind="胶粘剂等级", label=adh),
    ]
    if fy is not None:
        design.append(ValueItem(kind="钢筋强度设计值", value=fy, unit="MPa"))
    return _card(
        "植筋锚固深度：锚固深度设计值 %smm。直径 %smm，HRB400，C40，A 级胶。" % (depth, dia),
        anchor_depths=[_depth_item(depth)],
        design_params=design,
    )


def _verdict_of(report, rule_id):
    for f in report.findings:
        if f.rule_id == rule_id:
            return f.verdict
    return None


def test_repo_rconst_gate_uses_method_names(repo_data_dir):
    """M1 实测口径锁死：R-CONST-001 门控词=加固方法名（卸载词做门控会漏激活缺失型检查）。"""
    rules, _ = _repo(repo_data_dir)
    rule = next(r for r in rules.rules if r.id == "R-CONST-001")
    assert set(rule.only_if_keywords) == {"增大截面", "粘贴钢板", "碳纤维"}
    assert "卸载" not in rule.only_if_keywords
    assert rule.check_type == "param_required"


def test_adhesive_matrix(repo_data_dir):
    rules, store = _repo(repo_data_dir)
    src = "结构胶：采用 A 级结构胶粘剂，钢对钢拉伸抗剪强度标准值 {v}MPa。"
    cases = {
        15.8: "pass",     # ≥ 全部适用限值（A级 15/14）
        12.0: "fail",     # < 下限 14
        14.5: "suspicious",  # 介于 14~15（用途档不同）
    }
    for value, expected in cases.items():
        card = _card(src.format(v=value), adhesive_indices=[_adh_item(value, "A")])
        report = check_plan(card, rules, store)
        assert _verdict_of(report, "R-ADH-001") == expected, value


def test_adhesive_unlabeled_and_unknowable(repo_data_dir):
    rules, store = _repo(repo_data_dir)
    # 门控命中但未标注指标值 → fail（规则 message 覆盖"或未标注"）
    card = _card("本工程采用 A 级结构胶粘剂。")
    assert _verdict_of(check_plan(card, rules, store), "R-ADH-001") == "fail"
    # 有值但等级未标注 → 无法选限值档 → needs_confirm
    card2 = _card("结构胶钢对钢拉伸抗剪强度标准值 13.0MPa。",
                  adhesive_indices=[_adh_item(13.0, None)])
    assert _verdict_of(check_plan(card2, rules, store), "R-ADH-001") == "needs_confirm"


def test_anchor_matrix(repo_data_dir):
    rules, store = _repo(repo_data_dir)
    # 320 ≥ 需求下限 190.1 → pass；150 < 下限 → fail（最有利假设下仍不足）
    assert _verdict_of(check_plan(_anchor_card(320.0), rules, store), "R-ANCH-001") == "pass"
    fail_report = check_plan(_anchor_card(150.0), rules, store)
    assert _verdict_of(fail_report, "R-ANCH-001") == "fail"
    finding = next(f for f in fail_report.findings if f.rule_id == "R-ANCH-001")
    ev = finding.evidence
    assert ev["stated_mm"] == 150.0
    assert ev["ld_required_lower_mm"] == pytest.approx(190.08, abs=0.05)


def test_anchor_needs_confirm_paths(repo_data_dir):
    rules, store = _repo(repo_data_dir)
    # 牌号 2024 年版表已删除（HRB335）→ fy 无法映射
    assert _verdict_of(check_plan(_anchor_card(320.0, grade_label="HRB335"), rules, store),
                       "R-ANCH-001") == "needs_confirm"
    # 缺植筋直径
    card = _anchor_card(320.0)
    card.design_params = [p for p in card.design_params if p.kind != "植筋直径"]
    assert _verdict_of(check_plan(card, rules, store), "R-ANCH-001") == "needs_confirm"
    # 基材等级不在表15.2.4 列（C35）
    assert _verdict_of(check_plan(_anchor_card(320.0, fc=35.0), rules, store),
                       "R-ANCH-001") == "needs_confirm"
    # 未标注锚固深度 → fail
    card2 = _card("植筋采用 HRB400 钢筋，直径 12mm，混凝土强度等级 C40，A 级胶（方案未写锚固深度）。",
                  design_params=_anchor_card(320.0).design_params)
    assert _verdict_of(check_plan(card2, rules, store), "R-ANCH-001") == "fail"


def test_presence_checks_and_gates(repo_data_dir):
    rules, store = _repo(repo_data_dir)
    gate_src = "本加固方案采用碳纤维加固。"
    # R-APP-001：有/无程序性鉴定证据
    card_ok = _card(gate_src + "鉴定结论：满足要求。", appraisal_first=Evidence(para=1, quote=gate_src))
    assert _verdict_of(check_plan(card_ok, rules, store), "R-APP-001") == "pass"
    assert _verdict_of(check_plan(_card(gate_src), rules, store), "R-APP-001") == "fail"
    # R-CONST-001：门控激活（方法词在场）+ 卸载描述有/无
    card_u = _card(gate_src, unloading=[ValueItem(kind="卸载", evidence=Evidence(para=1, quote=gate_src))])
    assert _verdict_of(check_plan(card_u, rules, store), "R-CONST-001") == "pass"
    assert _verdict_of(check_plan(_card(gate_src), rules, store), "R-CONST-001") == "fail"


def test_unverified_rule_never_fails(make_knowledge):
    """规则依据未核对 → 一律 needs_confirm，绝不产生 fail（limit 依据纪律）。"""
    rule = _rule("R-X", "adhesive", ["胶粘剂"], severity="fail")  # status=待核对
    rules = RuleStore(make_knowledge(rules=[rule]))
    card = _card("胶粘剂指标钢对钢拉伸抗剪强度标准值 3.0MPa。")  # 门控在场、无指标抽取项 → fail 候选
    report = check_plan(card, rules, ClauseStore(make_knowledge(clauses=[])))
    assert report.summary()["fail"] == 0
    assert _verdict_of(report, "R-X") == "needs_confirm"


def test_parse_failure_degrades_everything(repo_data_dir):
    rules, store = _repo(repo_data_dir)
    card = _card("")
    report = check_plan(card, rules, store, parse_failed=True)
    assert report.degraded is True
    assert report.summary() == {"fail": 0, "suspicious": 0, "needs_confirm": 4, "pass": 0}
    # 零段落（如无文本层 PDF）同口径降级
    report2 = check_plan(_card(""), rules, store)
    assert report2.degraded is True
    assert report2.summary()["fail"] == 0


def test_unknown_target_falls_back_needs_confirm(make_knowledge, repo_data_dir):
    rule = _rule("R-FUT", "future", ["新类目"], check_type="consistency")
    rule["status"] = "已核对"
    rules = RuleStore(make_knowledge(rules=[rule]))
    store = ClauseStore(make_knowledge(clauses=[]))
    card = _card("新类目相关描述。")
    assert _verdict_of(check_plan(card, rules, store), "R-FUT") == "needs_confirm"


def test_check_layer_limits_match_clause_json(repo_data_dir):
    """核查层规范系数 ↔ 条款库 limits 双出口对账（同 test_code_tables_match_clause_json 纪律）。"""
    store = ClauseStore(repo_data_dir / "knowledge")
    c1523 = store.get("GB50367-2013-15.2.3").limits
    c1525 = store.get("GB50367-2013-15.2.5").limits
    c1522 = store.get("GB50367-2013-15.2.2").limits
    assert ANCHOR_FORMULA_COEF == c1523["formula_coefficient"]
    assert ANCHOR_PSI_W_MIN == c1525["psi_w_min"]
    assert ANCHOR_PSI_BR_MIN == c1525["psi_br_other"]
    assert ANCHOR_PSI_T_MIN == c1525["psi_T_le_60C"]
    assert ANCHOR_PSI_AE_MIN == c1522["psi_ae_gt_C30"]
    # fy 映射与 GB/T 50010 条款一致（引擎经条款库取值，此处锁死锚点）
    fy = store.get("GB50010-2010-4.2.3").limits["fy_design_N_mm2"]
    assert fy["HRB400"] == 360 and fy["HPB300"] == 270 and fy["HRB500"] == 435
