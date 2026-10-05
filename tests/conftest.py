"""pytest 共享夹具。优先使用已安装包；未安装时回退 src 路径（骨架期便利，不掩盖发布问题——
发布门以干净 venv 按 README 安装后全绿为准，见 plan/05 M6）。"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    import structural_strengthening_checker  # noqa: F401
except ImportError:
    sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def repo_data_dir() -> Path:
    return REPO_ROOT / "data"


@pytest.fixture
def make_knowledge(tmp_path):
    """构造临时 knowledge 目录（条款/规则/检查单 JSON，utf-8）。"""

    def _make(clauses=None, rules=None, checklist=None) -> Path:
        kdir = tmp_path / "knowledge"
        (kdir / "clauses").mkdir(parents=True, exist_ok=True)
        (kdir / "rules").mkdir(parents=True, exist_ok=True)
        if clauses:
            (kdir / "clauses" / "c.json").write_text(
                json.dumps(clauses, ensure_ascii=False), encoding="utf-8"
            )
        if rules:
            (kdir / "rules" / "r.json").write_text(
                json.dumps(rules, ensure_ascii=False), encoding="utf-8"
            )
        if checklist is not None:
            (kdir / "checklist_gb55021.json").write_text(
                json.dumps(checklist, ensure_ascii=False), encoding="utf-8"
            )
        return kdir

    return _make


@pytest.fixture
def repo_cwd(tmp_path, monkeypatch):
    """切到仓库根运行（find_data_dir 向上查找依赖 cwd）。"""
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT
