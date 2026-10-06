"""PyInstaller GUI 入口（SSC.exe，console=False）：启动四页签桌面界面。

windowed exe 无控制台，任何启动期异常都必须落到可见消息框；若 PySide6 本身不可用
（DLL 缺失等），退回 ctypes 原生 MessageBox，保证用户永远看到错误而不是静默退出。
"""

from __future__ import annotations

import sys
import traceback


def _fallback_message(title: str, text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def main() -> int:
    try:
        from structural_strengthening_checker.gui.app import launch

        return launch()
    except Exception as exc:
        text = "".join(traceback.format_exception(exc)).strip() or repr(exc)
        try:
            from PySide6 import QtWidgets

            app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
            QtWidgets.QMessageBox.critical(None, "SSC 启动失败", text)
            del app
        except Exception:
            _fallback_message("SSC 启动失败", text)
        return 1


if __name__ == "__main__":
    sys.exit(main())
