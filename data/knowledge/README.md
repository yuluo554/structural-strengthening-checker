# data/knowledge 机器可读知识库

- `clauses/*.json`：条款库（schema 见 plan/04 §1.1）。纪律：status=已核对 必须有 source.checked_date；无出处不得以确定语气落库。
- `rules/*.json`：核查规则库（schema 见 plan/04 §1.5）。不同类目 gate.only_if_keywords 必须互斥（引擎 + 测试强制）。
- `checklist_gb55021.json`：GB 55021-2021 检查单条目。

当前为骨架占位条目（status 全部=待核对）：**限值与公式系数一律 M1 按规范原文核对后回填，禁止预填记忆值**。
