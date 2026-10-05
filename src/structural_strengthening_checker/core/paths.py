"""数据目录定位：条款库/规则库/检查单/算例库统一放在仓库 data/knowledge 下。

查找顺序：显式参数 > 环境变量 SSC_DATA_DIR > 从 CWD 逐级向上找 data/knowledge。
（发布打包形态的数据内嵌策略在 M5 决策，见 plan/06。）
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .errors import SSCError

ENV_DATA_DIR = "SSC_DATA_DIR"


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

    cwd = Path.cwd()
    for base in [cwd, *cwd.parents]:
        if (base / "data" / "knowledge").is_dir():
            return base / "data"

    raise SSCError(
        "未找到数据目录（data/knowledge）。请从仓库根目录运行，"
        f"或用 --data-dir / 环境变量 {ENV_DATA_DIR} 指定。"
    )
