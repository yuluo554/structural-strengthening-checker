# HANDOFF-M4（M3 方案核查 → M4 内置基准交接快照）

> 用法：新对话输入 `/goal 读取 "plan/HANDOFF-M4.md" 继续完成 M4 内置基准里程碑`（从仓库根运行；路径用相对路径，防本机路径进历史）。
> 上一里程碑：M3 方案核查与检查单（✅ 2026-10-05，plan/00 状态表已回写；判定口径决策见 plan/06 M3 各行）。

## 一、当前进度（M3 交付态）

- **解析层实装**：`parsing/docx_text.py` 完整版（docx 逐段+PDF 逐页；损坏/加密/缺文件/无文本层
  统一 `ParseError` 受控降级——CLI 按 plan/03 §三输出"可解析段落 0"+全部规则 needs_confirm，
  绝不 traceback、绝不产生 fail；中文路径回归测试锁定）。
- **参数卡抽取实装**：`parsing/param_card_builder.py`（正则+槽位：methods / materials /
  adhesive_indices / anchor_depths / **design_params（M3 新增槽位）** / unloading / crack_repairs /
  appraisal_first），每项带 evidence；quote 非原文子串 → 丢弃并留痕 `card.notes` +
  `evidence_issues()` 独立复核（FR-B5 防幻觉双闸）。ValueItem 增 `label` 字段（牌号/等级）。
  appraisal_first 刻意不用裸词"鉴定/检测"（基线材料段有"安全性鉴定要求"GB 50728 引文语境，
  裸词会误判——证据词表见模块 docstring）。
- **规则引擎三级判定实装**（`checking/engine.py`）：param_range 数值比对（R-ADH-001 胶等级
  分档区间比对 [min,max]→pass/suspicious/fail；R-ANCH-001 需求下限筛查）+ checklist 存在性
  （R-APP-001）+ param_required 缺失型（R-CONST-001）；规则 status≠已核对一律 needs_confirm；
  未知目标组合兜底 needs_confirm；`CheckReport.non_pass_rule_ids()` 供基准对账。
- **R-ANCH-001 口径（M3 决策，plan/06）**：最有利假设需求下限筛查——αspt 表15.2.3 全列最小
  （内插）、fbd 表15.2.4 该胶等级/基材等级最高档、ψbr·ψw·ψT=1.0·1.1·1.0、ψae=1.0；
  标注深度<下限⇒fail（可证不足）；≥下限⇒pass（报告注明精确复核走 ssc calc）；输入缺失
  （牌号无法映射/基材等级不在表列/缺直径）⇒needs_confirm。fy 由牌号按新增条款
  GB50010-2010-4.2.3（表4.2.3-1，建研院防火所挂载 2024 年版表格图片目视核对，渠道已登记
  standards_raw/README）映射。锚固系数常量与条款库 limits 由
  test_check_layer_limits_match_clause_json 锁死。
- **CLI 实装**：`ssc check`（文本/`--json`/`--report DIR` 三出口；结论行+证据摘录+假设披露+
  汇总+免责声明；核查完成即 exit 0，结论看报告）——plan/03 §五 M3 范围内 docx 报告导出留 M4；
  `ssc checklist`（`--doc` auto_text 自动建议（检出关键词→符合/未检出→待确认，绝不自动不符合）/
  `--interactive` 逐项核对 1-4/s/q+备注（EOF 优雅终止）/`--fill` 渲染符合性清单（非法选项标注
  不中断）/`--out` 留痕 JSON）。
- **端到端对账（M3 DoD 超额完成）**：合成方案语料 6/6（seed=20261005：基线+5 注入），
  `ssc check --json` 的 non_pass 集合与 truth.expected_non_pass 逐份一致（基线 0 误报），
  tests/test_cli.py::test_check_end_to_end_corpus_reconciliation 锁死；入仓样本与生成器现跑
  产物 sha256 逐字节一致（M3 复核无漂移）。
- 条款库 **52 条**（新增 GB/T 50010-2010-4.2.3，51 已核对/1 待核对 JGJ145-6.3 不变）；
  pytest **118 项全绿**（M2 86 → +解析层 12 + 判定矩阵 10 + CLI 端到端 10）；
  selfcheck SELFCHECK_OK（52 条/4 规则互斥 OK/11 检查单/bench 14/14）。

## 二、M4 待办（内置基准达标，DoD 见 plan/05 §五 M4）

1. **`ssc bench` 扩展 check 基准**（bench/check_bench.py 骨架待建）：现场 gen_plan.generate
   （seed 固定，不背产物）→ 逐份 check → 对账口径=文档全部非 pass 集合 vs truth
   （expected_non_pass + also_expect）→ 指标：检出率、**误报 0**、判定准确率；
