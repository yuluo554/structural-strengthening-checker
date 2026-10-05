"""CLI 入口（console script `ssc`，或 py -X utf8 -m structural_strengthening_checker）。

命令面见 plan/03 §五。M3 起 check / checklist 实装：
- check：docx/PDF → 文本提取 → 参数卡 → 规则引擎三级判定 → 结论输出（解析失败整体降级）；
- checklist：GB 55021 条目一览 / --doc auto_text 建议 / --interactive 逐项核对 / --fill 渲染留痕。

退出码：0 成功（含"核查完成但有不符合项"——结论看报告，不看退出码）；
1 自检失败/一般错误；2 输入错误或缺可选依赖组；3 条文未核对门控拦截。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

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

VERDICT_LABELS = {
    "fail": "不符合",
    "suspicious": "疑似",
    "needs_confirm": "待人工确认",
    "pass": "通过",
}

DISCLAIMER = "免责声明：本工具为辅助验算与核查工具，输出不替代正式设计文件与施工图审查。"


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

    p_calc = sub.add_parser("calc", help="执行验算（M2 实装计算体）")
    p_calc.add_argument("module", help="验算模块 id（见 ssc modules）")
    p_calc.add_argument("--input", required=True, help="参数卡 JSON 文件")

    p_check = sub.add_parser("check", help="加固方案文本核查（docx/PDF → 参数卡 → 三级判定）")
    p_check.add_argument("plan_file", help="方案文件（.docx/.pdf）")
    p_check.add_argument("--json", action="store_true", help="以 JSON 输出完整核查报告")
    p_check.add_argument("--report", default=None, metavar="DIR",
                         help="将核查报告 JSON 写入指定目录（check_report.json）；docx 报告 M4 实装")

    p_ckl = sub.add_parser("checklist", help="GB 55021-2021 检查单（一览 / --doc 建议 / --interactive 逐项核对 / --fill 渲染）")
    p_ckl.add_argument("--doc", default=None, metavar="FILE",
                       help="方案文件：auto_text 条目自动给核对建议")
    p_ckl.add_argument("--interactive", action="store_true",
                       help="逐项交互核对（终端输入选择与备注）")
    p_ckl.add_argument("--fill", default=None, metavar="FILE",
                       help="加载核对结果 JSON 渲染符合性清单（不再交互）")
    p_ckl.add_argument("--out", default=None, metavar="FILE",
                       help="核对结果保存路径（--interactive/--doc 模式下可用）")

    sub.add_parser("bench", help="内置基准（M4 达标；当前验算基准可跑）")

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
        f"算例库: {bench['total']} 例（通过 {bench['passed']} / 未通过 {bench['failed']} / "
        f"门控阻塞 {bench['blocked_by_clauses']}）"
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
    cap = result["capacity"]
    ratio = result["ratio"]
    ratio_text = f"{ratio['value']:.3f}" if ratio.get("value") is not None else "N/A"
    cap_text = f"{cap['value']:.4f}".rstrip("0").rstrip(".") if cap.get("value") is not None else "N/A"
    print(f"验算结论: [{result['verdict']}] {module.name}")
    print(f"  特征值(capacity) = {cap_text} {cap['unit']}；效应比({ratio['meaning']}) = {ratio_text}")
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"  [提示] {w}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


# ---------------------------------------------------------------------------
# ssc check（M3 实装）
# ---------------------------------------------------------------------------

def _fmt_quote(quote: Optional[str], width: int = 42) -> str:
    if not quote:
        return ""
    q = quote.replace("\n", " ")
    return q if len(q) <= width else q[: width - 1] + "…"


def _print_finding(f, prefix: str = "  ") -> None:
    label = VERDICT_LABELS.get(f.verdict, f.verdict)
    print(f"{prefix}[{f.verdict} {label}] {f.rule_id} {f.rule_name}")
    print(f"{prefix}    结论: {f.message}")
    print(f"{prefix}    依据: {f.clause_id or '（文档级证据问题）'}")
    if f.advice:
        print(f"{prefix}    建议: {f.advice}")
    ev = f.evidence or {}
    if f.rule_id == "EVIDENCE" or not ev:
        return
    if "items" in ev:
        for i, item in enumerate(ev["items"], 1):
            q = _fmt_quote(item.get("quote"))
            loc = f"段 {item['para']}" if item.get("para") else ""
            print(f"{prefix}    证据{i}: {q}（{loc}）")
            extras = {k: v for k, v in item.items()
                      if k not in ("quote", "para", "page") and v is not None}
            if extras:
                print(f"{prefix}      数值: {json.dumps(extras, ensure_ascii=False)}")
    else:
        q = _fmt_quote(ev.get("quote"))
        if q:
            loc = f"段 {ev['para']}" if ev.get("para") else ""
            print(f"{prefix}    证据: {q}（{loc}）")
        extras = {k: v for k, v in ev.items()
                  if k not in ("quote", "para", "page", "assumptions") and v is not None}
        if extras:
            print(f"{prefix}      数值: {json.dumps(extras, ensure_ascii=False)}")
        for a in ev.get("assumptions") or []:
            print(f"{prefix}      假设: {a}")


def _check_report_json(report, card, paras_count: int) -> Dict:
    return {
        "doc": {"name": report.doc_name, "sha256": card.doc_sha256,
                "parseable_paras": paras_count, "degraded": report.degraded},
        "methods": [m.name for m in card.methods],
        "summary": report.summary(),
        "non_pass_rule_ids": report.non_pass_rule_ids(),
        "findings": [
            {
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "verdict": f.verdict,
                "message": f.message,
                "clause_id": f.clause_id,
                "advice": f.advice,
                "evidence": f.evidence,
            }
            for f in report.findings
        ],
        "disclaimer": DISCLAIMER,
    }


def _cmd_check(args) -> int:
    from .checking.engine import check_plan
    from .checking.rules import RuleStore
    from .core.errors import ParseError
    from .parsing.docx_text import extract_paras
    from .parsing.param_card_builder import build_param_card

    plan_path = Path(args.plan_file)
    data_dir = find_data_dir(args.data_dir)
    store = ClauseStore(data_dir / "knowledge")
    rules = RuleStore(data_dir / "knowledge")
    if rules.issues:
        for issue in rules.issues:
            print(f"  [x] 规则库问题: {issue}")
        return EXIT_ERROR

    doc_sha256 = None
    parse_failed = False
    parse_note = ""
    try:
        doc_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    except OSError as exc:
        print(f"[输入] 无法读取方案文件: {exc}")
        return EXIT_INPUT
    try:
        paras = extract_paras(plan_path)
    except MissingExtraError as exc:
        print(f"[缺少依赖] {exc}")
        return EXIT_INPUT
    except ValueError as exc:
        print(f"[输入] {exc}")
        return EXIT_INPUT
    except ParseError as exc:
        # 降级纪律（plan/03 §三）：解析失败不产生任何 fail，整体降级 needs_confirm
        paras = []
        parse_failed = True
        parse_note = str(exc)

    card = build_param_card(paras, doc_name=plan_path.name, doc_sha256=doc_sha256)
    report = check_plan(card, rules, store, parse_failed=parse_failed)

    if args.json:
        print(json.dumps(_check_report_json(report, card, len(paras)),
                         ensure_ascii=False, indent=2))
    else:
        method_txt = "、".join(m.name for m in card.methods) or "未检出加固方法"
        print(f"方案核查: {report.doc_name}（可解析段落 {len(paras)}；方法: {method_txt}）")
        if parse_failed:
            print(f"  [解析失败] {parse_note}")
            print("  [降级] 按 plan/03 降级纪律输出全部规则的待人工确认清单，不产生任何自动 fail。")
        for f in report.findings:
            _print_finding(f)
        s = report.summary()
        print(
            f"汇总: 不符合 {s['fail']} / 疑似 {s['suspicious']} / "
            f"待人工确认 {s['needs_confirm']} / 通过 {s['pass']}"
        )
        print(DISCLAIMER)

    if args.report:
        out_dir = Path(args.report)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "check_report.json"
        out_path.write_text(
            json.dumps(_check_report_json(report, card, len(paras)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"核查报告 JSON 已写入: {out_path}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# ssc checklist（M3 实装：一览 / --doc 建议 / --interactive 逐项核对 / --fill 渲染）
# ---------------------------------------------------------------------------

def _doc_full_text(path: Path) -> str:
    from .parsing.docx_text import extract_paras

    paras = extract_paras(path)
    return "\n".join(p.text for p in paras)


def _auto_text_suggestion(item, doc_text: str):
    """auto_text 条目建议：检出关键词→建议符合；未检出→待确认。

    刻意不自动给"不符合"（宁缺勿错）：关键词未出现≠条款不满足，须人工复核。
    """
    hits = [kw for kw in item.keywords if kw in doc_text]
    if hits:
        return "符合", f"检出关键词: {'、'.join(hits)}"
    return "待确认", "未检出相关表述，需人工复核"


def _load_answers(path: Path) -> Dict[str, Dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SSCError(f"无法读取核对结果文件: {exc}")
    except json.JSONDecodeError as exc:
        raise SSCError(f"核对结果文件不是合法 JSON: {exc}")
    if not isinstance(data, dict):
        raise SSCError("核对结果文件应为 {item_id: {choice, note}} 形式的 JSON 对象")
    return data


def _render_filled(ckl, answers: Dict[str, Dict[str, str]]) -> List[str]:
    lines = [f"GB 55021-2021 强制条款符合性清单（核对结果 {len(answers)} 项 / 共 {len(ckl.items)} 项）"]
    counts: Dict[str, int] = {}
    for item in ckl.items:
        ans = answers.get(item.item_id) or {}
        choice = ans.get("choice", "待确认")
        note = ans.get("note", "")
        counts[choice] = counts.get(choice, 0) + 1
        valid = item.options
        mark = "" if choice in valid else "  <- 非法选项（应为 " + "/".join(valid) + "）"
        lines.append(f"  [{choice}] {item.item_id}（条号 {item.clause_no or '待回填'}）{item.gist}{mark}")
        if note:
            lines.append(f"        备注: {note}")
    summary = " / ".join(f"{k} {v}" for k, v in counts.items())
    lines.append(f"汇总: {summary}")
    lines.append(DISCLAIMER)
    return lines


def _cmd_checklist(args) -> int:
    from .checking.checklist_gb55021 import ChecklistStore

    data_dir = find_data_dir(args.data_dir)
    ckl = ChecklistStore(data_dir / "knowledge")
    if ckl.issues:
        for issue in ckl.issues:
            print(f"  [x] {issue}")
        return EXIT_ERROR

    answers: Dict[str, Dict[str, str]] = {}

    if args.fill:
        answers = _load_answers(Path(args.fill))
        for line in _render_filled(ckl, answers):
            print(line)
        return EXIT_OK

    doc_text = ""
    if args.doc:
        doc_path = Path(args.doc)
        try:
            doc_text = _doc_full_text(doc_path)
        except MissingExtraError as exc:
            print(f"[缺少依赖] {exc}")
            return EXIT_INPUT
        except SSCError as exc:  # ParseError
            print(f"[解析失败] {exc}")
            return EXIT_INPUT
        except ValueError as exc:
            print(f"[输入] {exc}")
            return EXIT_INPUT

    if args.interactive:
        print(f"GB 55021-2021 检查单逐项核对（共 {len(ckl.items)} 项；选项：1 符合 / 2 不符合 / 3 不适用 / 4 待确认，s 跳过，q 结束并保存）")
        for item in ckl.items:
            print(f"\n- {item.item_id}（条号 {item.clause_no or '待回填'}）[{item.check_mode}]")
            print(f"  要点: {item.gist}")
            if item.advice:
                print(f"  核查提示: {item.advice}")
            if item.check_mode == "auto_text" and doc_text:
                sug, why = _auto_text_suggestion(item, doc_text)
                print(f"  自动建议: {sug}（{why}）")
            try:
                raw = input("  你的判定 [1-4/s/q]: ").strip().lower()
            except EOFError:
                print("\n[输入结束] 已答项如下（未答项记待确认）。")
                break
            if raw == "q":
                break
            if raw == "s" or raw == "":
                continue
            if raw in ("1", "2", "3", "4"):
                choice = ("符合", "不符合", "不适用", "待确认")[int(raw) - 1]
                try:
                    note = input("  备注（可回车省略）: ").strip()
                except EOFError:
                    note = ""
                answers[item.item_id] = {"choice": choice, "note": note}
            else:
                print("  [跳过] 无效输入。")
        for line in _render_filled(ckl, answers):
            print(line)
        if args.out:
            Path(args.out).write_text(
                json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"核对结果已保存: {args.out}")
        return EXIT_OK

    # 默认：条目一览（--doc 时附自动建议，不交互）
    mode = "（--doc 自动建议模式）" if doc_text else ""
    print(f"GB 55021-2021 检查单条目: {len(ckl.items)} 项{mode}")
    for item in ckl.items:
        line = f"  - {item.item_id}（条号 {item.clause_no or '待核对回填'}）{item.gist}"
        print(line)
        extra = f"核对方式 {item.check_mode} / status={item.status}"
        if doc_text and item.check_mode == "auto_text":
            sug, why = _auto_text_suggestion(item, doc_text)
            extra += f" / 建议 {sug}（{why}）"
        print(f"      {extra}")
    if not doc_text:
        print("提示: --doc <方案文件> 可对 auto_text 条目自动建议；--interactive 逐项核对；--fill 渲染留痕清单。")
    if args.out and doc_text:
        answers = {}
        for item in ckl.items:
            if item.check_mode == "auto_text":
                sug, why = _auto_text_suggestion(item, doc_text)
                answers[item.item_id] = {"choice": sug, "note": why, "mode": "auto_text"}
            else:
                answers[item.item_id] = {"choice": "待确认", "note": "manual 条目需人工核对", "mode": "manual"}
        Path(args.out).write_text(
            json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"建议清单已保存: {args.out}")
    return EXIT_OK


def _cmd_bench(args) -> int:
    data_dir = find_data_dir(args.data_dir)
    store = ClauseStore(data_dir / "knowledge")
    bench = run_calc_bench(data_dir, store=store)
    print("验算基准（真值比对：verdict 严格相等 + 数值 ±0.5% 相对容差，口径 plan/05 §三）")
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
        print("桌面界面在 M5 实装（plan/05 §五）；当前可用 CLI: ssc selfcheck / modules / calc / check / checklist / bench。")
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
