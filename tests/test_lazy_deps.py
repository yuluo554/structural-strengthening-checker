"""可选依赖惰性导入：缺 extras 必须友好降级，绝不 traceback。"""

import sys

import pytest

from structural_strengthening_checker.core.errors import MissingExtraError


def test_missing_extra_message_has_install_hint():
    err = MissingExtraError("gui", "桌面界面")
    assert "[gui]" in str(err)
    assert "pip install" in str(err)


def test_docx_missing_friendly(monkeypatch):
    from structural_strengthening_checker.parsing import docx_text

    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(MissingExtraError) as ei:
        docx_text._import_docx()
    assert "[parse]" in str(ei.value)


def test_pypdf_missing_friendly(monkeypatch):
    from structural_strengthening_checker.parsing import docx_text

    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(MissingExtraError) as ei:
        docx_text._import_pypdf()
    assert "[parse]" in str(ei.value)


def test_report_missing_friendly(monkeypatch):
    from structural_strengthening_checker.report import docx_export

    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(MissingExtraError) as ei:
        docx_export._import_docx()
    assert "[report]" in str(ei.value)


def test_pyside6_missing_friendly(monkeypatch):
    from structural_strengthening_checker.gui import app

    monkeypatch.setitem(sys.modules, "PySide6", None)
    with pytest.raises(MissingExtraError) as ei:
        app._import_qt()
    assert "[gui]" in str(ei.value)


def test_unsupported_suffix_no_deps_needed(tmp_path):
    from structural_strengthening_checker.parsing.docx_text import extract_paras

    fake = tmp_path / "plan.txt"
    fake.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_paras(fake)
