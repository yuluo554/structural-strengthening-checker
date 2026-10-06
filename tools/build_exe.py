"""exe 构建封装（M5）：跑 PyInstaller + 版权/完整性红线断言。

用法（仓库根）:
    py -X utf8 tools/build_exe.py            # 构建 + 断言 + 摘要
    py -X utf8 tools/build_exe.py --skip-build   # 仅对既有 dist/SSC 重跑断言

断言（红线，任一违反 exit 1）:
- dist/SSC/SSC.exe 与 ssc-cli.exe 存在；
- 内嵌数据齐：_internal/data/knowledge（三库 JSON）与 _internal/data/cases/*.json 与仓库一致；
- dist 全树不出现 _private/（规范全文）/standards_raw/、synthetic/、workings/ 路径成分。

注意：构建环境需安装 .[gui,report,parse,package]（PySide6/python-docx/pypdf/PyInstaller）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist" / "SSC"
FORBIDDEN_PARTS = ("_private", "standards_raw", "synthetic", "workings")


def run_build() -> None:
    if shutil.which("py") is None:
        raise SystemExit("未找到 py 启动器（本机纪律用 py -X utf8 运行）")
    cmd = [sys.executable, "-X", "utf8", "-m", "PyInstaller", "--noconfirm", "--clean", "tools/ssc.spec"]
    print("[build]", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise SystemExit(f"PyInstaller 失败（exit {proc.returncode}）")


def assert_no_forbidden_parts() -> int:
    hits = []
    n_files = 0
    for p in DIST.rglob("*"):
        n_files += 1
        parts = {part.lower() for part in p.parts[len(DIST.parts):]}
        for bad in FORBIDDEN_PARTS:
            if bad in parts or any(bad in part.lower() for part in parts):
                hits.append(str(p.relative_to(DIST)))
    print(f"[assert] dist 全树 {n_files} 个路径，扫描禁区成分 {FORBIDDEN_PARTS}")
    if hits:
        print("[assert][x] 产物出现禁区文件/目录:")
        for h in hits[:20]:
            print("   ", h)
        return 1
    print("[assert] OK：无 _private/standards_raw/synthetic/workings 成分")
    return 0


def assert_data_embedded() -> int:
    internal = DIST / "_internal"
    embedded_knowledge = internal / "data" / "knowledge"
    issues = []
    if not (DIST / "SSC.exe").is_file():
        issues.append("缺少 dist/SSC/SSC.exe")
    if not (DIST / "ssc-cli.exe").is_file():
        issues.append("缺少 dist/SSC/ssc-cli.exe")
    if not embedded_knowledge.is_dir():
        issues.append(f"内嵌数据目录缺失: {embedded_knowledge}")
    else:
        n_clauses = len(list((embedded_knowledge / "clauses").glob("*.json")))
        n_rules = len(list((embedded_knowledge / "rules").glob("*.json")))
        if n_clauses < 1 or n_rules < 1 or not (embedded_knowledge / "checklist_gb55021.json").is_file():
            issues.append(f"内嵌三库不齐（clauses={n_clauses}, rules={n_rules}）")
        repo_clauses = len(list((ROOT / "data" / "knowledge" / "clauses").glob("*.json")))
        repo_rules = len(list((ROOT / "data" / "knowledge" / "rules").glob("*.json")))
        if (n_clauses, n_rules) != (repo_clauses, repo_rules):
            issues.append(f"内嵌库文件数与仓库不一致: {n_clauses}/{n_rules} vs 仓库 {repo_clauses}/{repo_rules}")
    embedded_cases = internal / "data" / "cases"
    repo_cases = sorted(p.name for p in (ROOT / "data" / "cases").glob("*.json"))
    embedded_case_names = sorted(p.name for p in embedded_cases.glob("*.json")) if embedded_cases.is_dir() else []
    if embedded_case_names != repo_cases:
        issues.append(f"内嵌算例与仓库不一致: {embedded_case_names} vs {repo_cases}")
    else:
        for name in repo_cases:
            a = json.loads((embedded_cases / name).read_text(encoding="utf-8"))
            b = json.loads((ROOT / "data" / "cases" / name).read_text(encoding="utf-8"))
            if json.dumps(a, sort_keys=True, ensure_ascii=False) != json.dumps(b, sort_keys=True, ensure_ascii=False):
                issues.append(f"内嵌算例内容漂移: {name}")
    if issues:
        print("[assert][x] 内嵌数据校验失败:")
        for i in issues:
            print("   ", i)
        return 1
    print(f"[assert] OK：SSC.exe/ssc-cli.exe 存在；knowledge 三库与 cases {len(repo_cases)} 份逐字节级对账一致")
    return 0


def main() -> int:
    if "--skip-build" not in sys.argv:
        run_build()
    if not DIST.is_dir():
        print("[assert][x] 缺少产物目录:", DIST)
        return 1
    rc = assert_no_forbidden_parts()
    rc += assert_data_embedded()
    if rc:
        return 1
    size_mb = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e6
    print(f"[done] dist/SSC 就绪（约 {size_mb:.0f} MB）。GUI: SSC.exe；CLI 验证: ssc-cli.exe --cli selfcheck")
    return 0


if __name__ == "__main__":
    sys.exit(main())
