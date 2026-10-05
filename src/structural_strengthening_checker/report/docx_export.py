"""报告导出（docx）：验算书（FR-D1）+ 方案核查报告（FR-D2）。M4 实装。

纪律（plan/02 FR-D3/D4）：
- 报告强制免责声明（DISCLAIMER 常量，落每份产物末尾）；
- 产物 0 外链：全部内容由 python-docx 从空白文档写就，不插图片、不加超链接、
  不引用网络模板——tests/test_report.py 对产物全部包件关系断言 is_external=False。
- 签署栏（FR-D1/D2）：验算书=计算/校核/审核；核查报告=核查/复核/批准。

依赖惰性导入，缺失抛 MissingExtraError（tests/test_lazy_deps 锁死）。
导出签名（plan/04 §二）扩展说明：export_check_report 增加 card=None 可选参数
（携带 sha256 等文档元信息；M2 metrics 增补同款兼容扩展），不传也能出完整报告。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..checking.engine import VERDICT_LABELS
from ..core.errors import MissingExtraError

DISCLAIMER = (
    "本报告由结构加固验算与加固方案核查工具生成，仅作辅助验算与核查用途，"
    "不替代正式设计文件、施工图审查与竣工验收。"
)

_SIGN_ROWS_CALC = (("计算", ""), ("校核", ""), ("审核", ""))
_SIGN_ROWS_CHECK = (("核查", ""), ("复核", ""), ("批准", ""))


def _import_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError("report", "docx 报告导出") from exc
    return docx


def _fmt_num(v: Any) -> str:
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, float):
        text = f"{v:.6g}"
        return text
    return str(v)


def _add_sign_block(document, rows) -> None:
    document.add_heading("签署栏", level=1)
    table = document.add_table(rows=len(rows), cols=3)
    table.style = "Table Grid"
    for i, (role, _blank) in enumerate(rows):
        cells = table.rows[i].cells
        cells[0].text = role
        cells[1].text = "签名："
        cells[2].text = "日期："
    document.add_paragraph("")


def _add_disclaimer(document) -> None:
    document.add_heading("免责声明", level=1)
    document.add_paragraph(DISCLAIMER)


def _schema_of(module_id: str) -> Dict[str, Dict[str, Any]]:
    """参数含义/单位取自模块注册表 schema（注册表未加载时退化为空，仅回显符号值）。"""
    try:
        from ..core.engine import get_module

        return get_module(module_id).param_schema
    except Exception:  # noqa: BLE001  报告层不因元信息缺失失败
        return {}


def _evidence_lines(evidence: Dict[str, Any]) -> List[str]:
    """核查证据 → 可读行（与 CLI _print_finding 同口径，报告版精简）。"""
    lines: List[str] = []
    if not evidence:
        return lines
    if "items" in evidence:
        for i, item in enumerate(evidence["items"], 1):
            loc = f"段 {item['para']}" if item.get("para") else ""
            quote = (item.get("quote") or "").replace("\n", " ")
            line = f"证据{i}：{quote}（{loc}）" if quote else f"证据{i}（{loc}）"
            extras = {
                k: v for k, v in item.items()
                if k not in ("quote", "para", "page") and v is not None
            }
            if extras:
                line += "；数值 " + ", ".join(f"{k}={_fmt_num(v)}" for k, v in extras.items())
            lines.append(line)
        return lines
    quote = (evidence.get("quote") or "").replace("\n", " ")
    loc = f"段 {evidence['para']}" if evidence.get("para") else ""
    if quote:
        lines.append(f"证据：{quote}（{loc}）")
    extras = {
        k: v for k, v in evidence.items()
        if k not in ("quote", "para", "page", "assumptions") and v is not None
    }
    if extras:
        lines.append("数值 " + ", ".join(f"{k}={_fmt_num(v)}" for k, v in extras.items()))
    for a in evidence.get("assumptions") or []:
        lines.append(f"假设：{a}")
    return lines


# ---------------------------------------------------------------------------
# FR-D1 验算书
# ---------------------------------------------------------------------------

def export_calc_book(result: Dict[str, Any], out_path: Path) -> Path:
    """验算书 docx：输入参数/计算过程/依据条款/结论/签署栏/免责声明（FR-D1）。

    result 为 CalcResult 形状 dict（run_calc 产物）。返回写入路径。
    """
    docx = _import_docx()
    document = docx.Document()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    module_id = result.get("module", "")
    document.add_heading(f"验算书：{module_id}", level=0)

    document.add_heading("一、验算结论", level=1)
    verdict = result.get("verdict", "")
    document.add_paragraph(f"验算结论：{verdict}")
    cap = result.get("capacity") or {}
    cap_v = cap.get("value")
    document.add_paragraph(
        f"承载力特征值：{'N/A' if cap_v is None else _fmt_num(cap_v)} {cap.get('unit', '')}"
    )
    ratio = result.get("ratio") or {}
    ratio_v = ratio.get("value")
    document.add_paragraph(
        f"效应比（{ratio.get('meaning', '')}）：{'N/A' if ratio_v is None else _fmt_num(ratio_v)}"
    )

    document.add_heading("二、输入参数", level=1)
    schema = _schema_of(module_id)
    inputs = result.get("inputs") or {}
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    header = table.rows[0].cells
    header[0].text = "符号"
    header[1].text = "数值"
    header[2].text = "含义（单位）"
    for sym, value in inputs.items():
        row = table.add_row().cells
        row[0].text = str(sym)
        row[1].text = _fmt_num(value)
        info = schema.get(sym) or {}
        meaning = info.get("meaning", "")
        unit = info.get("unit", "")
        row[2].text = f"{meaning}（{unit}）" if meaning else f"（{unit}）" if unit else ""

    document.add_heading("三、计算过程", level=1)
    steps = result.get("steps") or []
    if not steps:
        document.add_paragraph("（无计算步骤记录）")
    for s in steps:
        head = f"步骤{s.get('no')} [{s.get('formula_ref', '')}] {s.get('expr', '')}"
        document.add_paragraph(head, style="List Number")
        values = s.get("values") or {}
        if values:
            document.add_paragraph(
                "数值：" + ", ".join(f"{k}={_fmt_num(v)}" for k, v in values.items())
                + (f"（{s['unit']}）" if s.get("unit") else "")
            )
        clause_ids = s.get("clause_ids") or []
        if clause_ids:
            document.add_paragraph("依据：" + "、".join(clause_ids))

    document.add_heading("四、依据条款", level=1)
    clauses_used = result.get("clauses_used") or []
    if not clauses_used:
        document.add_paragraph("（无）")
    for cid in clauses_used:
        document.add_paragraph(str(cid), style="List Bullet")

    document.add_heading("五、提示与警告", level=1)
    warnings = result.get("warnings") or []
    if not warnings:
        document.add_paragraph("（无）")
    for w in warnings:
        document.add_paragraph(str(w), style="List Bullet")

    _add_sign_block(document, _SIGN_ROWS_CALC)
    _add_disclaimer(document)
    document.save(str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# FR-D2 方案核查报告
# ---------------------------------------------------------------------------

def export_check_report(report: Any, out_path: Path, card: Any = None) -> Path:
    """方案核查报告 docx：问题清单+证据链+整改建议+签署栏+免责声明（FR-D2）。

    report 为 checking.engine.CheckReport；card 可选（PlanParamCard，取 sha256 等文档元信息）。
    返回写入路径。
    """
    docx = _import_docx()
    document = docx.Document()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    document.add_heading("加固方案核查报告", level=0)
    document.add_paragraph(f"核查文档：{report.doc_name}")
    if card is not None and getattr(card, "doc_sha256", None):
        document.add_paragraph(f"文档 sha256：{card.doc_sha256}")

    document.add_heading("一、核查概要", level=1)
    summary = report.summary()
    document.add_paragraph(
        "汇总：不符合 {fail} / 疑似 {suspicious} / 待人工确认 {needs_confirm} / 通过 {pass}".format(
            **summary
        )
    )
    if report.degraded:
        document.add_paragraph(
            "解析状态：解析失败/无可解析段落，全部规则整体降级待人工确认（不产生任何自动 fail）。"
        )

    document.add_heading("二、核查明细", level=1)
    if not report.findings:
        document.add_paragraph("（无核查结论）")
    for i, f in enumerate(report.findings, 1):
        label = VERDICT_LABELS.get(f.verdict, f.verdict)
        document.add_paragraph(
            f"{i}. [{f.verdict} {label}] {f.rule_id} {f.rule_name}", style="List Number"
        )
        document.add_paragraph(f"结论：{f.message}")
        document.add_paragraph(f"依据：{f.clause_id or '（文档级证据问题）'}")
        if f.advice:
            document.add_paragraph(f"建议：{f.advice}")
        for line in _evidence_lines(f.evidence or {}):
            document.add_paragraph(line)

    document.add_heading("三、整改建议汇总", level=1)
    advices = [f.advice for f in report.findings if f.verdict != "pass" and f.advice]
    if not advices:
        document.add_paragraph("（非 pass 结论均无模板建议，见明细逐条意见）")
    seen: List[str] = []
    for a in advices:
        if a not in seen:
            seen.append(a)
            document.add_paragraph(a, style="List Number")

    _add_sign_block(document, _SIGN_ROWS_CHECK)
    _add_disclaimer(document)
    document.save(str(out_path))
    return out_path
