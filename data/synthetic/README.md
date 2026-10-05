# data/synthetic 合成方案样本与真值

- 生成器：`src/structural_strengthening_checker/datagen/gen_plan.py`（**M1 已实装 v1**），python-docx + 固定 seed。
- 产物：基线全合规文档（clean_baseline: true）+ 注入已知错误的文档 + truth.json（含 doc sha256、expected_verdict、also_expect）。
- 本目录只入仓**少量人工抽查样本**（`samples/`，seed=20261005：基线 + R-ADH-001/R-APP-001/三重组合 + truth.json）；
  全量基准产物现场生成（可复现），sha256 变动记入 data/README 台账。
- 真值语义：注入项记主期望 expected_verdict；隐含结论记 also_expect（v1 四类注入互不隐含，恒为空）；
  评测按"文档全部非 pass 集合"对账，多报 also_expect 之外的问题算误报（plan/05 §四）。
- 确定性：全部随机量出自 random.Random(seed)；docx zip 时间戳统一归一化为 (1980,1,1)，
  同 seed 两次运行产物 sha256 逐字节一致（M1 DoD，双跑对账通过）。
- 注入类型与规则库联动：adhesive_grade_low→R-ADH-001 / anchor_depth_insufficient→R-ANCH-001 /
  missing_appraisal_first→R-APP-001 / missing_unloading→R-CONST-001（material_grade_low、crack_repair_wrong 为 P1/P2 扩展）。