2. **指标门槛进测试断言**（检出率达标、误报 0）并进 CI；**指标表进 README**；
3. `ssc report` docx 导出实装（FR-D1/D2：验算书+核查报告，免责声明+签署栏+0 外链）——
   plan/03 命令面把 report 排 M4/M5，M3 遗留的 `--report` 目录现在只写 JSON，docx 在此补；
4. M4 DoD：验算算例通过率 100%（已达成，bench 14/14 常驻）+ 方案核查检出率/误报 0 达标 +
   基准一条命令复现（`ssc bench`）+ CI 常驻；
5. **既定口径固化**（plan/05 §五 M4）：基准达标后把"动了会打挂基准"的约定扩充为
   "指标门槛+接口签名"完整清单回写 HANDOFF-M5 §三。

## 三、既定口径清单（M2 版 + M3 增补，动了会打挂基准/纪律，改前先对照）

- **条文纪律红线**：status≠已核对（或未登记）的条款不得进入计算路径；引擎级门控在 run_calc 内、
  先于参数校验（tests/test_engine_gating.py 锁死顺序）。**M3 延伸**：核查层同样吃 status 纪律——
  规则 status≠已核对 → needs_confirm，绝不 fail；数值判定前 store.require_verified 支撑条款
  （ANCHOR_SUPPORT_CLAUSES），任一未核对 → needs_confirm。
- **status=已核对 ⇔ source.checked_date 非空**；无出处的值不得以确定语气落库。
- **代码表值↔条款库双出口一致**：calc/common.py 表值与条款库 limits 由
  test_code_tables_match_clause_json 锁死；**M3 新增同构锁**：checking/engine.py 锚固系数常量
  （ANCHOR_FORMULA_COEF 等 5 个）+ GB50010 fy 映射锚点由
  test_check_layer_limits_match_clause_json 锁死——改任何一侧必须同步另一侧。
- **算例真值必有来源**；容差 ±0.5%（相对）+ verdict 严格相等；真值键名=CalcResult.metrics 键。
- **参数扫描金标准哈希**：tests/test_param_sweep.py GOLDEN_SHA256——改公式/判定/warnings 文案
  都会变哈希，有意修改按模块 docstring 流程重算回填。
- **三态判定口径（M2 定稿）**：满足/需调整/不满足（定义见 plan/04 §1.3）；改口径必须重跑
  bench+参数扫描。
- **方案核查三级判定口径（M3 定稿，plan/06 M3 各行）**：fail=文档自身可证不足（低于限值/
  缺失型要求确无描述/未标注且规则 message 覆盖）；suspicious=介于多档适用限值间"不能排除"；
  needs_confirm=证据不足/无法建立限值/规则依据未核对/解析降级；pass=该规则筛查未发现问题。
  **对账=非 pass 集合（与顺序无关）**；R-ANCH-001 需求下限口径与 R-ADH-001 区间口径改动
  会直接打挂端到端对账测试与 M4 基准。
- **解析降级纪律（plan/03 §三）**：ParseError/零段落 → 全部规则 needs_confirm，不产生任何 fail
  （test_check_corrupt_docx_degrades_no_fail 等锁死）。
- **规则门控关键词跨类目互斥**（check_gate_mutex + 测试锁死），门控对全部 check_type 生效；
  R-CONST-001 门控词=加固方法名（缺失型检查；test_repo_rconst_gate_uses_method_names 锁死）。
- **生成器确定性**：全部随机量出自 random.Random(seed)；docx zip 时间戳归一 (1980,1,1)；
  truth.json 不含时间戳；注入与 rule_id 一一对应（INJECTION_RULE_MAP），also_expect 恒空直到
  出现多规则注入。**改生成器文案=改语料=改 sha256 台账+端到端测试，须同步。**
- **appraisal_first 证据词表**：程序性鉴定证据词（检测鉴定/鉴定报告/鉴定结论/抗震鉴定/先检测/
  鉴定机构），刻意排除裸词"鉴定/检测"（防"安全性鉴定要求"误判）——改词表须重跑端到端对账。
- **核心层（core/calc/checking/parsing 的证据结构）只 import stdlib**（checking/engine.py import
  calc.common 属核心层内部、stdlib only ✓）；PySide6/python-docx/pypdf 只能进 extras 且必须
  惰性导入（tests/test_lazy_deps.py + test_project_guards.py 守门）。
- **语法限 3.8**：带注解模块一律 `from __future__ import annotations`；CLI 输出禁 emoji（GBK）。
- **可选参数 schema 约定（M2 起）**：param_schema 条目可带 `"required": false`；计算体内
  "条件必填"在 compute 内抛 ValidationError。
- 退出码约定：0 成功（**M3 起：check/checklist 核查完成即 0，结论看报告**）/ 1 自检失败 /
  2 输入或缺 extras / 3 条文门控拦截。
