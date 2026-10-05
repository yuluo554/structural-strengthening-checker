"""公式引擎：验算模块注册表 + 条款门控 + 参数校验 + 统一执行入口。

设计（plan/03 §3.1）：
- 每个验算模块用 @register_calc 注册：module_id / 名称 / 所需条款集合 / 参数 schema / compute 函数；
- run_calc 的执行顺序是纪律本身：①模块存在 → ②条款门控（全部 status=已核对）→
  ③参数校验（范围/类型）→ ④compute。任何一步不满足都到不了数值计算；
- compute 返回 CalcResult 形状的 dict（plan/04 §1.3），逐步骤挂公式编号与依据条款。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .clauses import ClauseStore
from .errors import SSCError
from .validate import validate_params


@dataclass
class CalcModule:
    module_id: str
    name: str
    description: str
    required_clauses: List[str]
    param_schema: Dict[str, Dict[str, Any]]
    compute: Callable[[Dict[str, Any], ClauseStore], Dict[str, Any]]


CALC_REGISTRY: Dict[str, CalcModule] = {}


def register_calc(
    module_id: str,
    name: str,
    description: str,
    required_clauses: List[str],
    param_schema: Dict[str, Dict[str, Any]],
) -> Callable:
    """注册验算模块。module_id 重复视为程序错误直接抛错。"""

    def deco(fn: Callable[[Dict[str, Any], ClauseStore], Dict[str, Any]]) -> Callable:
        if module_id in CALC_REGISTRY:
            raise ValueError(f"验算模块 module_id 重复注册: {module_id}")
        CALC_REGISTRY[module_id] = CalcModule(
            module_id=module_id,
            name=name,
            description=description,
            required_clauses=list(required_clauses),
            param_schema=param_schema,
            compute=fn,
        )
        return fn

    return deco


def get_module(module_id: str) -> CalcModule:
    if module_id not in CALC_REGISTRY:
        raise SSCError(
            f"未注册的验算模块: {module_id}（可用: {', '.join(sorted(CALC_REGISTRY))}）"
        )
    return CALC_REGISTRY[module_id]


def module_readiness(module: CalcModule, store: ClauseStore) -> Dict[str, Any]:
    """模块就绪度：条款核对进度（selfcheck/modules 展示用）。"""
    registered = [cid for cid in module.required_clauses if cid in store]
    verified = [
        cid
        for cid in registered
        if store.get(cid).status == "已核对"
    ]
    return {
        "module_id": module.module_id,
        "name": module.name,
        "clauses_required": len(module.required_clauses),
        "clauses_registered": len(registered),
        "clauses_verified": len(verified),
        "ready": len(verified) == len(module.required_clauses) and bool(module.required_clauses),
    }


def run_calc(module_id: str, params: Dict[str, Any], store: ClauseStore) -> Dict[str, Any]:
    """统一入口：门控 → 校验 → 计算。返回 CalcResult 形状的 dict。"""
    module = get_module(module_id)
    store.require_verified(module.required_clauses)  # FR-A7 条文纪律门控
    validate_params(module.param_schema, params)
    return module.compute(params, store)
