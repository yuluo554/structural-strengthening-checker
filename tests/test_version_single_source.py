"""版本单一来源守门（D10）：pyproject.toml 与 __init__.__version__ 必须一致。

两者漂移是「装出来是 0.1.0、`--version` 说 0.1.1」这类事故的入口；本仓没有打包脚本
回写版本号，所以只能靠守门钉住。解析用 tomllib（3.11+ 标准库；本仓 floor >=3.12）。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from structural_strengthening_checker import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_pyproject_version_matches_package():
    assert _pyproject_version() == __version__, (
        f"pyproject.toml {_pyproject_version()!r} != __version__ {__version__!r}"
    )


def test_version_is_semver_core():
    """X.Y.Z 形态（允许 -预发布/-dev 后缀）；防 `0.0.0` 占位或空串混入。"""
    assert re.fullmatch(r"\d+\.\d+\.\d+([-+][A-Za-z0-9.\-]+)?", __version__), __version__
    assert __version__ != "0.0.0", "0.0.0 是占位值，发布前必须转正"


def test_version_appears_in_readme_status():
    """README 首屏状态行声明的版本必须与代码一致（自述漂移的历史高发点）。"""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:15])
    assert f"v{__version__}" in head, (
        f"README 首屏未出现当前版本 v{__version__}；首屏为：\n{head}"
    )
