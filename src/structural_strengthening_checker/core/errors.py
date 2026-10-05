"""统一异常体系。CLI 捕获 SSCError 输出友好消息并按约定退出码退出，绝不裸 traceback。

退出码约定：0 成功；1 自检失败/一般错误；2 输入错误或缺少可选依赖组；
3 条文未核对被请求进入计算路径（条文纪律红线）。
"""

from __future__ import annotations

from typing import Optional


class SSCError(Exception):
    """本工具所有受控异常的基类。"""


class ValidationError(SSCError):
    """输入参数卡/数据 schema 校验失败。message 中逐字段列出问题。"""


class ClauseNotVerifiedError(SSCError):
    """条文纪律（FR-A7）：status≠已核对（或未登记）的条款不得进入计算路径。"""

    def __init__(self, unverified: "list[str]", unregistered: "list[str]") -> None:
        self.unverified = unverified
        self.unregistered = unregistered
        parts = []
        if unregistered:
            parts.append("条款库中未登记: " + ", ".join(unregistered))
        if unverified:
            parts.append("status=待核对: " + ", ".join(unverified))
        super().__init__(
            "条文未核对，拒绝进入计算路径（plan/05 条文核对流程）——"
            + "；".join(parts)
        )


class MissingExtraError(SSCError):
    """可选依赖组未安装。message 必须带安装提示，CLI 据此降级退出。"""

    def __init__(self, extra: str, purpose: str, pip_extra: Optional[str] = None) -> None:
        self.extra = extra
        self.purpose = purpose
        target = pip_extra or extra
        super().__init__(
            f"缺少可选依赖组 [{extra}]（用于{purpose}）。"
            f"请执行: py -m pip install -e .[{target}]（或 pip install {target} 的等效命令）"
        )
