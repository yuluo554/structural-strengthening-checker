"""报告导出（docx）：验算书 + 方案核查报告（M4/M5 实装模板）。

纪律（plan/02 FR-D3/D4）：报告强制免责声明；产物 0 外链。
依赖惰性导入，缺失抛 MissingExtraError。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..core.errors import MissingExtraError

DISCLAIMER = (
    "本报告由结构加固验算与加固方案核查工具生成，仅作辅助验算与核查用途，"
    "不替代正式设计文件、施工图审查与竣工验收。"
)


def _import_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError("report", "docx 报告导出") from exc
    return docx


def export_calc_book(result: Dict[str, Any], out_path: Path) -> Path:
    """验算书 docx：输入参数/计算过程/依据条款/结论/签署栏/免责声明。M4 实装。"""
    _import_docx()
    raise NotImplementedError("验算书导出在 M4 实装（plan/05 §五）")


def export_check_report(report: Any, out_path: Path) -> Path:
    """方案核查报告 docx：问题清单+证据链+整改建议+免责声明。M4 实装。"""
    _import_docx()
    raise NotImplementedError("核查报告导出在 M4 实装（plan/05 §五）")
