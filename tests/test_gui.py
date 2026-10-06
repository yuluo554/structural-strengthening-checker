"""GUI 四页签测试（PySide6 offscreen）：主流程冒烟 + 消费面纪律。

- PySide6 未安装 → importorskip 跳过（CI 仅 windows/3.8 矩阵加装 gui extras）；
- QT_QPA_PLATFORM=offscreen 必须在首次导入 PySide6 前设置；
- 消息框/文件对话框统一 monkeypatch（测试不弹窗、不阻塞）。
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6 import QtWidgets  # noqa: E402

import structural_strengthening_checker.gui.mainwindow as mw  # noqa: E402
from structural_strengthening_checker.core.engine import CALC_REGISTRY  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_CASE01 = os.path.join(REPO, "data", "synthetic", "samples", "case01_seed20261005.docx")


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _quiet_dialogs(monkeypatch, tmp_path_factory):
    """屏蔽模态消息框与文件对话框（返回确定值），测试不阻塞。"""
    MB = QtWidgets.QMessageBox
    ok = QtWidgets.QMessageBox.StandardButton.Ok
    for name in ("information", "warning", "critical", "about"):
        monkeypatch.setattr(MB, name, staticmethod(lambda *a, **k: ok))


@pytest.fixture()
def window(repo_data_dir, qapp):
    win = mw.MainWindow(repo_data_dir)
    yield win
    win.close()


@pytest.fixture()
def calc_tab(window):
    return window.centralWidget().widget(0)


@pytest.fixture()
def check_tab(window):
    return window.centralWidget().widget(1)


@pytest.fixture()
def checklist_tab(window):
    return window.centralWidget().widget(2)


@pytest.fixture()
def report_tab(window):
    return window.centralWidget().widget(3)


@pytest.fixture()
def rebar_input(repo_data_dir):
    data = json.loads(
        (repo_data_dir / "cases" / "post_rebar_cases.json").read_text(encoding="utf-8")
    )
    cases = data if isinstance(data, list) else data["cases"]
    return cases[0]["input"]


# ---------------------------------------------------------------------------
# 主窗口结构
# ---------------------------------------------------------------------------

def test_main_window_four_tabs(window):
    tabs = window.centralWidget()
    assert tabs.count() == 4
    assert [tabs.tabText(i) for i in range(4)] == ["验算表单", "方案核查", "检查单", "报告"]
    assert window.clause_store.issues == []
    assert window.rule_store.issues == []
    assert window.checklist_store.issues == []


def test_calc_tab_modules_from_registry(window, calc_tab):
    combo = calc_tab.module_combo
    assert combo.count() == len(CALC_REGISTRY)
    idx = combo.findData("post_rebar_anchor")
    assert idx >= 0
    combo.setCurrentIndex(idx)
    schema = CALC_REGISTRY["post_rebar_anchor"].param_schema
    assert set(calc_tab.edits) == set(schema)


def test_status_bar_shows_data_dir(window, repo_data_dir):
    assert str(repo_data_dir) in window.statusBar().currentMessage()


# ---------------------------------------------------------------------------
# 页签 1：验算表单
# ---------------------------------------------------------------------------

def test_calc_tab_run_ok(window, calc_tab, rebar_input):
    idx = calc_tab.module_combo.findData("post_rebar_anchor")
    calc_tab.module_combo.setCurrentIndex(idx)
    for key, value in rebar_input.items():
        calc_tab.edits[key].setText(str(value))
    assert calc_tab.run_calc_now() is True
    assert "验算结论" in calc_tab.verdict_label.text()
    assert "第1步" in calc_tab.result_browser.toPlainText()


def test_calc_tab_validation_error_inline(calc_tab, rebar_input):
    idx = calc_tab.module_combo.findData("post_rebar_anchor")
    calc_tab.module_combo.setCurrentIndex(idx)
    for key, value in rebar_input.items():
        calc_tab.edits[key].setText(str(value))
    calc_tab.edits["d"].setText("-12")  # 直径必须为正
    assert calc_tab.run_calc_now() is False
    assert "参数校验未通过" in calc_tab.result_browser.toPlainText()


def test_calc_tab_missing_required(calc_tab, rebar_input):
    idx = calc_tab.module_combo.findData("post_rebar_anchor")
    calc_tab.module_combo.setCurrentIndex(idx)
    for key, value in rebar_input.items():
        calc_tab.edits[key].setText(str(value))
    calc_tab.edits["ld"].setText("")  # 必填留空
    assert calc_tab.run_calc_now() is False
    assert "缺少必填参数" in calc_tab.result_browser.toPlainText()


def test_calc_tab_load_input_json(window, calc_tab, rebar_input, tmp_path):
    p = tmp_path / "params.json"
    p.write_text(json.dumps(rebar_input, ensure_ascii=False), encoding="utf-8")
    idx = calc_tab.module_combo.findData("post_rebar_anchor")
    calc_tab.module_combo.setCurrentIndex(idx)
    for edit in calc_tab.edits.values():
        edit.setText("")
    mw.QtWidgets.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(p), ""))
    calc_tab.load_input_json()
    assert calc_tab.edits["d"].text() == str(rebar_input["d"])


# ---------------------------------------------------------------------------
# 页签 2：方案核查
# ---------------------------------------------------------------------------

def test_check_tab_run_on_sample(window, check_tab):
    check_tab.path_edit.setText(SAMPLE_CASE01)
    assert check_tab.run_check_now() is True
    assert check_tab.tree.topLevelItemCount() == len(check_tab.findings)
    assert check_tab.tree.topLevelItemCount() > 0
    assert "汇总" in check_tab.summary_label.text()
    # 三级判定标签来自 VERDICT_LABELS 单一出口（消费面纪律）
    labels = {check_tab.tree.topLevelItem(i).text(0) for i in range(check_tab.tree.topLevelItemCount())}
    assert labels <= set(mw.VERDICT_LABELS.values()) | {"待人工确认"}


def test_check_tab_detail_view(check_tab):
    check_tab.path_edit.setText(SAMPLE_CASE01)
    assert check_tab.run_check_now() is True
    check_tab.tree.setCurrentItem(check_tab.tree.topLevelItem(0))
    text = check_tab.detail_browser.toPlainText()
    assert "结论:" in text and "依据:" in text


def test_check_tab_export_report_dir(window, check_tab, tmp_path):
    check_tab.path_edit.setText(SAMPLE_CASE01)
    assert check_tab.run_check_now() is True
    out_dir = tmp_path / "report_out"
    out_dir.mkdir()
    mw.QtWidgets.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(out_dir))
    result = check_tab.export_report_dir()
    assert result == out_dir
    data = json.loads((out_dir / "check_report.json").read_text(encoding="utf-8"))
    assert "findings" in data and "disclaimer" in data
    assert (out_dir / "check_report.docx").is_file()


def test_check_tab_missing_file(check_tab):
    check_tab.path_edit.setText(str(check_tab.path_edit.text() or "no_such_missing_file.docx"))
    assert check_tab.run_check_now() is False


# ---------------------------------------------------------------------------
# 页签 3：检查单
# ---------------------------------------------------------------------------

def test_checklist_tab_items_count(window, checklist_tab):
    assert len(checklist_tab.combos) == len(window.checklist_store.items)
    assert window.checklist_store.items
    for combo in checklist_tab.combos.values():
        assert combo.currentText() == "待确认" or combo.currentText() in (
            "符合", "不符合", "不适用", "待确认"
        )


def test_checklist_tab_save_and_render(window, checklist_tab, tmp_path):
    first_id = window.checklist_store.items[0].item_id
    checklist_tab.combos[first_id].setCurrentText("符合")
    checklist_tab.notes[first_id].setText("GUI 测试备注")
    out = tmp_path / "answers.json"
    mw.QtWidgets.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(out), ""))
    saved = checklist_tab.save_answers()
    assert saved == out
    answers = json.loads(out.read_text(encoding="utf-8"))
    assert answers[first_id] == {"choice": "符合", "note": "GUI 测试备注"}
    rendered = checklist_tab.render_filled()
    assert "汇总" in rendered and first_id in rendered


def test_checklist_manual_items_stay_pending(window, checklist_tab):
    """manual 条目不允许被自动建议改写（宁缺勿错口径）。"""
    for item in window.checklist_store.items:
        if item.check_mode == "manual":
            assert checklist_tab.suggestion_labels[item.item_id].text() == ""


def test_checklist_suggestions_need_doc(checklist_tab):
    checklist_tab.doc_edit.setText("")
    assert checklist_tab.generate_suggestions() is False


# ---------------------------------------------------------------------------
# 页签 4：报告
# ---------------------------------------------------------------------------

def test_report_tab_export_calc_book(report_tab, rebar_input, tmp_path):
    params_path = tmp_path / "params.json"
    params_path.write_text(json.dumps(rebar_input, ensure_ascii=False), encoding="utf-8")
    idx = report_tab.calc_combo.findData("post_rebar_anchor")
    report_tab.calc_combo.setCurrentIndex(idx)
    report_tab.calc_input_edit.setText(str(params_path))
    out = tmp_path / "calc_book.docx"
    report_tab.calc_out_edit.setText(str(out))
    result = report_tab.export_calc_book()
    assert result == out and out.is_file() and out.stat().st_size > 0


def test_report_tab_export_check_report(report_tab, tmp_path):
    out = tmp_path / "check_report.docx"
    report_tab.check_file_edit.setText(SAMPLE_CASE01)
    report_tab.check_out_edit.setText(str(out))
    result = report_tab.export_check_report()
    assert result == out and out.is_file() and out.stat().st_size > 0
