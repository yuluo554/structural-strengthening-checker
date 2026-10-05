"""零依赖核心层：条款库 / 公式引擎 / 校验 / 路径定位 / 异常体系。

纪律：本层只 import 标准库（plan/03 依赖分层）。
"""

from .errors import ClauseNotVerifiedError, MissingExtraError, SSCError, ValidationError

__all__ = ["SSCError", "ValidationError", "ClauseNotVerifiedError", "MissingExtraError"]
