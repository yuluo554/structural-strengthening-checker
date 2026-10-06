"""打包纪律测试（M5）：find_data_dir 冻结分支 / spec 数据红线 / 全离线守门。

- 冻结分支优先级（plan/06 决策）：显式 > SSC_DATA_DIR > 内嵌 > CWD 上溯；
- spec datas 仅收 data/knowledge/** 与 data/cases/*.json（_private 永不入包）；
- 全离线（NFR）：源码树禁止网络库 import——断网全功能的代码级证据。
"""

from __future__ import annotations

import sys
from pathlib import Path

from structural_strengthening_checker.core.paths import find_data_dir

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "structural_strengthening_checker"


# ---------------------------------------------------------------------------
# find_data_dir 冻结（打包）分支
# ---------------------------------------------------------------------------

def test_find_data_dir_frozen_meipass(tmp_path, monkeypatch):
    (tmp_path / "data" / "knowledge").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.delenv("SSC_DATA_DIR", raising=False)
    assert find_data_dir() == tmp_path / "data"


def test_find_data_dir_frozen_exe_dir(tmp_path, monkeypatch):
    (tmp_path / "data" / "knowledge").mkdir(parents=True)
    (tmp_path / "SSC.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "SSC.exe"))
    monkeypatch.delenv("SSC_DATA_DIR", raising=False)
    assert find_data_dir() == tmp_path / "data"


def test_find_data_dir_frozen_internal_dir(tmp_path, monkeypatch):
    (tmp_path / "_internal" / "data" / "knowledge").mkdir(parents=True)
    (tmp_path / "SSC.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "SSC.exe"))
    monkeypatch.delenv("SSC_DATA_DIR", raising=False)
    assert find_data_dir() == tmp_path / "_internal" / "data"


def test_find_data_dir_env_overrides_bundled(tmp_path, monkeypatch):
    (tmp_path / "env_data" / "knowledge").mkdir(parents=True)
    (tmp_path / "bundled" / "data" / "knowledge").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundled"), raising=False)
    monkeypatch.setenv("SSC_DATA_DIR", str(tmp_path / "env_data"))
    assert find_data_dir() == tmp_path / "env_data"


def test_find_data_dir_explicit_wins(repo_cwd):
    assert find_data_dir(str(repo_cwd / "data")) == repo_cwd / "data"


def test_find_data_dir_source_mode_unchanged(repo_cwd):
    """非冻结形态行为不变：CWD 上溯找到仓库 data（回归守门）。"""
    assert getattr(sys, "frozen", False) is False
    assert find_data_dir() == repo_cwd / "data"


# ---------------------------------------------------------------------------
# spec 与构建脚本红线
# ---------------------------------------------------------------------------

def test_spec_datas_only_knowledge_and_cases():
    text = (REPO_ROOT / "tools" / "ssc.spec").read_text(encoding="utf-8")
    datas_section = text.split("datas = [", 1)[1].split("common = dict", 1)[0]
    assert '"data/knowledge"' in datas_section
    assert '"data/cases"' in datas_section
    for banned in ("_private", "standards_raw", "synthetic", "workings"):
        assert banned not in datas_section, f"spec datas 不得包含 {banned}"


def test_spec_builds_both_exes():
    text = (REPO_ROOT / "tools" / "ssc.spec").read_text(encoding="utf-8")
    assert 'name="SSC"' in text and "console=False" in text
    assert 'name="ssc-cli"' in text and "console=True" in text


def test_build_exe_asserts_forbidden_parts():
    text = (REPO_ROOT / "tools" / "build_exe.py").read_text(encoding="utf-8")
    for banned in ("_private", "standards_raw", "synthetic", "workings"):
        assert banned in text, f"build_exe.py 红线断言须覆盖 {banned}"


# ---------------------------------------------------------------------------
# 全离线守门（断网全功能的代码级证据）
# ---------------------------------------------------------------------------

def test_no_network_imports_in_source():
    banned = (
        "import socket", "from socket", "import urllib", "from urllib",
        "import http", "from http", "import requests", "from requests",
        "import httpx", "from httpx", "import ftplib", "import smtplib",
        "import telnetlib", "import xmlrpc", "import aiohttp",
    )
    offenders = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for b in banned:
            if b in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {b}")
    assert offenders == [], f"源码出现网络库引用（违背全离线约束）: {offenders}"
