"""PySide6 桌面界面入口（M5 实装）：四页签 验算表单/方案核查/检查单/报告。

分层纪律（plan/03）：本模块是 gui 包的惰性导入薄入口——PySide6 只在 _import_qt() 内导入，
全部 Qt 组件在 gui/mainwindow.py（仅在 _import_qt 成功后被 launch 导入），
因此缺 gui extras 时本模块可安全 import（test_lazy_deps 守门）。

GUI 消费面纪律（plan/06 M5 决策）：四页签全部消费既有 API（run_calc /
cli._run_check_pipeline / ChecklistStore / export_calc_book / export_check_report），
不另起第二套行为；详见 gui/mainwindow 模块 docstring。
"""

from __future__ import annotations

from typing import Optional

from ..core.errors import MissingExtraError


def _import_qt():
    try:
        from PySide6 import QtWidgets  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError("gui", "桌面界面") from exc
    from PySide6 import QtWidgets

    return QtWidgets


def launch(data_dir: Optional[str] = None) -> int:
    """启动桌面应用（四页签）。返回 QApplication.exec 退出码。

    data_dir 透传给 find_data_dir（打包内嵌/环境变量/CWD 上溯的既有查找顺序不变）。
    """
    QtWidgets = _import_qt()
    _ = QtWidgets.QApplication  # 确认 Qt 可用后再进入主窗口模块
    from .mainwindow import run_app

    return run_app(data_dir)
