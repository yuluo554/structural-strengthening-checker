"""PySide6 桌面界面（M5 实装）。依赖惰性导入，缺 extras 友好降级。"""

from __future__ import annotations

from ..core.errors import MissingExtraError


def _import_qt():
    try:
        from PySide6 import QtWidgets  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError("gui", "桌面界面") from exc
    from PySide6 import QtWidgets

    return QtWidgets


def launch() -> int:
    """启动桌面应用。M5 实装四页签（验算表单/方案核查/检查单/报告）。"""
    QtWidgets = _import_qt()
    _ = QtWidgets.QApplication  # 确认可用后再声明未实装
    raise NotImplementedError("桌面界面在 M5 实装（plan/05 §五）；CLI 已可完成全部核心通路。")
