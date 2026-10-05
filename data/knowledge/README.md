# data/knowledge 机器可读知识库

- `clauses/*.json`：条款库（schema 见 plan/04 §1.1）。纪律：status=已核对 必须有 source.checked_date；无出处不得以确定语气落库。
- `rules/*.json`：核查规则库（schema 见 plan/04 §1.5）。不同类目 gate.only_if_keywords 必须互斥（引擎 + 测试强制）。
- `checklist_gb55021.json`：GB 55021-2021 检查单条目。

## 当前状态（M1 首批，2026-10-05 核对）

- 条款库 49 条：`gb50367-2013.json`（31 条，10.2 纤维复合材/9.2 粘钢/5.2 增大截面/15.2 植筋/4.4 胶粘剂/3.1/5.1.5）、
  `gb55021-2021.json`（16 条，正文强制条款+附录A/B 材料与胶指标）、`gb50728-2011.json`（1 条，4.2.2）、
  `jgj145-2013.json`（1 条，**待核对**——渠道熔断记录见 data/standards_raw/README.md）。
- 规则库 4 条（adhesive/anchoring/appraisal/unloading 四类目，关键词互斥测试锁死），限值依据全部指向已核对条款。
- 检查单 11 项（GB 55021-2021 真实条号回填，含全文强制条款）。
- M0 骨架占位条目（clauses_skeleton.json / rules_skeleton.json）已删除；占位条号 4.5.5 的章节归属
  已按原文修正为 4.4.x + GB 50728-2011 4.2.2 + GB 55021-2021 附录B（详见 data/README 偏差记录）。
- **表值类数据（表10.2.8/9.2.9/15.2.3/15.2.4/4.3.4/4.3.5 等）在可达渠道均为图片，limits 中以
  `value: null + note` 留痕，M2 以正式出版文本补核——不得以记忆值预填。**
