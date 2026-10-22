"""bench 算例门槛的 CLI 层守门（D2）。

函数层（tests/test_bench.py::test_bench_truth_mismatch_counts_failed）只断言
run_calc_bench 的返回值；cli._cmd_bench 曾经只读 bench["issues"]，忽略
bench["failed"] / bench["blocked_by_clauses"]，于是篡改算例真值仍 BENCH_OK + rc 0。
本文件把守门下沉到 CLI 层：篡改真值 → main(["bench"]) 退出码必须非 0。

两条测试对应两个方向：
  ① 正常仓库 → rc 0（防止反向收得过狠，把正常状态判红）
  ② tmp_path 造篡改副本 → rc 非 0（核心负控）
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from structural_strengthening_checker.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bench_cli_green_on_repo_data(repo_cwd, capsys):
    """正常仓库：门槛判定达标、退出码 0。"""
    code = main(["bench"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "BENCH_OK" in out


def _tampered_data_copy(tmp_path: Path) -> Path:
    """复制仓库 data/（排除私有原始件），再把第一例的 Mu_kNm 改到离谱。"""
    dst = tmp_path / "data"
    shutil.copytree(
        REPO_ROOT / "data",
        dst,
        ignore=shutil.ignore_patterns("_private", "standards_raw", "output"),
    )
    case_file = dst / "cases" / "flexure_cases.json"
    cases = json.loads(case_file.read_text(encoding="utf-8"))
    assert cases and cases[0]["expected"]["Mu_kNm"] > 0
    cases[0]["expected"]["Mu_kNm"] = 999.99
    case_file.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return dst


def test_bench_cli_fails_on_tampered_truth(tmp_path, capsys):
    """负控：篡改一条算例真值 → 退出码非 0 且点名失败例数（D2 的核心验收）。"""
    data_dir = _tampered_data_copy(tmp_path)
    code = main(["--data-dir", str(data_dir), "bench"])
    out = capsys.readouterr().out
    assert code != 0, out
    assert "算例真值比对失败 1 例" in out
    assert "BENCH_FAIL" in out
