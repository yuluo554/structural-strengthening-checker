"""项目级守门测试：pyproject extras 声明 / EOL 策略 / 数据纪律 / 未来注解兼容。"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "structural_strengthening_checker"


def test_pyproject_extras_declared():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for extra in ("gui", "report", "parse", "dev", "package"):
        assert f"{extra} = [" in text, f"pyproject 缺少 extras 组 {extra}"
    assert 'requires-python = ">=3.12"' in text
    assert "dependencies = []" in text  # 核心层零依赖纪律


def test_gitattributes_eol_guard():
    text = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "eol=lf" in text  # 位级锁定基准的 CRLF 防护（M2 引入位级锁定后配合 CR 守门）


def test_all_modules_have_future_annotations():
    """注解纪律：带注解的模块统一 from __future__ import annotations（延迟求值，防运行期名称解析差异）。"""
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        needs_future = ("-> " in text) or (": list[" in text) or ("->list[" in text)
        if needs_future and "from __future__ import annotations" not in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"缺少 future annotations: {offenders}"


def test_no_personal_paths_in_source():
    """脱敏前置守门（开发期）：源码树不得出现个人绝对路径形态。"""
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in ("C:\\Users\\", "D:\\ProgramData"):
            if marker in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"源码出现本机绝对路径: {offenders}"


def test_python_version_floor():
    """支持面 >=3.12（3.8/3.9/3.10/3.11 均已 EOL 或即将 EOL）——要求与本机事实一致。"""
    assert sys.version_info >= (3, 12)
