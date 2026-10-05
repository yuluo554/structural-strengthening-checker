"""参数合法性校验：数值范围/必填字段。数值结论只来自通过校验的确定性计算。"""

from __future__ import annotations

from typing import Any, Dict, List

from .errors import ValidationError


def check_range(sym: str, value: Any, rng: Dict[str, Any], problems: List[str]) -> None:
    """rng 形如 {"min": 0, "max": null, "exclusive": true}；None 值跳过（缺字段另查）。"""
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        problems.append(f"{sym}: 期望数值，得到 {type(value).__name__}")
        return
    exclusive = bool(rng.get("exclusive", False))
    lo, hi = rng.get("min"), rng.get("max")
    if lo is not None:
        if value < lo or (exclusive and value == lo):
            problems.append(f"{sym}={value} 超出合法范围（下限 {lo}{'（不含）' if exclusive else ''}）")
    if hi is not None:
        if value > hi or (exclusive and value == hi):
            problems.append(f"{sym}={value} 超出合法范围（上限 {hi}{'（不含）' if exclusive else ''}）")


def validate_params(param_schema: Dict[str, Dict[str, Any]], params: Dict[str, Any]) -> None:
    """按模块参数 schema 校验：缺字段/越界/类型，逐字段列出问题后一次性抛出。

    schema 条目可带 "required": False（M2 起）：缺省不报错，提供时仍做范围/类型校验。
    """
    missing = [
        sym
        for sym, spec in param_schema.items()
        if spec.get("required", True) and sym not in params
    ]
    problems: List[str] = []
    if missing:
        problems.append("缺少参数: " + ", ".join(missing))
    for sym, spec in param_schema.items():
        if sym in params:
            check_range(sym, params[sym], spec.get("range") or {}, problems)
    if problems:
        raise ValidationError("参数卡校验失败: " + "；".join(problems))
