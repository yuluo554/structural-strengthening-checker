# data/cases 算例库（验算基准真值）

- schema 见 plan/04 §1.7：`case_id / module / input / expected / source` 必填；**无来源的数值不得作为基准真值**（引擎 load_cases 强制）。
- 来源：规范条文说明算例 + 公开教材算例，逐条登记（书名/版次/页码/例题号）；尽量双渠道互证。
- M1 填充：每模块 ≥3 例（一次受力 / 二次受力 / 反向例），共 ≥12 例。
- 容差策略：数值 ±0.5%（写入 tolerance_policy），verdict 严格相等。
