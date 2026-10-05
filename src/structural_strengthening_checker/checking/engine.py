"""核查引擎：参数卡 × 规则库 → 三级判定报告（M3 实装）。

判定形态（plan/04 §1.5 规则 schema；HANDOFF-M3 §二.3）：
- param_range 数值比对：R-ADH-001（胶粘剂指标 vs 条款限值，按胶等级选档）与
  R-ANCH-001（标注锚固深度 vs 需求下限估算）；
- checklist 存在性：R-APP-001（"先鉴定后加固"证据在场）；
- param_required 缺失型：R-CONST-001（方法类目激活而卸载/支撑描述缺失——门控词用
  加固方法名，缺失型检查对"未提卸载"的文档也要激活，M1 实测口径）。

三级判定与兜底纪律：
- fail 仅在文档自身可证不足时产生（数值低于限值 / 缺失型要求确无描述）；
- suspicious=疑似（介于多档适用限值之间等"不能排除"情形）；
- needs_confirm=证据不足/无法建立限值/规则依据未核对/目标类型暂不支持自动判定；
  解析失败或可解析段落为 0 时全部规则整体降级 needs_confirm（plan/03 §三）；
- 规则 status≠已核对 → 一律 needs_confirm，绝不产生 fail（limit 依据纪律）；
- 每条结论挂依据条款 clause_id；值类结论附原文摘录（quote 必为 source_text 子串），
  缺失型结论附门控关键词（无正向原文可摘）。

R-ANCH-001 需求下限口径（M3 决策，plan/06）：文档通常不提供 s1/s2/保护层/受力状态，
无法精确复算要求值；本层取"最有利假设下限"做筛查——αspt 取表15.2.3 该直径全列最小
（内插）、fbd 取表15.2.4 该胶等级/基材等级的最高档、ψbr·ψw·ψT 取规范下限（1.0·1.1·1.0，
ψw 下限 1.1 出自 15.2.5 条文）、ψae 取 1.0（15.2.2 非抗震）。标注深度低于该下限 ⇒ 无论
实际构造条件如何均不满足（fail 声音可靠）；不低于下限 ⇒ 筛查通过（pass），精确复核应
用 ssc calc post_rebar_anchor 补全参数后验算。fy 由钢筋牌号按 GB/T 50010-2010（2024年版）
表4.2.3-1（条款库 GB50010-2010-4.2.3）映射；牌号未登记或文档未提供牌号 → needs_confirm。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..calc.common import ALPHA_SPT_ROWS, FBD_TABLE
from ..core.clauses import ClauseStore
from ..core.errors import ClauseNotVerifiedError
from ..parsing.param_card import PlanParamCard, ValueItem
from .rules import Rule, RuleStore

VERDICT_FAIL = "fail"
VERDICT_SUSPICIOUS = "suspicious"
VERDICT_NEEDS_CONFIRM = "needs_confirm"
VERDICT_PASS = "pass"

# 判定等级的中文标签（CLI 文本输出与 docx 报告共用，单一出口）
VERDICT_LABELS = {
    "fail": "不符合",
    "suspicious": "疑似",
    "needs_confirm": "待人工确认",
    "pass": "通过",
}

_SEVERITY_ORDER = (VERDICT_FAIL, VERDICT_SUSPICIOUS, VERDICT_NEEDS_CONFIRM, VERDICT_PASS)


def worst_verdict(verdicts: List[str]) -> str:
    """多条判定取最重（fail > suspicious > needs_confirm > pass）；空列表兜底 needs_confirm。

    M4 起为公共接口：核查基准的判定准确率按"该 rule_id 在报告中的最重 verdict"对账。
    """
    for v in _SEVERITY_ORDER:
        if v in verdicts:
            return v
    return VERDICT_NEEDS_CONFIRM

# 植筋锚固筛查支撑条款（全部须已核对方可数值判定；limits 键由测试与条款库对账）
CLAUSE_ANCHOR_FORMULA = "GB50367-2013-15.2.3"
CLAUSE_ANCHOR_FBD = "GB50367-2013-15.2.4"
CLAUSE_ANCHOR_PSI = "GB50367-2013-15.2.5"
CLAUSE_ANCHOR_COMB = "GB50367-2013-15.2.2"
CLAUSE_REBAR_FY = "GB50010-2010-4.2.3"

ANCHOR_SUPPORT_CLAUSES = (
    CLAUSE_ANCHOR_FORMULA,
    CLAUSE_ANCHOR_FBD,
    CLAUSE_ANCHOR_PSI,
    CLAUSE_ANCHOR_COMB,
    CLAUSE_REBAR_FY,
)

# 锚固需求下限用的规范系数（出处见模块 docstring；与条款库 limits 由
# test_check_layer_limits_match_clause_json 锁死一致，改任一侧必须同步）
ANCHOR_FORMULA_COEF = 0.2      # 式15.2.3 ls=0.2·αspt·d·fy/fbd（15.2.3 limits.formula_coefficient）
ANCHOR_PSI_BR_MIN = 1.0        # 15.2.5 limits.psi_br_other（其他构件下限）
ANCHOR_PSI_W_MIN = 1.1         # 15.2.5 limits.psi_w_min（孔壁潮湿影响系数下限）
ANCHOR_PSI_T_MIN = 1.0         # 15.2.5 limits.psi_T_le_60C（T≤60℃）
ANCHOR_PSI_AE_MIN = 1.0        # 15.2.2 limits.psi_ae_gt_C30（基材高于 C30 / 非抗震下限）


@dataclass
class CheckFinding:
    rule_id: str
    rule_name: str
    verdict: str
    message: str
    clause_id: str
    advice: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckReport:
    doc_name: str
    findings: List[CheckFinding] = field(default_factory=list)
    degraded: bool = False  # 解析失败/零段落整体降级标记

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"fail": 0, "suspicious": 0, "needs_confirm": 0, "pass": 0}
        for f in self.findings:
            counts[f.verdict] = counts.get(f.verdict, 0) + 1
        return counts

    def non_pass_rule_ids(self) -> List[str]:
        """M4 对账口径：文档全部非 pass 结论的 rule_id 集合（保序去重）。"""
        seen: List[str] = []
        for f in self.findings:
            if f.verdict != VERDICT_PASS and f.rule_id not in seen:
                seen.append(f.rule_id)
        return seen




def check_plan(
    card: PlanParamCard,
    rules: RuleStore,
    store: ClauseStore,
    parse_failed: bool = False,
) -> CheckReport:
    """参数卡 × 规则库 → 三级判定。parse_failed=True 或零段落时整体降级 needs_confirm。"""
    degraded = parse_failed or not card.source_text.strip()
    report = CheckReport(doc_name=card.doc_name, degraded=degraded)

    if degraded:
        for rule in rules.rules:
            report.findings.append(
                CheckFinding(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    verdict=VERDICT_NEEDS_CONFIRM,
                    message="方案文本解析失败/无可解析段落，整体降级待人工确认（不产生任何自动 fail）",
                    clause_id=rule.clause_id,
                    advice=rule.advice,
                    evidence={"gate_keywords": list(rule.only_if_keywords)},
                )
            )
        return report

    # 证据子串审计（FR-B5 总闸）：抽取层丢弃留痕 + 独立复核，异常项降级 needs_confirm
    for note in card.notes:
        report.findings.append(
            CheckFinding(
                rule_id="EVIDENCE",
                rule_name="证据子串校验",
                verdict=VERDICT_NEEDS_CONFIRM,
                message=f"抽取证据问题（该项已丢弃）：{note}",
                clause_id="",
            )
        )
    for issue in card.evidence_issues():
        report.findings.append(
            CheckFinding(
                rule_id="EVIDENCE",
                rule_name="证据子串校验",
                verdict=VERDICT_NEEDS_CONFIRM,
                message=f"抽取证据问题（防幻觉复核）：{issue}",
                clause_id="",
            )
        )

    gate_text = card.full_text()
    for rule in rules.active_rules(gate_text):
        if rule.status != "已核对":
            report.findings.append(
                CheckFinding(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    verdict=VERDICT_NEEDS_CONFIRM,
                    message=f"{rule.message}（规则依据 status={rule.status}，未核对不产生自动 fail）",
                    clause_id=rule.clause_id,
                    advice=rule.advice,
                    evidence={"gate_keywords": list(rule.only_if_keywords)},
                )
            )
            continue
        finding = _check_one(rule, card, store)
        if finding is not None:
            report.findings.append(finding)
    return report


# ---------------------------------------------------------------------------
# 单规则判定（按 check_type + target 分派）
# ---------------------------------------------------------------------------

def _check_one(rule: Rule, card: PlanParamCard, store: ClauseStore) -> Optional[CheckFinding]:
    target = rule.target or ""
    if rule.check_type == "checklist" and target.startswith("appraisal_first"):
        return _check_appraisal(rule, card)
    if rule.check_type == "param_required" and target.startswith("unloading"):
        return _check_unloading(rule, card)
    if rule.check_type == "param_range" and target.startswith("adhesive_indices"):
        return _check_adhesive(rule, card, store)
    if rule.check_type == "param_range" and target.startswith("anchor_depths"):
        return _check_anchor_depth(rule, card, store)
    # 未知目标组合：兜底纪律，绝不 fail
    return CheckFinding(
        rule_id=rule.id,
        rule_name=rule.name,
        verdict=VERDICT_NEEDS_CONFIRM,
        message=f"{rule.message}（目标 {target!r} 暂不支持自动判定，请人工核对）",
        clause_id=rule.clause_id,
        advice=rule.advice,
        evidence={"gate_keywords": list(rule.only_if_keywords)},
    )


def _gate_evidence(rule: Rule) -> Dict[str, Any]:
    return {"gate_keywords": list(rule.only_if_keywords)}


def _check_appraisal(rule: Rule, card: PlanParamCard) -> CheckFinding:
    ev = card.appraisal_first
    if ev is not None:
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_PASS,
            message="方案含检测鉴定环节证据（先鉴定、后加固）",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence={"quote": ev.quote, "para": ev.para, "page": ev.page},
        )
    return CheckFinding(
        rule_id=rule.id,
        rule_name=rule.name,
        verdict=VERDICT_FAIL,
        message=rule.message + "（方案未检出鉴定结论/鉴定报告等程序性证据）",
        clause_id=rule.clause_id,
        advice=rule.advice,
        evidence=_gate_evidence(rule),
    )


def _check_unloading(rule: Rule, card: PlanParamCard) -> CheckFinding:
    if card.unloading:
        ev = card.unloading[0].evidence
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_PASS,
            message="方案写明加固前卸载/支撑构造措施",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence={"quote": ev.quote, "para": ev.para, "page": ev.page},
        )
    return CheckFinding(
        rule_id=rule.id,
        rule_name=rule.name,
        verdict=VERDICT_FAIL,
        message=rule.message + "（方案类目命中加固方法但未检出卸载/支撑描述）",
        clause_id=rule.clause_id,
        advice=rule.advice,
        evidence=_gate_evidence(rule),
    )


# ---------------------------------------------------------------------------
# R-ADH-001：胶粘剂钢对钢拉伸抗剪强度标准值（限值出自条款库 GB55021-2021-B.0.2）
# ---------------------------------------------------------------------------

def _parse_index_name(target: str) -> str:
    if "index=" in target:
        return target.split("index=", 1)[1].rstrip("]").strip()
    return ""


def _grade_limits(store: ClauseStore, clause_id: str, grade: Optional[str]) -> Optional[Tuple[float, float, Dict[str, Any]]]:
    """按胶等级返回 (适用限值下限, 上限, 依据字典)；无法建立 → None。"""
    clause = store.get(clause_id)
    if clause.status != "已核对":
        return None
    limits = clause.limits
    key_map = {"A": "grade_A", "B": "grade_B"}
    if grade not in key_map:
        return None
    key = key_map[grade]
    vals = []
    src = {}
    for table_key in (
        "steel_to_steel_shear_std_MPa_steel_pasting",
        "steel_to_steel_shear_std_MPa_frp_pasting",
    ):
        row = limits.get(table_key)
        if isinstance(row, dict) and key in row:
            vals.append(float(row[key]))
            src[table_key] = row[key]
    if not vals:
        return None
    return min(vals), max(vals), src


def _check_adhesive(rule: Rule, card: PlanParamCard, store: ClauseStore) -> CheckFinding:
    index_name = _parse_index_name(rule.target)
    items = [i for i in card.adhesive_indices if not index_name or i.kind == index_name]
    if not items:
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_FAIL,
            message=rule.message + "（方案提及结构胶类目但未标注该指标值）",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence=_gate_evidence(rule),
        )
    verdicts: List[str] = []
    evidences: List[Dict[str, Any]] = []
    messages: List[str] = []
    unresolvable = False
    for item in items:
        bounds = None
        clause_status_note = ""
        try:
            store.require_verified([rule.clause_id])
            bounds = _grade_limits(store, rule.clause_id, item.label)
        except (ClauseNotVerifiedError, KeyError):
            clause_status_note = "限值条款未核对或未登记"
        if bounds is None:
            unresolvable = True
            evidences.append({
                "quote": item.evidence.quote, "para": item.evidence.para,
                "page": item.evidence.page, "value": item.value, "unit": item.unit,
                "grade": item.label,
            })
            messages.append(
                f"{item.kind}={item.value}{item.unit}（等级{'已标注 ' + item.label if item.label else '未标注'}）"
                f"无法确定适用限值{('：' + clause_status_note) if clause_status_note else ''}"
            )
            continue
        lo, hi, src = bounds
        v = item.value
        grade_txt = f"{item.label}级胶" if item.label else "等级未标注"
        if v is None:
            verdicts.append(VERDICT_NEEDS_CONFIRM)
            messages.append(f"{item.kind} 无有效数值（{grade_txt}）")
        elif v < lo:
            verdicts.append(VERDICT_FAIL)
            messages.append(
                f"{item.kind}={v}{item.unit} 低于 {grade_txt}适用限值下限 {lo}MPa（{src}）"
            )
        elif v >= hi:
            verdicts.append(VERDICT_PASS)
            messages.append(f"{item.kind}={v}{item.unit} 不低于 {grade_txt}全部适用限值（上限 {hi}MPa）")
        else:
            verdicts.append(VERDICT_SUSPICIOUS)
            messages.append(
                f"{item.kind}={v}{item.unit} 介于 {grade_txt}适用限值 {lo}~{hi}MPa 之间（粘贴纤维复合材/粘贴钢材用途不同），疑似不足"
            )
        evidences.append({
            "quote": item.evidence.quote, "para": item.evidence.para,
            "page": item.evidence.page, "value": item.value, "unit": item.unit,
            "grade": item.label, "limit_min": lo, "limit_max": hi,
        })
    return CheckFinding(
        rule_id=rule.id,
        rule_name=rule.name,
        verdict=worst_verdict(verdicts) if verdicts else VERDICT_NEEDS_CONFIRM,
        message="；".join(messages) if messages else rule.message,
        clause_id=rule.clause_id,
        advice=rule.advice,
        evidence={"items": evidences} if len(items) > 1 else evidences[0],
    )


# ---------------------------------------------------------------------------
# R-ANCH-001：植筋锚固深度（需求下限口径见模块 docstring；表值复用 calc/common.py，
# 由 test_code_tables_match_clause_json 与条款库锁死一致）
# ---------------------------------------------------------------------------

def _alpha_spt_min(d: float) -> Optional[float]:
    """表15.2.3 该直径的全列最小 αspt（行间按表注线性内插，取内插后最小列值）。"""
    if d <= 0:
        return None
    if d <= 20.0:
        row_lo, row_hi, frac = ALPHA_SPT_ROWS["le20"], ALPHA_SPT_ROWS["le20"], 0.0
    elif d <= 25.0:
        row_lo, row_hi, frac = ALPHA_SPT_ROWS["le20"], ALPHA_SPT_ROWS["d25"], (d - 20.0) / 5.0
    elif d <= 32.0:
        row_lo, row_hi, frac = ALPHA_SPT_ROWS["d25"], ALPHA_SPT_ROWS["d32"], (d - 25.0) / 7.0
    else:
        return None  # 超出表列范围（同 calc 层口径：请直接给定 αspt）
    return min(lo + frac * (hi - lo) for lo, hi in zip(row_lo, row_hi))


def _fbd_max(grade: Optional[str], fc_grade: Optional[str]) -> Optional[float]:
    """表15.2.4 该胶等级/基材等级的最高档 fbd（最有利构造条件行）。"""
    if not grade or not fc_grade:
        return None
    key = fc_grade.strip().upper()
    vals = []
    for row in FBD_TABLE:
        if grade == "B" and "B" not in row["grade"]:
            continue
        if key in row["values"]:
            vals.append(float(row["values"][key]))
    if not vals:
        return None
    return max(vals)


def _design_param(card: PlanParamCard, kind: str) -> Optional[ValueItem]:
    for item in card.design_params:
        if item.kind == kind:
            return item
    return None


def _check_anchor_depth(rule: Rule, card: PlanParamCard, store: ClauseStore) -> CheckFinding:
    depths = list(card.anchor_depths)
    if not depths:
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_FAIL,
            message=rule.message + "（方案未标注植筋/锚固深度）",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence=_gate_evidence(rule),
        )

    # ── 建立需求下限的输入 ──
    missing: List[str] = []
    dia = _design_param(card, "植筋直径")
    grade_item = _design_param(card, "钢筋牌号")
    fc_item = _design_param(card, "混凝土强度等级")
    adh_item = _design_param(card, "胶粘剂等级")
    fy_item = _design_param(card, "钢筋强度设计值")

    d = dia.value if dia and dia.value else None
    if d is None:
        missing.append("植筋直径 d")
    fc_grade = ("C%d" % int(fc_item.value)) if fc_item and fc_item.value else None
    if fc_grade is None:
        missing.append("基材混凝土强度等级")
    adh_grade = adh_item.label if adh_item else None
    if adh_grade is None:
        missing.append("胶粘剂等级（A/B 级）")

    fy = fy_item.value if fy_item and fy_item.value else None
    fy_source = "方案标注钢筋抗拉强度设计值"
    if fy is None and grade_item and grade_item.label:
        try:
            store.require_verified([CLAUSE_REBAR_FY])
            mapping = store.get(CLAUSE_REBAR_FY).limits.get("fy_design_N_mm2") or {}
            if grade_item.label in mapping:
                fy = float(mapping[grade_item.label])
                fy_source = f"牌号 {grade_item.label} 按 {CLAUSE_REBAR_FY}（表4.2.3-1）映射"
        except (ClauseNotVerifiedError, KeyError):
            pass
    if fy is None:
        missing.append(
            f"钢筋抗拉强度设计值 fy（牌号 {grade_item.label if grade_item else '未标注'} 无法映射）"
        )

    if missing or d is None:
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_NEEDS_CONFIRM,
            message=rule.message + f"（无法建立锚固深度需求下限，缺少：{'、'.join(missing)}）；"
                    "精确复核请用 ssc calc post_rebar_anchor 补全参数验算",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence={"quote": depths[0].evidence.quote, "para": depths[0].evidence.para,
                      "missing": missing},
        )

    # ── 条文纪律门：支撑条款任一未核对 → 不产生数值判定 ──
    try:
        store.require_verified(list(ANCHOR_SUPPORT_CLAUSES))
    except (ClauseNotVerifiedError, KeyError):
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_NEEDS_CONFIRM,
            message=rule.message + "（锚固支撑条款未全部核对，不产生自动数值判定）",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence={"quote": depths[0].evidence.quote, "para": depths[0].evidence.para},
        )

    alpha_min = _alpha_spt_min(d)
    fbd_top = _fbd_max(adh_grade, fc_grade)
    if alpha_min is None or fbd_top is None:
        reason = "植筋直径超出表15.2.3 范围" if alpha_min is None else (
            f"表15.2.4 无 {adh_grade}级胶/{fc_grade} 列值"
        )
        return CheckFinding(
            rule_id=rule.id,
            rule_name=rule.name,
            verdict=VERDICT_NEEDS_CONFIRM,
            message=rule.message + f"（无法建立需求下限：{reason}）",
            clause_id=rule.clause_id,
            advice=rule.advice,
            evidence={"quote": depths[0].evidence.quote, "para": depths[0].evidence.para},
        )

    # 需求下限（最有利假设，系数出处见模块 docstring 与命名常量表）
    ls_min = ANCHOR_FORMULA_COEF * alpha_min * d * fy / fbd_top
    ld_req_lower = ANCHOR_PSI_BR_MIN * ANCHOR_PSI_W_MIN * ANCHOR_PSI_T_MIN * ANCHOR_PSI_AE_MIN * ls_min
    assumptions = [
        f"αspt 取表15.2.3 直径 d={d:g} 全列最小 {alpha_min:g}",
        f"fbd 取表15.2.4 {adh_grade}级胶/{fc_grade} 最高档 {fbd_top:g}MPa",
        "ψbr=ψT=%g（15.2.5 下限）、ψw=%g（15.2.5 下限）、ψae=%g（15.2.2 非抗震）"
        % (ANCHOR_PSI_BR_MIN, ANCHOR_PSI_W_MIN, ANCHOR_PSI_AE_MIN),
        fy_source,
    ]

    verdicts: List[str] = []
    evidences: List[Dict[str, Any]] = []
    messages: List[str] = []
    for item in depths:
        v = item.value
        ev = {
            "quote": item.evidence.quote, "para": item.evidence.para,
            "page": item.evidence.page, "stated_mm": v,
            "ld_required_lower_mm": round(ld_req_lower, 2), "assumptions": assumptions,
        }
        evidences.append(ev)
        if v is None:
            verdicts.append(VERDICT_NEEDS_CONFIRM)
            messages.append(f"{item.kind}锚固深度无有效数值")
        elif v < ld_req_lower:
            verdicts.append(VERDICT_FAIL)
            messages.append(
                f"{item.kind}锚固深度 {v:g}mm 低于最有利假设下的需求下限 {ld_req_lower:.1f}mm，"
                "无论实际构造条件如何均不满足（式15.2.2-2：ld≥ψN·ψae·ls）"
            )
        else:
            verdicts.append(VERDICT_PASS)
            messages.append(
                f"{item.kind}锚固深度 {v:g}mm 不低于最有利假设下的需求下限 {ld_req_lower:.1f}mm"
                "（筛查通过；精确复核请用 ssc calc post_rebar_anchor）"
            )
    return CheckFinding(
        rule_id=rule.id,
        rule_name=rule.name,
        verdict=worst_verdict(verdicts),
        message="；".join(messages),
        clause_id=rule.clause_id,
        advice=rule.advice,
        evidence={"items": evidences} if len(depths) > 1 else evidences[0],
    )
