"""PySide6 四页签主窗口（M5 实装）：验算表单 / 方案核查 / 检查单 / 报告。

消费面纪律（plan/06 M5 决策，HANDOFF-M5 §二.2"不另起第二套行为"）：
- 验算表单：core.engine.run_calc（门控→校验→计算与 CLI 同一入口）；
- 方案核查：cli._run_check_pipeline（ssc check / ssc report check 唯一共用核查路径），
  JSON 导出用 cli._check_report_json（与 ssc check --report 同形状）；
- 检查单：ChecklistStore + cli._auto_text_suggestion（宁缺勿错，不自动给"不符合"）
  + cli._render_filled（渲染与 ssc checklist --fill 同一函数）；
- 报告：report.docx_export.export_calc_book / export_check_report 直接入库函数；
- 判定标签 checking.engine.VERDICT_LABELS、免责声明 cli.DISCLAIMER 均单一出口。

本模块只在 gui.app._import_qt() 成功后被导入（PySide6 顶层导入），缺 gui extras 时
gui.app 仍可安全 import（test_lazy_deps 守门）。错误处理：SSCError/ValidationError →
界面内联红字或消息框（映射 CLI 退出码语义 2/3），绝不裸 traceback；windowed exe 无控制台。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from .. import __version__
from ..calc import EXPECTED_MODULES  # noqa: F401  触发 4 模块注册副作用
from ..checking.checklist_gb55021 import ChecklistStore
from ..checking.engine import VERDICT_LABELS
from ..checking.rules import RuleStore
from ..cli import (
    DISCLAIMER,
    _auto_text_suggestion,
    _check_report_json,
    _render_filled,
    _run_check_pipeline,
)
from ..core.clauses import ClauseStore
from ..core.engine import CALC_REGISTRY, run_calc
from ..core.errors import ClauseNotVerifiedError, MissingExtraError, SSCError, ValidationError
from ..core.paths import find_data_dir

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INPUT = 2

# 判定颜色（呈现层；标签文本用 VERDICT_LABELS 单一出口）
VERDICT_COLORS = {
    "fail": "#c62828",
    "suspicious": "#ef6c00",
    "needs_confirm": "#546e7a",
    "pass": "#2e7d32",
}
CALC_VERDICT_COLORS = {
    "不满足": "#c62828",
    "需调整": "#ef6c00",
    "满足": "#2e7d32",
}

PLAN_FILE_FILTER = "加固方案文件 (*.docx *.pdf)"
JSON_FILE_FILTER = "参数卡 JSON (*.json)"
DOCX_FILTER = "Word 文档 (*.docx)"

EXIT_CODE_NAME = {EXIT_OK: "0（成功，结论看报告）", EXIT_ERROR: "1（一般错误）", EXIT_INPUT: "2（输入/缺依赖）"}


def _range_tip(spec: Dict[str, Any]) -> str:
    rng = spec.get("range") or {}
    lo, hi, excl = rng.get("min"), rng.get("max"), bool(rng.get("exclusive", False))
    parts = []
    if lo is not None:
        parts.append(("> %g" if excl else ">= %g") % lo)
    if hi is not None:
        parts.append(("< %g" if excl else "<= %g") % hi)
    return "；合法范围 " + " 且 ".join(parts) if parts else ""


def _evidence_text(ev: Dict[str, Any]) -> str:
    """证据字典 → 可读文本（与 CLI _print_finding 同口径的呈现层格式化）。"""
    lines: List[str] = []
    if not ev:
        return "（无证据）"
    items = ev.get("items") if isinstance(ev, dict) else None
    if items:
        for i, item in enumerate(items, 1):
            lines.append(f"证据{i}:")
            lines.extend(_evidence_text(item).rstrip("\n").splitlines())
        tail = {k: v for k, v in ev.items() if k != "items" and v is not None}
        if tail:
            lines.append("汇总数值: " + json.dumps(tail, ensure_ascii=False))
        return "\n".join(lines)
    if not isinstance(ev, dict):
        return json.dumps(ev, ensure_ascii=False)
    quote = (ev.get("quote") or "").replace("\n", " ")
    loc = []
    if ev.get("para") is not None:
        loc.append(f"段 {ev['para']}")
    if ev.get("page") is not None:
        loc.append(f"页 {ev['page']}")
    if quote:
        lines.append(f"原文: “{quote}”（{'，'.join(loc)}）" if loc else f"原文: “{quote}”")
    extras = {
        k: v for k, v in ev.items() if k not in ("quote", "para", "page", "assumptions") and v is not None
    }
    if extras:
        lines.append("数值: " + json.dumps(extras, ensure_ascii=False))
    for a in ev.get("assumptions") or []:
        lines.append(f"假设: {a}")
    return "\n".join(lines) if lines else "（无证据）"


# ---------------------------------------------------------------------------
# 页签 1：验算表单
# ---------------------------------------------------------------------------

class CalcTab(QtWidgets.QWidget):
    """模块选择 + param_schema 动态表单 + 三态结论/逐步计算展示。

    参数卡 JSON 与 ssc calc --input 同格式（扁平 {参数名: 数值}），CLI 与 GUI 共用。
    """

    def __init__(self, data_dir: Path, store: ClauseStore, parent=None) -> None:
        super().__init__(parent)
        self._data_dir = data_dir
        self._store = store
        self._result: Optional[Dict[str, Any]] = None
        self._result_module: Optional[str] = None
        self.edits: Dict[str, QtWidgets.QLineEdit] = {}

        root = QtWidgets.QHBoxLayout(self)
        left = QtWidgets.QVBoxLayout()

        head = QtWidgets.QHBoxLayout()
        head.addWidget(QtWidgets.QLabel("验算模块"))
        self.module_combo = QtWidgets.QComboBox()
        for mid in sorted(CALC_REGISTRY):
            self.module_combo.addItem(f"{mid} — {CALC_REGISTRY[mid].name}", userData=mid)
        head.addWidget(self.module_combo, 1)
        left.addLayout(head)

        self.form_scroll = QtWidgets.QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        form_host = QtWidgets.QWidget()
        self.form_layout = QtWidgets.QFormLayout(form_host)
        self.form_scroll.setWidget(form_host)
        left.addWidget(self.form_scroll, 1)

        btns = QtWidgets.QHBoxLayout()
        b_load = QtWidgets.QPushButton("载入参数卡 JSON…")
        b_save = QtWidgets.QPushButton("保存参数卡 JSON…")
        b_run = QtWidgets.QPushButton("开始验算")
        b_docx = QtWidgets.QPushButton("导出验算书 docx…")
        b_load.clicked.connect(self.load_input_json)
        b_save.clicked.connect(self.save_input_json)
        b_run.clicked.connect(self.run_calc_now)
        b_docx.clicked.connect(self.export_calc_book)
        for b in (b_load, b_save, b_run, b_docx):
            btns.addWidget(b)
        left.addLayout(btns)
        root.addLayout(left, 5)

        right = QtWidgets.QVBoxLayout()
        self.verdict_label = QtWidgets.QLabel("（尚未验算）")
        self.verdict_label.setStyleSheet("font-size: 15pt; font-weight: bold;")
        right.addWidget(self.verdict_label)
        self.feature_label = QtWidgets.QLabel("")
        self.feature_label.setWordWrap(True)
        right.addWidget(self.feature_label)
        self.result_browser = QtWidgets.QTextBrowser()
        right.addWidget(self.result_browser, 1)
        root.addLayout(right, 6)

        self.module_combo.currentIndexChanged.connect(self._rebuild_form)
        self._rebuild_form()

    # ---- 表单构建与参数收集 ----

    def _rebuild_form(self) -> None:
        module = CALC_REGISTRY[self.module_combo.currentData()]
        self.edits.clear()
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for key, spec in module.param_schema.items():
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText(f"{spec.get('unit', '')}")
            optional = not spec.get("required", True)
            label = f"{key}（{spec.get('meaning', '')}，{spec.get('unit', '')}）"
            if optional:
                label += "［可选］"
            tip = _range_tip(spec)
            if tip:
                edit.setToolTip(tip)
            self.form_layout.addRow(QtWidgets.QLabel(label), edit)
            self.edits[key] = edit

    def _collect_params(self) -> Dict[str, Any]:
        module = CALC_REGISTRY[self.module_combo.currentData()]
        params: Dict[str, Any] = {}
        for key, edit in self.edits.items():
            text = edit.text().strip()
            if not text:
                continue
            try:
                params[key] = float(text)
            except ValueError:
                raise ValidationError(f"参数 {key} 不是数值: {text!r}")
        missing = [
            k for k, spec in module.param_schema.items()
            if spec.get("required", True) and k not in params
        ]
        if missing:
            raise ValidationError("缺少必填参数: " + ", ".join(missing))
        return params

    def _fill_form(self, params: Dict[str, Any]) -> None:
        for key, edit in self.edits.items():
            if key in params:
                edit.setText(str(params[key]))

    # ---- 动作 ----

    def load_input_json(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "载入参数卡", "", JSON_FILE_FILTER)
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            self._show_error(f"无法读取参数卡: {exc}")
            return
        except json.JSONDecodeError as exc:
            self._show_error(f"参数卡不是合法 JSON: {exc}")
            return
        if not isinstance(data, dict):
            self._show_error("参数卡应为扁平 {参数名: 数值} JSON（与 ssc calc --input 同格式）")
            return
        params = data.get("params") if isinstance(data.get("params"), dict) else data
        unknown = [k for k in params if k not in self.edits]
        self._fill_form({k: v for k, v in params.items() if k in self.edits})
        self._show_info(
            f"已载入 {sum(1 for k in params if k in self.edits)} 项参数"
            + (f"（忽略非本模块字段: {', '.join(unknown)}）" if unknown else "")
        )

    def save_input_json(self) -> None:
        try:
            params = self._collect_params()
        except ValidationError as exc:
            self._show_error(f"当前表单无法作为参数卡保存：{exc}")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "保存参数卡", "params.json", JSON_FILE_FILTER)
        if not path:
            return
        Path(path).write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
        self._show_info(f"参数卡已保存: {path}（可与 ssc calc / ssc report calc 共用）")

    def run_calc_now(self) -> bool:
        module_id = self.module_combo.currentData()
        try:
            params = self._collect_params()
            result = run_calc(module_id, params, self._store)
        except ValidationError as exc:
            self._show_error(f"参数校验未通过（exit 2 口径）：{exc}")
            return False
        except ClauseNotVerifiedError as exc:
            self._show_gate(str(exc))
            return False
        except SSCError as exc:
            self._show_error(f"验算失败: {exc}")
            return False
        self._result = result
        self._result_module = module_id
        self._render_result(module_id, result)
        return True

    def export_calc_book(self) -> Optional[Path]:
        if self._result is None:
            self._show_info("请先完成一次验算，再导出验算书。")
            return None
        default = f"calc_book_{self._result_module or 'result'}.docx"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出验算书", default, DOCX_FILTER)
        if not path:
            return None
        try:
            from ..report.docx_export import export_calc_book

            out = export_calc_book(self._result, Path(path))
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.warning(self, "缺少依赖", str(exc))
            return None
        self._show_info(f"验算书 docx 已写入: {out}")
        return out

    # ---- 展示 ----

    def _render_result(self, module_id: str, result: Dict[str, Any]) -> None:
        verdict = result.get("verdict", "")
        color = CALC_VERDICT_COLORS.get(verdict, "#37474f")
        self.verdict_label.setText(f"验算结论：{verdict}")
        self.verdict_label.setStyleSheet(f"font-size: 15pt; font-weight: bold; color: {color};")
        cap = result.get("capacity") or {}
        ratio = result.get("ratio") or {}
        cap_text = (
            f"{cap['value']:.4g} {cap.get('unit', '')}" if cap.get("value") is not None else "N/A"
        )
        ratio_text = (
            f"{ratio['value']:.3f}" if ratio.get("value") is not None else "N/A"
        )
        self.feature_label.setText(
            f"承载力/特征值 = {cap_text}    效应比（{ratio.get('meaning', '')}）= {ratio_text}"
        )
        lines: List[str] = []
        metrics = result.get("metrics") or {}
        if metrics:
            lines.append("── 特征量（metrics）──")
            for k, v in metrics.items():
                lines.append(f"  {k} = {v}")
        steps = result.get("steps") or []
        if steps:
            lines.append("── 计算过程 ──")
            for s in steps:
                lines.append(f"第{s.get('no')}步 {s.get('formula_ref', '')}  {s.get('expr', '')}")
                vals = s.get("values") or {}
                if vals:
                    lines.append("    " + ", ".join(f"{k} = {v}" for k, v in vals.items()))
                cl = "、".join(s.get("clause_ids") or [])
                unit = s.get("unit") or ""
                if cl or unit:
                    lines.append(f"    （单位 {unit}；依据 {cl}）" if unit else f"    （依据 {cl}）")
        used = result.get("clauses_used") or []
        if used:
            lines.append("── 依据条款 ──")
            for c in used:
                lines.append(f"  {c}")
        warnings = result.get("warnings") or []
        if warnings:
            lines.append("── 提示（不改变判定）──")
            for w in warnings:
                lines.append(f"  [提示] {w}")
        lines.append("")
        lines.append(DISCLAIMER)
        self.result_browser.setPlainText("\n".join(lines))

    def _show_error(self, text: str) -> None:
        self.verdict_label.setText("未得出结论")
        self.verdict_label.setStyleSheet("font-size: 15pt; font-weight: bold; color: #c62828;")
        self.feature_label.setText("")
        self.result_browser.setPlainText(text)

    def _show_gate(self, text: str) -> None:
        self.verdict_label.setText("条文门控拦截（exit 3 口径）")
        self.verdict_label.setStyleSheet("font-size: 15pt; font-weight: bold; color: #ef6c00;")
        self.feature_label.setText("")
        self.result_browser.setPlainText(
            text + "\n\n按条文纪律红线，status=待核对的条款不得进入计算路径；"
                   "请先按 plan/05 核对流程完成条文入库。"
        )

    def _show_info(self, text: str) -> None:
        self.result_browser.append(text)


# ---------------------------------------------------------------------------
# 页签 2：方案核查
# ---------------------------------------------------------------------------

class CheckTab(QtWidgets.QWidget):
    """文件选择 + 三级判定明细（树）+ 证据链详情（文本）+ 报告导出。

    核查走 cli._run_check_pipeline 唯一共用路径；报告导出与 ssc check --report 同形状
    （check_report.json + check_report.docx，缺 report extras 时 JSON 照写+提示）。
    """

    def __init__(self, data_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._data_dir = data_dir
        self._pipeline: Optional[Tuple[Any, Any, List[Any]]] = None

        root = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("方案文件"))
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("选择 .docx / .pdf 加固方案文件")
        b_browse = QtWidgets.QPushButton("浏览…")
        b_run = QtWidgets.QPushButton("开始核查")
        b_export = QtWidgets.QPushButton("导出报告…")
        b_browse.clicked.connect(self._browse)
        b_run.clicked.connect(self.run_check_now)
        b_export.clicked.connect(self.export_report_dir)
        for w in (self.path_edit, b_browse, b_run, b_export):
            row.addWidget(w)
        root.addLayout(row)

        self.banner_label = QtWidgets.QLabel("")
        self.banner_label.setWordWrap(True)
        self.banner_label.setStyleSheet("color: #c62828;")
        self.banner_label.hide()
        root.addWidget(self.banner_label)

        self.summary_label = QtWidgets.QLabel("（尚未核查）")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["判定", "规则", "名称", "结论", "依据条款"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemSelectionChanged.connect(self._show_detail)
        self.detail_browser = QtWidgets.QTextBrowser()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.detail_browser)
        splitter.setSizes([380, 220])
        root.addWidget(splitter, 1)
        self.findings: List[Any] = []

    def _browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择方案文件", "", PLAN_FILE_FILTER)
        if path:
            self.path_edit.setText(path)

    def run_check_now(self) -> bool:
        text = self.path_edit.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "方案核查", "请先选择方案文件（.docx/.pdf）。")
            return False
        plan_path = Path(text)
        try:
            report, card, paras, parse_failed, parse_note = _run_check_pipeline(plan_path, self._data_dir)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "方案核查", f"无法读取方案文件: {exc}")
            return False
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.critical(self, "缺少依赖", str(exc))
            return False
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "方案核查", f"输入不支持: {exc}")
            return False
        except SSCError as exc:
            QtWidgets.QMessageBox.critical(self, "方案核查", f"核查失败: {exc}")
            return False
        self._pipeline = (report, card, paras)
        self.findings = list(report.findings)
        if parse_failed:
            self.banner_label.setText(
                f"[解析失败] {parse_note}\n已按降级纪律整体输出待人工确认清单，不产生任何自动 fail。"
            )
            self.banner_label.show()
        else:
            self.banner_label.hide()
        self._populate(report, card, len(paras))
        return True

    def _populate(self, report, card, paras_count: int) -> None:
        self.tree.clear()
        for f in self.findings:
            label = VERDICT_LABELS.get(f.verdict, f.verdict)
            item = QtWidgets.QTreeWidgetItem(
                [label, f.rule_id, f.rule_name, f.message, f.clause_id or "（文档级证据问题）"]
            )
            color = QtGui.QColor(VERDICT_COLORS.get(f.verdict, "#37474f"))
            item.setForeground(0, QtGui.QBrush(color))
            item.setData(0, QtCore.Qt.UserRole, f)
            item.setToolTip(3, f.message)
            self.tree.addTopLevelItem(item)
        for i, w in enumerate((90, 110, 240, 360, 190)):
            self.tree.setColumnWidth(i, w)
        s = report.summary()
        method_txt = "、".join(m.name for m in card.methods) or "未检出加固方法"
        self.summary_label.setText(
            f"{report.doc_name}（可解析段落 {paras_count}；方法: {method_txt}）    汇总: "
            f"不符合 {s['fail']} / 疑似 {s['suspicious']} / 待人工确认 {s['needs_confirm']} / 通过 {s['pass']}"
        )
        self.detail_browser.setPlainText("选择上方任一结论查看证据链。")

    def _show_detail(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        f = items[0].data(0, QtCore.Qt.UserRole)
        if f is None:
            return
        lines = [
            f"[{VERDICT_LABELS.get(f.verdict, f.verdict)}] {f.rule_id}  {f.rule_name}",
            f"结论: {f.message}",
            f"依据: {f.clause_id or '（文档级证据问题）'}",
        ]
        if f.advice:
            lines.append(f"建议: {f.advice}")
        lines.append("证据链:")
        lines.append(_evidence_text(f.evidence or {}))
        self.detail_browser.setPlainText("\n".join(lines))

    def export_report_dir(self) -> Optional[Path]:
        if self._pipeline is None:
            QtWidgets.QMessageBox.information(self, "导出报告", "请先完成一次方案核查。")
            return None
        outdir = QtWidgets.QFileDialog.getExistingDirectory(self, "选择报告输出目录")
        if not outdir:
            return None
        report, card, paras = self._pipeline
        out_dir = Path(outdir)
        json_path = out_dir / "check_report.json"
        json_path.write_text(
            json.dumps(_check_report_json(report, card, len(paras)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            from ..report.docx_export import export_check_report

            docx_path = export_check_report(report, out_dir / "check_report.docx", card=card)
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.warning(
                self, "缺少依赖",
                f"{exc}\n\n（JSON 报告已写入 {json_path}；docx 报告需安装 report extras）",
            )
            return out_dir
        QtWidgets.QMessageBox.information(
            self, "导出报告", f"核查报告已写入:\n{json_path}\n{docx_path}"
        )
        return out_dir


# ---------------------------------------------------------------------------
# 页签 3：检查单
# ---------------------------------------------------------------------------

class ChecklistTab(QtWidgets.QWidget):
    """GB 55021-2021 检查单 GUI 形态（--interactive/--doc 的等价界面）。

    建议逻辑用 cli._auto_text_suggestion（检出关键词→符合，未检出→待确认，绝不自动
    给"不符合"）；渲染用 cli._render_filled（与 ssc checklist --fill 同一函数）；
    核对结果 JSON 与 CLI --out 同形状 {item_id: {choice, note}}。
    """

    def __init__(self, data_dir: Path, store: ChecklistStore, parent=None) -> None:
        super().__init__(parent)
        self._store = store
        self.combos: Dict[str, QtWidgets.QComboBox] = {}
        self.notes: Dict[str, QtWidgets.QLineEdit] = {}
        self.suggestion_labels: Dict[str, QtWidgets.QLabel] = {}

        root = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("方案文档（可选，供 auto_text 条目生成建议）"))
        self.doc_edit = QtWidgets.QLineEdit()
        b_browse = QtWidgets.QPushButton("浏览…")
        b_suggest = QtWidgets.QPushButton("载入并生成建议")
        b_browse.clicked.connect(self._browse)
        b_suggest.clicked.connect(self.generate_suggestions)
        for w in (self.doc_edit, b_browse, b_suggest):
            row.addWidget(w)
        root.addLayout(row)

        self.issues_label = QtWidgets.QLabel("")
        self.issues_label.setStyleSheet("color: #c62828;")
        self.issues_label.setWordWrap(True)
        root.addWidget(self.issues_label)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        host = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(host)
        if store.issues:
            self.issues_label.setText("检查单数据问题（与 ssc checklist exit 1 同口径，已停用核对）:\n" + "\n".join(store.issues))
        for item in store.items:
            box = QtWidgets.QGroupBox()
            box.setTitle(f"{item.item_id}（条号 {item.clause_no or '待回填'}）[{item.check_mode}]")
            bl = QtWidgets.QVBoxLayout(box)
            gist = QtWidgets.QLabel(item.gist)
            gist.setWordWrap(True)
            bl.addWidget(gist)
            if item.advice:
                advice = QtWidgets.QLabel("核查提示: " + item.advice)
                advice.setWordWrap(True)
                advice.setStyleSheet("color: #546e7a;")
                bl.addWidget(advice)
            h = QtWidgets.QHBoxLayout()
            combo = QtWidgets.QComboBox()
            combo.addItems(item.options)
            note = QtWidgets.QLineEdit()
            note.setPlaceholderText("备注（可留空）")
            h.addWidget(QtWidgets.QLabel("判定"))
            h.addWidget(combo)
            h.addWidget(QtWidgets.QLabel("备注"), 0)
            h.addWidget(note, 1)
            bl.addLayout(h)
            sug = QtWidgets.QLabel("")
            sug.setStyleSheet("color: #546e7a;")
            sug.setWordWrap(True)
            bl.addWidget(sug)
            vbox.addWidget(box)
            self.combos[item.item_id] = combo
            self.notes[item.item_id] = note
            self.suggestion_labels[item.item_id] = sug
        vbox.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        btns = QtWidgets.QHBoxLayout()
        b_save = QtWidgets.QPushButton("保存核对结果 JSON…")
        b_render = QtWidgets.QPushButton("渲染符合性清单")
        b_save.clicked.connect(self.save_answers)
        b_render.clicked.connect(self.render_filled)
        btns.addWidget(b_save)
        btns.addWidget(b_render)
        btns.addStretch(1)
        root.addLayout(btns)

        self.result_browser = QtWidgets.QTextBrowser()
        self.result_browser.setMaximumHeight(180)
        root.addWidget(self.result_browser)

        if store.issues:
            for b in (b_suggest, b_save, b_render):
                b.setEnabled(False)

    def _browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择方案文件", "", PLAN_FILE_FILTER)
        if path:
            self.doc_edit.setText(path)

    def generate_suggestions(self) -> bool:
        text = self.doc_edit.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, "检查单", "请先选择方案文件（仅 auto_text 条目会生成建议）。")
            return False
        try:
            from ..parsing.docx_text import extract_paras

            doc_text = "\n".join(p.text for p in extract_paras(Path(text)))
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.critical(self, "缺少依赖", str(exc))
            return False
        except SSCError as exc:  # ParseError
            QtWidgets.QMessageBox.critical(self, "解析失败", str(exc))
            return False
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "输入不支持", str(exc))
            return False
        for item in self._store.items:
            if item.check_mode != "auto_text":
                continue
            sug, why = _auto_text_suggestion(item, doc_text)
            self.combos[item.item_id].setCurrentText(sug)
            self.notes[item.item_id].setText(why)
            self.suggestion_labels[item.item_id].setText(f"自动建议: {sug}（{why}）")
        self.result_browser.setPlainText("已按 auto_text 条目生成建议；manual 条目仍需人工判定（默认待确认）。")
        return True

    def collect_answers(self) -> Dict[str, Dict[str, str]]:
        answers: Dict[str, Dict[str, str]] = {}
        for item in self._store.items:
            answers[item.item_id] = {
                "choice": self.combos[item.item_id].currentText(),
                "note": self.notes[item.item_id].text().strip(),
            }
        return answers

    def save_answers(self) -> Optional[Path]:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "保存核对结果", "checklist_answers.json", JSON_FILE_FILTER)
        if not path:
            return None
        Path(path).write_text(
            json.dumps(self.collect_answers(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.result_browser.append(f"核对结果已保存: {path}（可用 ssc checklist --fill 复现渲染）")
        return Path(path)

    def render_filled(self) -> str:
        lines = _render_filled(self._store, self.collect_answers())
        self.result_browser.setPlainText("\n".join(lines))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 页签 4：报告
# ---------------------------------------------------------------------------

class ReportTab(QtWidgets.QWidget):
    """报告导出工作台：验算书（FR-D1）+ 核查报告（FR-D2）。

    直接入库函数 export_calc_book / export_check_report，与 ssc report calc/check 同出口。
    """

    def __init__(self, data_dir: Path, store: ClauseStore, parent=None) -> None:
        super().__init__(parent)
        self._data_dir = data_dir
        self._store = store

        root = QtWidgets.QVBoxLayout(self)

        g1 = QtWidgets.QGroupBox("验算书导出（FR-D1：输入参数/计算过程/依据条款/结论/签署栏/免责声明）")
        f1 = QtWidgets.QFormLayout(g1)
        self.calc_combo = QtWidgets.QComboBox()
        for mid in sorted(CALC_REGISTRY):
            self.calc_combo.addItem(f"{mid} — {CALC_REGISTRY[mid].name}", userData=mid)
        self.calc_input_edit = QtWidgets.QLineEdit()
        self.calc_out_edit = QtWidgets.QLineEdit()
        b_in = QtWidgets.QPushButton("浏览…")
        b_in.clicked.connect(self._browse_calc_input)
        in_row = QtWidgets.QHBoxLayout()
        in_row.addWidget(self.calc_input_edit, 1)
        in_row.addWidget(b_in)
        f1.addRow("验算模块", self.calc_combo)
        f1.addRow("参数卡 JSON", in_row)
        f1.addRow("输出 docx", self.calc_out_edit)
        b1 = QtWidgets.QPushButton("导出验算书")
        b1.clicked.connect(self.export_calc_book)
        f1.addRow("", b1)
        root.addWidget(g1)

        g2 = QtWidgets.QGroupBox("核查报告导出（FR-D2：概要/明细含证据链/整改建议/签署栏/免责声明）")
        f2 = QtWidgets.QFormLayout(g2)
        self.check_file_edit = QtWidgets.QLineEdit()
        self.check_out_edit = QtWidgets.QLineEdit()
        b_file = QtWidgets.QPushButton("浏览…")
        b_file.clicked.connect(self._browse_plan)
        file_row = QtWidgets.QHBoxLayout()
        file_row.addWidget(self.check_file_edit, 1)
        file_row.addWidget(b_file)
        f2.addRow("方案文件", file_row)
        f2.addRow("输出 docx", self.check_out_edit)
        b2 = QtWidgets.QPushButton("导出核查报告")
        b2.clicked.connect(self.export_check_report)
        f2.addRow("", b2)
        root.addWidget(g2)

        self.log_browser = QtWidgets.QTextBrowser()
        root.addWidget(self.log_browser, 1)
        self.log_browser.setPlainText(
            "说明：本页与 ssc report calc/check 命令共用同一导出函数与核查流水线；"
            "签署栏为占位空栏（不虚构签署人），产物含免责声明且 0 外部链接。\n" + DISCLAIMER
        )

    def _browse_calc_input(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择参数卡 JSON", "", JSON_FILE_FILTER)
        if path:
            self.calc_input_edit.setText(path)

    def _browse_plan(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择方案文件", "", PLAN_FILE_FILTER)
        if path:
            self.check_file_edit.setText(path)

    def _log(self, text: str) -> None:
        self.log_browser.append(text)

    def export_calc_book(self) -> Optional[Path]:
        module_id = self.calc_combo.currentData()
        input_text = self.calc_input_edit.text().strip()
        out_text = self.calc_out_edit.text().strip()
        if not input_text or not out_text:
            QtWidgets.QMessageBox.warning(self, "验算书导出", "请先填写参数卡 JSON 与输出 docx 路径。")
            return None
        try:
            params = json.loads(Path(input_text).read_text(encoding="utf-8"))
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "验算书导出", f"无法读取参数卡: {exc}")
            return None
        except json.JSONDecodeError as exc:
            QtWidgets.QMessageBox.critical(self, "验算书导出", f"参数卡不是合法 JSON: {exc}")
            return None
        if isinstance(params, dict) and isinstance(params.get("params"), dict):
            params = params["params"]
        try:
            result = run_calc(module_id, params, self._store)
        except ClauseNotVerifiedError as exc:
            QtWidgets.QMessageBox.critical(self, "条文门控拦截", str(exc))
            return None
        except ValidationError as exc:
            QtWidgets.QMessageBox.critical(self, "参数校验未通过", str(exc))
            return None
        except SSCError as exc:
            QtWidgets.QMessageBox.critical(self, "验算失败", str(exc))
            return None
        try:
            from ..report.docx_export import export_calc_book

            out = export_calc_book(result, Path(out_text))
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.warning(self, "缺少依赖", str(exc))
            return None
        self._log(f"验算书 docx 已写入: {out}")
        return out

    def export_check_report(self) -> Optional[Path]:
        file_text = self.check_file_edit.text().strip()
        out_text = self.check_out_edit.text().strip()
        if not file_text or not out_text:
            QtWidgets.QMessageBox.warning(self, "核查报告导出", "请先填写方案文件与输出 docx 路径。")
            return None
        try:
            report, card, _paras, _failed, _note = _run_check_pipeline(Path(file_text), self._data_dir)
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "核查报告导出", f"无法读取方案文件: {exc}")
            return None
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.critical(self, "缺少依赖", str(exc))
            return None
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "输入不支持", str(exc))
            return None
        except SSCError as exc:
            QtWidgets.QMessageBox.critical(self, "核查失败", str(exc))
            return None
        try:
            from ..report.docx_export import export_check_report

            out = export_check_report(report, Path(out_text), card=card)
        except MissingExtraError as exc:
            QtWidgets.QMessageBox.warning(self, "缺少依赖", str(exc))
            return None
        self._log(f"核查报告 docx 已写入: {out}")
        return out


# ---------------------------------------------------------------------------
# 主窗口与应用入口
# ---------------------------------------------------------------------------

class MainWindow(QtWidgets.QMainWindow):
    """四页签主窗口；数据三库在构造时加载一次，页签共享。"""

    def __init__(self, data_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.data_dir = data_dir
        self.setWindowTitle(f"结构加固验算与方案核查工具 ssc v{__version__}")
        self.resize(1120, 720)

        self.clause_store = ClauseStore(data_dir / "knowledge")
        self.rule_store = RuleStore(data_dir / "knowledge")
        self.checklist_store = ChecklistStore(data_dir / "knowledge")

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(CalcTab(data_dir, self.clause_store), "验算表单")
        tabs.addTab(CheckTab(data_dir), "方案核查")
        tabs.addTab(ChecklistTab(data_dir, self.checklist_store), "检查单")
        tabs.addTab(ReportTab(data_dir, self.clause_store), "报告")
        self.setCentralWidget(tabs)

        cs = self.clause_store.status_summary()
        rs = self.rule_store.status_summary()
        ckl = self.checklist_store.status_summary()
        issues = len(cs["issues"]) + len(rs["issues"]) + len(ckl["issues"])
        status_text = (
            f"数据目录: {data_dir}    条款 {cs['total']} 条（已核对 {cs['verified']}）    "
            f"规则 {rs['total']} 条（依据已核对 {rs['verified']}）    检查单 {ckl['total']} 项    "
            + ("数据存在问题！" if issues else "数据自检 OK")
        )
        self.statusBar().showMessage(status_text)

        help_menu = self.menuBar().addMenu("帮助")
        about = QtGui.QAction("关于", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self, "关于",
            f"结构加固验算与方案核查工具 ssc v{__version__}\n\n"
            "四页签：验算表单（GB 50367-2013 四模块验算）/ 方案核查（三级判定+证据链）/ "
            "检查单（GB 55021-2021 强制条款核对）/ 报告（docx 导出）。\n\n"
            f"数据目录: {self.data_dir}\n\n{DISCLAIMER}",
        )


def run_app(data_dir: Optional[str] = None) -> int:
    """创建应用与主窗口并进入事件循环；返回退出码（0 正常，2 数据目录缺失，1 加载失败）。"""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("ssc")
    app.setApplicationDisplayName("结构加固验算与方案核查")
    try:
        resolved = find_data_dir(data_dir)
    except SSCError as exc:
        QtWidgets.QMessageBox.critical(
            None, "数据目录未找到",
            f"{exc}\n\n打包版已内嵌 data/knowledge；源码运行请从仓库根启动，"
            f"或用 --data-dir / 环境变量 SSC_DATA_DIR 指定。",
        )
        return EXIT_INPUT
    try:
        window = MainWindow(resolved)
    except Exception as exc:  # 数据 JSON 损坏等加载期异常：windowed exe 无控制台，必须弹框
        QtWidgets.QMessageBox.critical(None, "启动失败", f"知识库加载失败: {exc}")
        return EXIT_ERROR
    window.show()
    return app.exec()
