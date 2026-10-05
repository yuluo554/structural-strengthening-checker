# data/synthetic 合成方案样本与真值

- 生成器：`src/structural_strengthening_checker/datagen/gen_plan.py`（M1 实装），python-docx + 固定 seed。
- 产物：基线全合规文档 + 注入已知错误的文档 + truth.json（含 doc sha256、expected_verdict、also_expect）。
- 本目录只入仓**少量人工抽查样本**；全量基准产物现场生成（可复现），sha256 变动记入 data/README 台账。
- 真值语义：注入项记主期望；隐含结论记 also_expect；评测按"文档全部非 pass 集合"对账（plan/05 §四）。
