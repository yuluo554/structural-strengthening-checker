"""数据目录定位：条款库/规则库/检查单/算例库统一放在仓库 data/knowledge 下。

查找顺序（M5 打包决策，plan/06）：
显式参数 > 环境变量 SSC_DATA_DIR > 打包内嵌（仅冻结/exe 形态）> 从 CWD 逐级向上找 data/knowledge。

打包内嵌查找（tools/ssc.spec 仅收 data/knowledge/** 与 data/cases/*.json）：
① sys._MEIPASS/data（PyInstaller onedir/onefile 通用，6.x 指向 _internal）；
② exe 同级 data/（用户可在发行目录旁挂更新数据）；
③ exe 同级 _internal/data/（PyInstaller 5 onedir 形态兜底）。
私有目录 data/_private/（规范全文）永不入包——版权红线，tools/build_exe.py 构建后断言。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from .errors import SSCError

ENV_DATA_DIR = "SSC_DATA_DIR"


def _bundled_data_dir() -> Optional[Path]:
    """冻结（exe）形态的内嵌数据目录；非冻结返回 None。"""
    if not getattr(sys, "frozen", False):
        return None
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "data")
    exe_dir = Path(sys.executable).resolve().parent
    candidates.append(exe_dir / "data")
    candidates.append(exe_dir / "_internal" / "data")
    for base in candidates:
        if (base / "knowledge").is_dir():
            return base
    return None


def find_data_dir(explicit: Optional[str] = None) -> Path:
    if explicit:
        path = Path(explicit)
        if not (path / "knowledge").is_dir():
            raise SSCError(f"--data-dir 指向的目录缺少 knowledge 子目录: {path}")
        return path

    env = os.environ.get(ENV_DATA_DIR)
    if env:
        path = Path(env)
        if not (path / "knowledge").is_dir():
            raise SSCError(f"环境变量 {ENV_DATA_DIR} 指向的目录缺少 knowledge 子目录: {path}")
        return path

    bundled = _bundled_data_dir()
    if bundled is not None:
        return bundled

    cwd = Path.cwd()
    for base in [cwd, *cwd.parents]:
        if (base / "data" / "knowledge").is_dir():
            return base / "data"

    raise SSCError(
        "未找到数据目录（data/knowledge）。请从仓库根目录运行，"
        f"或用 --data-dir / 环境变量 {ENV_DATA_DIR} 指定。"
    )
