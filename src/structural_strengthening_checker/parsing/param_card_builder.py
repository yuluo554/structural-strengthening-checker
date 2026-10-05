"""解析层：docx/PDF 段落 → 方案参数卡（规则优先：正则+槽位，M3 实装）。

抽取纪律（FR-B3/FR-B5，plan/02 §三）：
- 全离线规则抽取，无 LLM；每个抽取值必须带 evidence（page/para/quote）；
- quote 一律取自 Para 原文（构造上保证是 source_text 子串）；仍以 evidence_issues()
  独立复核，非子串的项丢弃并记入 card.notes（check_plan 将其降级 needs_confirm）；
- 抽不出的槽位保持为空，绝不猜测——缺失由核查层按各规则语义处理（未标注型规则判
  fail，无法建立限值的判 needs_confirm），解析层宁缺勿错。

模式表为启发式词表：覆盖合成方案语料与常见方案措辞（"不应小于/≥/设计值"等），
新词表项须带单测。appraisal_first 刻意不用裸词"鉴定/检测"——基线文档材料段存在
"安全性鉴定要求"（GB 50728 引文语境），裸词会把材料合规表述误当鉴定程序证据（M3 实测）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .docx_text import Para
from .param_card import Evidence, MethodItem, PlanParamCard, ValueItem

# ── 加固方法词表（name=归一方法名，keywords=按出现顺序优先匹配的触发词） ──
METHOD_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("粘贴碳纤维复合材加固", ("粘贴碳纤维", "碳纤维复合材", "碳纤维布", "碳纤维板", "碳纤维")),
    ("粘贴钢板加固", ("粘贴钢板", "粘钢")),
    ("增大截面加固法", ("增大截面",)),
    ("置换混凝土加固法", ("置换混凝土",)),
    ("外包型钢加固法", ("外包型钢", "外粘型钢")),
    ("植筋（后锚固连接）", ("植筋",)),
    ("锚栓连接", ("锚栓",)),
]

# ── 胶粘剂安全性能指标名（plan/04 §1.4 adhesive_indices；限值依据 GB55021-2021-B.0.2） ──
ADHESIVE_INDEX_NAMES = (
    "钢对钢拉伸抗剪强度标准值",
    "钢对钢对接粘结抗拉强度",
    "钢对混凝土正拉粘结强度",
    "正拉粘结强度",
)

# appraisal_first 证据词（程序性鉴定证据；刻意排除裸词"鉴定/检测"）
APPRAISAL_PATTERNS = ("检测鉴定", "鉴定报告", "鉴定结论", "抗震鉴定", "先检测", "鉴定机构")

_RE_CONCRETE_GRADE = re.compile(r"混凝土(?:强度)?等级\s*[:：]?\s*C\s*([0-9]{2,3})")
_RE_REBAR_GRADE = re.compile(r"\b(HPB300|HRB335|HRBF335|HRB400|HRBF400|RRB400|HRB500|HRBF500)\b")
_RE_ADH_GRADE = re.compile(r"([AB])\s*级\s*(?:改性环氧|环氧|聚氨酯|无机)?\s*(?:结构)?(?:胶粘剂|胶|结构胶)")
_NUM = r"([0-9]+(?:\.[0-9]+)?)"
_RE_ADH_INDEX = [
    (name, re.compile(re.escape(name) + r"[^0-9.\-]{0,6}" + _NUM + r"\s*(MPa|MPa|N/mm²|兆帕)?"))
    for name in ADHESIVE_INDEX_NAMES
]
_RE_ANCHOR_DEPTH = re.compile(
    r"(?:锚固深度|植筋深度|锚固长度)(?:设计值)?[^\d]{0,6}" + _NUM + r"\s*(?:mm|毫米)"
)
_RE_REBAR_DIA = re.compile(r"(?:公称直径|直径)\s*[:：]?\s*" + _NUM + r"\s*(?:mm|毫米)")
_RE_FY_DESIGN = re.compile(
    r"(?:抗拉强度设计值|强度设计值)\s*[:：]?\s*" + _NUM + r"\s*(?:MPa|N/mm²|兆帕)"
)
_RE_UNLOAD = re.compile(r"卸载|卸荷|临时支撑|设置支撑")
_RE_CRACK = re.compile(r"裂缝[^。；;]{0,40}?(表面封闭|压力注[浆射]|注射|灌缝|修补胶泥|密封膏|修补)")


def _mk_evidence(para: Para) -> Evidence:
    return Evidence(page=para.page, para=para.index, quote=para.text)


def _safe_add(items: List[ValueItem], item: ValueItem, source_text: str, notes: List[str]) -> None:
    """防幻觉闸：quote 非原文子串 → 丢弃该项并留痕（FR-B5）。"""
    quote = item.evidence.quote
    if quote and quote not in source_text:
        notes.append(
            f"丢弃 {item.kind}{('/' + item.label) if item.label else ''}: 摘录不是原文子串"
        )
        return
    items.append(item)


def build_param_card(
    paras: List[Para], doc_name: str = "", doc_sha256: str = None
) -> PlanParamCard:
    """段落列表 → 参数卡（正则+槽位；全部证据取自原文段落）。"""
    source_text = "\n".join(p.text for p in paras)
    card = PlanParamCard(doc_name=doc_name, doc_sha256=doc_sha256, source_text=source_text)
    notes: List[str] = []

    for para in paras:
        text = para.text

        # ── 加固方法 ──
        for name, keywords in METHOD_KEYWORDS:
            if any(kw in text for kw in keywords) and not any(
                m.name == name for m in card.methods
            ):
                card.methods.append(MethodItem(name=name, evidence=_mk_evidence(para)))

        # ── 材料：混凝土强度等级 / 钢筋牌号 / 胶粘剂等级 ──
        for m in _RE_CONCRETE_GRADE.finditer(text):
            grade = "C%s" % m.group(1)
            _safe_add(
                card.materials,
                ValueItem(kind="混凝土", value=float(m.group(1)), unit="C", label=grade,
                          confidence=1.0, evidence=_mk_evidence(para)),
                source_text, notes,
            )
            _safe_add(
                card.design_params,
                ValueItem(kind="混凝土强度等级", value=float(m.group(1)), unit="C", label=grade,
                          confidence=1.0, evidence=_mk_evidence(para)),
                source_text, notes,
            )
        is_anchor_ctx = ("植筋" in text) or ("锚栓" in text)
        for m in _RE_REBAR_GRADE.finditer(text):
            grade = m.group(1)
            _safe_add(
                card.materials,
                ValueItem(kind="钢材", label=grade, confidence=1.0, evidence=_mk_evidence(para)),
                source_text, notes,
            )
            if is_anchor_ctx:
                _safe_add(
                    card.design_params,
                    ValueItem(kind="钢筋牌号", label=grade, confidence=1.0,
                              evidence=_mk_evidence(para)),
                    source_text, notes,
                )
        for m in _RE_ADH_GRADE.finditer(text):
            grade = m.group(1)
            _safe_add(
                card.materials,
                ValueItem(kind="胶粘剂", label=grade + "级", confidence=1.0,
                          evidence=_mk_evidence(para)),
                source_text, notes,
            )
            _safe_add(
                card.design_params,
                ValueItem(kind="胶粘剂等级", label=grade, confidence=1.0,
                          evidence=_mk_evidence(para)),
                source_text, notes,
            )

        # ── 胶粘剂安全性能指标（label=同段检出的胶等级，供核查层选限值） ──
        adh_grade = None
        m_grade = _RE_ADH_GRADE.search(text)
        if m_grade:
            adh_grade = m_grade.group(1)
        for name, rx in _RE_ADH_INDEX:
            for m in rx.finditer(text):
                unit = m.group(2) or "MPa"
                if unit in ("N/mm²", "兆帕"):
                    unit = "MPa"
                _safe_add(
                    card.adhesive_indices,
                    ValueItem(kind=name, value=float(m.group(1)), unit=unit, label=adh_grade,
                              confidence=1.0 if m.group(2) else 0.8,
                              evidence=_mk_evidence(para)),
                    source_text, notes,
                )

        # ── 锚固/植筋深度 ──
        for m in _RE_ANCHOR_DEPTH.finditer(text):
            element = "植筋" if "植筋" in text else ("锚栓" if "锚栓" in text else "未指明构件")
            _safe_add(
                card.anchor_depths,
                ValueItem(kind=element, value=float(m.group(1)), unit="mm", label=element,
                          confidence=1.0, evidence=_mk_evidence(para)),
                source_text, notes,
            )

        # ── 植筋设计参数（直径/牌号/强度设计值） ──
        if is_anchor_ctx:
            for m in _RE_REBAR_DIA.finditer(text):
                _safe_add(
                    card.design_params,
                    ValueItem(kind="植筋直径", value=float(m.group(1)), unit="mm",
                              confidence=1.0, evidence=_mk_evidence(para)),
                    source_text, notes,
                )
            for m in _RE_FY_DESIGN.finditer(text):
                _safe_add(
                    card.design_params,
                    ValueItem(kind="钢筋强度设计值", value=float(m.group(1)), unit="MPa",
                              confidence=1.0, evidence=_mk_evidence(para)),
                    source_text, notes,
                )

        # ── 卸载/支撑（每段最多记一项） ──
        if _RE_UNLOAD.search(text):
            kind = "卸载" if ("卸载" in text or "卸荷" in text) else "支撑"
            _safe_add(
                card.unloading,
                ValueItem(kind=kind, confidence=1.0, evidence=_mk_evidence(para)),
                source_text, notes,
            )

        # ── 裂缝修补方式（M3 仅抽取留证；对应规则为 P1/P2 扩展项） ──
        m_crack = _RE_CRACK.search(text)
        if m_crack:
            _safe_add(
                card.crack_repairs,
                ValueItem(kind="裂缝修补", label=m_crack.group(1), confidence=0.8,
                          evidence=_mk_evidence(para)),
                source_text, notes,
            )

        # ── 先鉴定后加固（程序性证据） ──
        if card.appraisal_first is None and any(pw in text for pw in APPRAISAL_PATTERNS):
            card.appraisal_first = _mk_evidence(para)

    card.notes = notes
    return card
