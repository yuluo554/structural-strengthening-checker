"""CLI 入口（console script `ssc`，或 py -X utf8 -m structural_strengthening_checker）。

命令面见 plan/03 §五。骨架期真实可用：--help / selfcheck / modules / calc（门控演示）/ bench / checklist；
check / report / gui 为受控降级（缺 extras 或未实装时友好提示，绝不 traceback）。

退出码：0 成功；1 自检失败/一般错误；2 输入错误或缺可选依赖组；3 条文未核对门控拦截。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .bench.calc_bench import run_calc_bench
from .calc import EXPECTED_MODULES  # noqa: F401  触发模块注册
from .core.clauses import ClauseStore
from .core.engine import CALC_REGISTRY, get_module, module_readiness, run_calc
from .core.errors import ClauseNotVerifiedError, MissingExtraError, SSCError, ValidationError
from .core.paths import find_data_dir

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INPUT = 2
EXIT_CLAUSE_GATE = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ssc",
        description="结构加固验算与加固方案核查工具（全离线；辅助定位，不替代正式设计）",
    )
    parser.add_argument("--version", action="version", version=f"ssc {__version__}")
    parser.add_argument("--data-dir", default=None, help="数据目录（默认自动查找 data/knowledge）")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("selfcheck", help="自检：数据库加载/schema 校验/status 统计/模块注册表/extras 探测")
    sub.add_parser("modules", help="列出已注册验算模块及条文核对进度")

    p_calc = sub.add_parser("calc", help="执行验算（M2 实装计算体；骨架期演示条款门控）")
    p_calc.add_argument("module", help="验算模块 id（见 ssc modules）")
    p_calc.add_argument("--input", required=True, help="参数卡 JSON 文件")

    p_check = sub.add_parser("check", help="加固方案文本核查（M3 实装）")
    p_check.add_argument("plan_file", help="方案文件（.docx/.pdf）")

    sub.add_parser("checklist", help="GB 55021-2021 检查单条目一览（M3 实装交互核对）")

    sub.add_parser("bench", help="内置基准（M4 达标；骨架期如实报告门控阻塞）")

    sub.add_parser("report", help="docx 报告导出（M4 实装）")
    sub.add_parser("gui", help="桌面界面（M5 实装）")
    return parser


def _load_stores(data_dir: Path):
    store = ClauseStore(data_dir / "knowledge")
    from .checking.rules import RuleStore
    from .checking.checklist_gb55021 import ChecklistStore

    rules = RuleStore(data_dir / "knowledge")
    checklist = ChecklistStore(data_dir / "knowledge")
    return store, rules, checklist


def _extras_probe() -> str:
    lines = []
    for extra, modname in (("gui", "PySide6"), ("report", "docx"), ("parse", "pypdf")):
        try:
            __import__(modname)
            lines.append(f"  [{extra}] 已安装")
        except ImportError:
            lines.append(f"  [{extra}] 未安装（按需: py -m pip install -e .[{extra}]）")
    return "\n".join(lines)


def _cmd_selfcheck(args) -> int:
    data_dir = find_data_dir(args.data_dir)
    store, rules, checklist = _load_stores(data_dir)
    print("=== structural-strengthening-checker selfcheck ===")
    print(f"数据目录: {data_dir}")

    cs = store.status_summary()
    print(f"条款库: {cs['total']} 条（已核对 {cs['verified']} / 待核对 {cs['pending']}）")
    rs = rules.status_summary()
    print(f"规则库: {rs['total']} 条（依据已核对 {rs['verified']}）")
    conflicts = rules.check_gate_mutex()
    print(f"规则门控互斥: {'冲突 ' + str(len(conflicts)) if conflicts else 'OK'}")
    ckl = checklist.status_summary()
    print(f"GB 55021 检查单: {ckl['total']} 项（已核对 {ckl['verified']}）")
    bench = run_calc_bench(data_dir, store=store)
    print(
        f"算例库: {bench['total']} 例（可执行待 M2 门控放开；"
        f"当前门控阻塞 {bench['blocked_by_clauses']}）"
    )

    print(f"验算模块: {len(CALC_REGISTRY)} 个")
    failed = False
    for module_id in sorted(CALC_REGISTRY):
        info = module_readiness(CALC_REGISTRY[module_id], store)
        mark = "READY" if info["ready"] else "GATED"
        print(
            f"  - {module_id} [{mark}] "
            f"条款 {info['clauses_verified']}/{info['clauses_required']} 已核对"
        )
    if set(CALC_REGISTRY) != set(EXPECTED_MODULES):
        print(f"  [x] 模块注册表与预期不符: {sorted(CALC_REGISTRY)} != {EXPECTED_MODULES}")
        failed = True
    print("extras 探测:")
    print(_extras_probe())

    all_issues = (
        list(cs["issues"]) + list(rs["issues"]) + list(ckl["issues"]) + list(bench["issues"])
    )
    if conflicts:
        for c in conflicts:
            all_issues.append(f"门控关键词跨类目冲突: {c.keyword!r} -> {c.categories}")
    if all_issues:
        failed = True
        print("发现问题:")
        for issue in all_issues:
            print(f"  [x] {issue}")

    if failed:
        print("SELFCHECK_FAIL")
        return EXIT_ERROR
    print("SELFCHECK_OK")
    return EXIT_OK


def _cmd_modules(args) -> int:
    data_dir = find_data_dir(args.data_dir)
    store = ClauseStore(data_dir / "knowledge")
    print(f"{'module_id':<28} {'名称':<40} 条文进度")
    for module_id in sorted(CALC_REGISTRY):
        info = module_readiness(CALC_REGISTRY[module_id], store)
        mark = "READY" if info["ready"] else "GATED"
        print(
            f"{module_id:<28} {info['name']:<40} "
            f"{info['clauses_verified']}/{info['clauses_required']} [{mark}]"
        )
    return EXIT_OK


def _cmd_calc(args) -> int:
    data_dir = find_data_dir(args.data_dir)
    store = ClauseStore(data_dir / "knowledge")
    module = get_module(args.module)  # 未注册 → SSCError
    try:
        with open(args.input, encoding="utf-8") as fh:
            params = json.load(fh)
    except OSError as exc:
        print(f"[输入] 无法读取参数文件: {exc}")
        return EXIT_INPUT
    except json.JSONDecodeError as exc:
        print(f"[输入] 参数文件不是合法 JSON: {exc}")
        return EXIT_INPUT
    try:
        result = run_calc(module.module_id, params, store)
    except ClauseNotVerifiedError as exc:
        print(f"[条款门控] {exc}")
        return EXIT_CLAUSE_GATE
    except ValidationError as exc:
        print(f"[参数校验] {exc}")
        return EXIT_INPUT
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


def _cmd_check(args) -> int:
    from .checking.engine import check_plan
    from .checking.rules import RuleStore
    from .parsing.docx_text import extract_paras
    from .parsing.param_card_builder import build_param_card

    data_dir = find_data_dir(args.data_dir)
    try:
        paras = extract_paras(Path(args.plan_file))
    except MissingExtraError as exc:
        print(f"[缺少依赖] {exc}")
        return EXIT_INPUT
    except ValueError as exc:
        print(f"[输入] {exc}")
        return EXIT_INPUT
    card = build_param_card(paras, doc_name=Path(args.plan_file).name)
    issues = card.evidence_issues()
    report = check_plan(card, RuleStore(data_dir / "knowledge"), ClauseStore(data_dir / "knowledge"))
    print(f"方案核查: {report.doc_name}（可解析段落 {len(paras)}）")
    for f in report.findings:
        print(f"  [{f.verdict}] {f.rule_id} {f.message}（依据 {f.clause_id}）")
    for issue in issues:
        print(f"  [证据问题] {issue} -> 降级 needs_confirm")
    print(f"汇总: {report.summary()}")
    print("完整核查（规则判定+三级结论）在 M3 实装。")
    return EXIT_OK


def _cmd_checklist(args) -> int:
    from .checking.checklist_gb55021 import ChecklistStore

    data_dir = find_data_dir(args.data_dir)
    ckl = ChecklistStore(data_dir / "knowledge")
    print(f"GB 55021-2021 检查单条目: {len(ckl.items)} 项")
    for item in ckl.items:
        print(f"  - {item.item_id}（条号 {item.clause_no or '待核对回填'}）{item.gist}")
        print(f"      核对方式 {item.check_mode} / status={item.status}")
    print("交互式逐项核对在 M3 实装。")
    if ckl.issues:
        for issue in ckl.issues:
            print(f"  [x] {issue}")
        return EXIT_ERROR
    return EXIT_OK


def _cmd_bench(args) -> int:
    data_dir = find_data_dir(args.data_dir)
    store = ClauseStore(data_dir / "knowledge")
    bench = run_calc_bench(data_dir, store=store)
    print("验算基准（骨架期：如实报告门控阻塞，M2 后出现真值比对结果）")
    print(
        json.dumps(
            {k: v for k, v in bench.items() if k != "details"},
            ensure_ascii=False, indent=2,
        )
    )
    if bench["issues"]:
        for issue in bench["issues"]:
            print(f"  [x] {issue}")
        return EXIT_ERROR
    return EXIT_OK


def _cmd_report(args) -> int:
    try:
        from .report.docx_export import export_calc_book  # noqa: F401
    except MissingExtraError as exc:
        print(f"[缺少依赖] {exc}")
        return EXIT_INPUT
    print("报告导出在 M4 实装（验算书 + 核查报告，含免责声明与签署栏）。")
    return EXIT_OK


def _cmd_gui(args) -> int:
    from .gui.app import launch

    try:
        return launch()
    except MissingExtraError as exc:
        print(f"[缺少依赖] {exc}")
        return EXIT_INPUT
    except NotImplementedError:
        print("桌面界面在 M5 实装（plan/05 §五）；当前可用 CLI: ssc selfcheck / modules / calc / bench。")
        return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_OK

    handlers = {
        "selfcheck": _cmd_selfcheck,
        "modules": _cmd_modules,
        "calc": _cmd_calc,
        "check": _cmd_check,
        "checklist": _cmd_checklist,
        "bench": _cmd_bench,
        "report": _cmd_report,
        "gui": _cmd_gui,
    }
    try:
        return handlers[args.command](args)
    except SSCError as exc:
        print(f"错误: {exc}")
        return EXIT_ERROR
    except NotImplementedError as exc:
        print(f"未实装: {exc}")
        return EXIT_INPUT
