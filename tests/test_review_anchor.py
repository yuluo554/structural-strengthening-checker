"""条款复核锚守门（D5）：52 条条款都带 next_review / review_interval。

两层守门：
  ① 结构：每条 source 都有合法 ISO 日期的 next_review 与 review_interval；
  ② 语义：逾期**只提示、不改 status、不影响退出码**——复核结论必须人重新核对后回写，
     工具自动续期等于把「已核对」变成装饰。
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUSES_DIR = REPO_ROOT / "data" / "knowledge" / "clauses"

EXPECTED_TOTAL = 52


def _all_clauses():
    for path in sorted(CLAUSES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("clauses", data) if isinstance(data, dict) else data
        for clause in items:
            yield path.name, clause


def test_all_clauses_have_review_anchors():
    """52 条条款每条都有 next_review 与 review_interval。"""
    missing = []
    total = 0
    for name, clause in _all_clauses():
        total += 1
        src = clause.get("source") or {}
        if not src.get("next_review") or not src.get("review_interval"):
            missing.append(f"{name}::{clause.get('clause_id')}")
    assert missing == [], f"缺少复核锚: {missing}"
    assert total == EXPECTED_TOTAL, f"条款数 {total} != {EXPECTED_TOTAL}"


def test_review_anchor_dates_are_valid_iso():
    """next_review 必须是可解析的 ISO 日期，且晚于 checked_date。"""
    problems = []
    for name, clause in _all_clauses():
        src = clause.get("source") or {}
        cid = clause.get("clause_id")
        try:
            nxt = dt.date.fromisoformat(src.get("next_review") or "")
        except ValueError:
            problems.append(f"{cid}: next_review 非 ISO 日期 {src.get('next_review')!r}")
            continue
        checked = src.get("checked_date")
        if checked:
            try:
                if nxt <= dt.date.fromisoformat(checked):
                    problems.append(f"{cid}: next_review {nxt} 不晚于 checked_date {checked}")
            except ValueError:
                problems.append(f"{cid}: checked_date 非 ISO 日期 {checked!r}")
    assert problems == [], problems


def test_review_interval_is_annual():
    """当前统一年度复核周期（改周期须同时改 data/README 的时效契约）。"""
    bad = [
        f"{clause.get('clause_id')}={src.get('review_interval')!r}"
        for _name, clause in _all_clauses()
        for src in [clause.get("source") or {}]
        if src.get("review_interval") != "annual"
    ]
    assert bad == [], f"非 annual 的复核周期: {bad}"


def test_overdue_only_warns_and_keeps_status(capsys):
    """★ 语义守门：逾期条款只提示，不自动续期、不把 status 改成已核对。

    这是「工具不得替人做复核结论」的可执行证据：即便 next_review 已过期，
    status 仍原样返回，且守门本身不让测试失败（只打印警告）。
    """
    future_ok, overdue = [], []
    for _name, clause in _all_clauses():
        src = clause.get("source") or {}
        try:
            nxt = dt.date.fromisoformat(src.get("next_review") or "")
        except ValueError:
            continue
        (overdue if nxt < dt.date.today() else future_ok).append(clause)

    for clause in overdue:
        src = clause.get("source") or {}
        print(
            "[警告] 条款复核锚已逾期：%s next_review=%s（status 保持 %r，须人工重新核对）"
            % (clause.get("clause_id"), src.get("next_review"), clause.get("status"))
        )

    # 逾期不改变 status：任何条款的 status 仍必须是二态之一，且待核对项仍只有那一条
    statuses = {c.get("status") for _n, c in _all_clauses()}
    assert statuses <= {"已核对", "待核对"}, statuses
    pending = [c["clause_id"] for _n, c in _all_clauses() if c.get("status") == "待核对"]
    assert pending == ["JGJ145-2013-6.3"], f"待核对集合被改动: {pending}"

    # 逾期只是信息：不影响本条测试结果（守门只证明语义，不把过期当红）
    assert len(future_ok) + len(overdue) == EXPECTED_TOTAL
