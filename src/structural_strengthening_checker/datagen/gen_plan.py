"""合成加固方案生成器（M1 实装）：python-docx，固定 seed，注入已知错误输出真值 JSON。

真值语义一次定清（评测按"文档全部非 pass 集合"对账，plan/05 §四）：
- 注入项记主期望 expected_verdict；
- 同一注入隐含的其余结论记 also_expect；
- 多报 also_expect 之外的问题算误报（误报 0 目标口径）。
"""

from __future__ import annotations

# 注入错误类型与规则库 rule_id 一一对应（M1 起逐类实装）
INJECTION_TYPES = (
    "adhesive_grade_low",        # 胶粘剂安全性能指标低于限值（R-ADH-001）
    "anchor_depth_insufficient", # 锚固/植筋深度不足（R-ANCH-001）
    "missing_appraisal_first",   # 漏"先鉴定后加固"环节（R-APP-001）
    "missing_unloading",         # 构造措施缺失：卸载/支撑要求未提（R-CONST-001）
    "material_grade_low",        # 材料强度等级标注不足（P1 扩展）
    "crack_repair_wrong",        # 裂缝修补方式与规范不符（P2 扩展）
)


def main() -> int:
    print("合成方案生成器在 M1 实装（plan/05 §四）；注入类型清单:")
    for t in INJECTION_TYPES:
        print(f"  - {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