- 品牌隔离：文档不提姊妹项目业务领域；HANDOFF 用法行一律相对路径。
- 版权红线：规范全文永不入仓（_private/）；扫描件/表格截图仅存 output/ 或 _private/；
  入仓条目=要点转述+≤2句短摘录+出处+status。
- **基准语义 M4 达标后**，本清单扩充为"指标门槛+接口签名"完整既定口径，改数据/加类目必重跑基准。

## 四、本机环境坑（只写实测，M2 版 + M3 增补）

- 本机唯一解释器 `py`=3.8.8；跑脚本一律 `py -X utf8`，全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip）。
- pip 需绕代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...`。
- `ssc.exe` 装在 `...\Python38\Scripts`（不在 PATH）；用 `py -X utf8 -m structural_strengthening_checker ...` 代替。
- 系统 Python 已存量安装 python-docx/pypdf/Pillow——extras 缺失降级路径靠测试内 monkeypatch
  模拟，勿信本机探测。
- Git Bash 下 `/tmp` 与 Windows Python 不通；临时文件用仓库内 `output/`（已 gitignore）。
- 本机 curl 可用；知乎/baidu 文库/scribd/soujianzhu/morgain 全部 403 或登录墙，勿再试；
  midasuser.com 手册页 WebFetch 403（M3 实测）；渠道黑名单见 data/standards_raw/README.md。
- **规范全文检索路径（M3 实测可用）**：Z.ai WebSearch 可命中建研院防火所（gf.cabr-fire.com）
  等机构挂载全文；Bing/DuckDuckGo 直连 curl 被墙或无机结果；建标库站内搜索纯 JS 不可静态抓取
  （书页需先拿书号，GB 50010 书号未取得——本次走建研院渠道绕过）。
- **PDF 图像提取**：pypdf `page.images` 可直接抽取 gqxh 扫描件图块；网页表格图片直接 curl 下载
  后用 Read 工具目视核对（M3 用此法核表4.2.3-1，同 M2 gqxh 拼版思路）。
- pytest 输出摘要行可能被 warnings 块淹没——看退出码（`echo $?`）或 `--tb=no -p no:warnings`。
- runpy 以 `py -m ...datagen.gen_plan` 直跑有 RuntimeWarning（包 __init__ 先 import），无实际影响；
  测试内用 `gen_plan.generate()` 调用。
- pytest 测试间共享 `DEMO_PARAMS`（tests/test_engine_gating.py）——改模块参数 schema 时同步该字典。

## 五、M3 DoD 复核（逐项）

- [x] 门控关键词互斥测试绿：test_checking/test_m1_data + selfcheck "规则门控互斥: OK"
- [x] 解析失败降级路径测试绿：损坏 docx/缺文件/空文档/无文本层 PDF → 全 needs_confirm、0 fail
- [x] 人工用 1 份合成方案跑通端到端：CLI 全语料 6/6 现跑对账（含 case02/case04 现场生成），
      non_pass 集合与 truth 一致、基线 0 误报；test_check_end_to_end_corpus_reconciliation 锁死
- [x] `ssc check` 实装（文本/JSON/报告 JSON 三出口）+ `ssc checklist` 实装（--doc/--interactive/--fill/--out）
- [x] 参数卡抽取实装（7+1 槽位全带证据，防幻觉双闸）
- [x] 规则引擎三级判定实装（4 规则全可自动判定 + status 纪律 + 兜底纪律）
- [x] GB/T 50010-2010 表4.2.3-1 补核入库（新渠道登记 + 台账行 + 对账测试）
- [x] 台账回写：plan/00·05·06、data/README、standards_raw/README
- [x] git 提交入库
- 偏差说明：无新增偏差。遗留：JGJ 145-2013 §6.3 渠道不可达保持待核对（不阻塞 M4）；
  plan/03 §五 `ssc check --report` 的 docx 报告导出按命令面"M4/M5"排期留 M4（当前写 JSON）；
  裂缝修补规则为 P1/P2 扩展（抽取槽位已就绪、规则未入库，M4 基准不受影响）。

## 六、关键命令速查

```bash
# 测试与自检（仓库根）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest --tb=no -p no:warnings -q
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker selfcheck
# 方案核查（端到端三出口）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker check data/synthetic/samples/case01_seed20261005.docx
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker check output/gen/case05_seed20261005.docx --json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker check data/synthetic/samples/baseline_seed20261005.docx --report output/m3_report
# 检查单三种用法
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker checklist --doc data/synthetic/samples/baseline_seed20261005.docx --out output/ckl.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker checklist --interactive --out output/ckl.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker checklist --fill output/ckl.json
# 基准（M4 扩展点；当前 14/14）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker bench
# 合成方案生成（M4 check 基准现场生成用）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker.datagen.gen_plan --out output/gen --seed 20261005 --count 5
# 安装（新环境）
py -m pip install -U pip && NO_PROXY="*" no_proxy="*" py -m pip install -e .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple
```
