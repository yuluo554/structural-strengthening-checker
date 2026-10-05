"""解析层（方案文本 → 参数卡）。依赖惰性导入，缺 extras 友好降级。"""

from .param_card import Evidence, MethodItem, PlanParamCard, ValueItem

__all__ = ["PlanParamCard", "Evidence", "MethodItem", "ValueItem"]
