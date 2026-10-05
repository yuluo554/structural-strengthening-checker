# HANDOFF-M3（M2 公式引擎 → M3 方案核查交接快照）

> 用法：新对话输入 `/goal 读取 "plan/HANDOFF-M3.md" 继续完成 M3 方案核查里程碑`（从仓库根运行；路径用相对路径，防本机路径进历史）。
> 上一里程碑：M2 公式引擎（✅ 2026-10-05，plan/00 状态表已回写；偏差与实现决策见 data/cases/workings/formula_verification_M2.md §四/§六）。

## 一、当前进度（M2 交付态）

- **公式本体与表值全部补核完成**：以 `data/_private/GB50367-2013_gqxh.pdf`（正式出版文本扫描件，中国灌区协会挂载，
  184 页，页面图像约 200DPI 可读）目视核对 7 组公式（式10.2.3-1~4 / 9.2.3-1~4 / 5.2.3-1~3 / 5.2.4-1~3 /
  5.2.5 / 9.2.9 / 10.2.8，另核对 15.2.2-2 组合式 `ld≥ψN·ψae·ls`——**M1 唯一公式熔断项解除**）与
  6 组表值（表10.2.8/9.2.9/15.2.3/15.2.4/4.3.4-1~3/4.3.5）；主记录 `data/cases/workings/formula_verification_M2.md`
  （逐项挂印刷页=PDF页−12 与互证方式；含 1 处 M1 记录修正：5.2.4 gist 应为"可近似取 h01=h0，εs1=εs0"）。
- 条款库 **51 条**（GB50367×33 新增 4.3.4/4.3.5 表值条款 + GB55021×16 + GB50728×1 + JGJ145×1 待核对）；
  12 条既有条目的 formula_ref/limits/gist 已按核对结果回写（公式形态进 limits.formula_* 键）。
- **4 个验算模块 compute 全部实装**（calc/common.py 共享层：已核对常数/表值/二次方程解析解/统一三态判定）：
  cfrp_beam_flexure（式10.2.3 组 + 式10.2.8 + 表10.2.8 内插 + ψf 封顶 + 式10.2.2/10.2.10 检查 + km 可选路径）、
  steel_plate_flexure（式9.2.3 组含受压钢板项 + 式9.2.9/表9.2.9）、section_enlarge_flexure（式5.2.3 线性解 +
  式5.2.4-1~3 二次受力 ξb + 式5.2.5 σs0 复核路径）、post_rebar_anchor（式15.2.3/15.2.5/15.2.2-2 终判 +
  表15.2.3/15.2.4 查表路径）。CalcResult 按 plan/04 §1.3 + `metrics` 增补（决策见 plan/06）。
- **算例库 14 例 bench 14/14 通过**（±0.5% 相对容差 + verdict 严格相等）：flexure_cases.json 9 例（真值来自
  手工计算书 `workings/flexure_workings.md`，先手算后实现）+ post_rebar_cases.json 5 例（3 例场景系数口径
  加终判扩展 + PR-004/005 查表算例）；三态覆盖：满足×8 / 需调整×6，"不满足"由单测+CLI 演示覆盖。
  pending/ 目录已删除。
- **参数扫描位级锁定**：tests/test_param_sweep.py，seed=20261005 × 12 落点/模块 × 4 模块，
  双跑 sha256 一致 + 金标准哈希锁定（三态分布 满足24/需调整21/不满足3，无异常落点）。
- `ssc calc` 实装（结论行 + CalcResult JSON）；`ssc bench` 真值比对实装；selfcheck 4 模块 READY、
  SELFCHECK_OK；**CLI 三态演示可复现**（tests/test_calc_three_states_demo 断言）。
- pytest **86 项全绿**（M1 72 → M2 86：新增 calc 模块测试 10 项 + 参数扫描 2 项 + 门控/CLI/bench 改造）。
- 工具入仓：`tools/extract_gqxh_page.py`（PDF 页面图像拼版，仅用于核对，产物不入仓）。

## 二、M3 待办（方案核查与检查单，DoD 见 plan/05 §五 M3）

1. **docx/PDF 文本提取完整版**（parsing/docx_text.py 骨架已有：docx 逐段 + pypdf 逐页；M3 补：中文路径/编码
   回归、空文档/损坏文件降级、依赖缺失 MissingExtraError 路径已有测试约定）；
2. **参数卡抽取（规则优先）**（parsing/param_card_builder.py 骨架=空参数卡兜底；M3 实装正则+槽位抽取：
   methods/materials/adhesive_indices/anchor_depth/unloading/crack_repair/appraisal_first，每项值必须带
   evidence，quote 非原文子串 → 丢弃该项并计入 needs_confirm 防幻觉 FR-B5）；
3. **规则引擎判定逻辑**（checking/engine.py 骨架已有类目门控过滤+兜底纪律；M3 实装三级判定：
   param_range 数值比对/keyword 存在性/required_section 缺失型，R-CONST-001 属缺失型——门控词用加固方法名
   （M1 实测：卸载关键词做门控会漏激活）；规则库 4 条已就绪）；
4. **GB 55021 检查单交互核对**（`ssc checklist` 骨架=条目一览；M3 实装逐项 manual/auto_text 核对流）；
5. **`ssc check` 端到端**：docx → 提取 → 参数卡 → check_plan → 三级结论输出（骨架期已能跑通降级路径）；
6. **M3 DoD**：门控关键词互斥测试绿；解析失败降级路径测试绿；人工用 1 份合成方案跑通端到端
   （用 `datagen/gen_plan` 现场生成，seed 固定可复现；样本 4 份在 data/synthetic/samples/）。

## 三、既定口径清单（动了会打挂基准/纪律，改前先对照）

- **条文纪律红线**：status≠已核对（或未登记）的条款不得进入计算路径；引擎级门控在 run_calc 内、先于参数校验
  （tests/test_engine_gating.py 锁死顺序；门控覆盖用临时待核对库逐模块断言）。
- **status=已核对 ⇔ source.checked_date 非空**；无出处的值不得以确定语气落库（ClauseStore 加载校验）。
- **代码表值↔条款库双出口一致**：calc/common.py 表值（挂条号）与 data/knowledge/clauses/*.json limits
  由 test_code_tables_match_clause_json 锁死——改任何一侧必须同步另一侧。
- **算例真值必有来源**（load_cases 强制）；容差 ±0.5%（相对）+ verdict 严格相等；真值键名=CalcResult.metrics 键
  （非数字元数据键 tolerance/note/verdict 除外）；基准按算例逐条对账，失配计 failed 并附 problems 明细。
- **参数扫描金标准哈希**：tests/test_param_sweep.py GOLDEN_SHA256——改公式/判定/warnings 文案都会变哈希，
  属有意修改时按模块 docstring 流程重算回填（actual 值在断言消息里）。
- **三态判定口径（M2 定稿）**：满足=达标且全部限值检查通过；需调整=可通过调整本方法参数达标（附调整方向与
  需求量）；不满足=本方法可行域内无法达标（x 超 ξb 限值）。改口径必须重跑 bench + 参数扫描金标准。
- **规范未注明处的实现决策**（formula_verification_M2.md §六，全部附 warning）：表10.2.8/9.2.9 档间线性内插；
  表15.2.3 c 档间保守取更小保护层列、d 档间按表注内插；表15.2.4 行选择=满足的最严条件行（B 级胶仅第一行）；
  ψ<0 退化为无加固解；x<2a′ 按"近似取 x=2a′"重算；Es/Esp 缺省 2.0e5/2.06e5 附 warning。
- **规则门控关键词跨类目互斥**（check_gate_mutex + 测试锁死），门控对全部 check_type 生效；R-CONST-001 门控词
  用加固方法名（缺失型检查）。
- **生成器确定性**：全部随机量出自 random.Random(seed)；docx zip 时间戳归一 (1980,1,1)；truth.json 不含时间戳；
  注入与 rule_id 一一对应（INJECTION_RULE_MAP），also_expect 恒空直到出现多规则注入。
- **核心层（core/calc）只 import stdlib**；PySide6/python-docx/pypdf 只能进 extras 且必须惰性导入
  （tests/test_lazy_deps.py + test_project_guards.py 守门）；dev extras 含 python-docx（CI 跑生成器测试）。
- **语法限 3.8**：带注解模块一律 `from __future__ import annotations`（守门测试）；CLI 输出禁 emoji（GBK 控制台）。
- **可选参数 schema 约定（M2 起）**：param_schema 条目可带 `"required": false`——缺省不报错、提供即校验；
  计算体内的"条件必填"（如 Asc>0 需 ap）在 compute 内抛 ValidationError。
- 退出码约定：0 成功 / 1 自检失败 / 2 输入或缺 extras / 3 条文门控拦截。
- 品牌隔离：文档不提姊妹项目业务领域；HANDOFF 用法行一律相对路径。
- 版权红线：规范全文永不入仓（_private/）；扫描件拼版图仅存 output/；入仓条目=要点转述+≤2句短摘录+出处+status。
- 基准语义一旦 M4 达标，本清单扩充为"指标门槛+接口签名"完整既定口径，改数据/加类目必重跑基准。

## 四、本机环境坑（只写实测）

- 本机唯一解释器 `py`=3.8.8；跑脚本一律 `py -X utf8`，全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip install）。
- pip 需绕代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...`。
- `ssc.exe` 装在 `...\Python38\Scripts`（不在 PATH）；用 `py -X utf8 -m structural_strengthening_checker ...` 代替。
- 系统 Python 已存量安装 python-docx/pypdf/Pillow（report/parse extras 探测已装；gui 未装）——extras 缺失降级
  路径靠测试内 monkeypatch 模拟，勿信本机探测。
- Git Bash 下 `/tmp` 与 Windows Python 不通；临时文件用仓库内 `output/`（已 gitignore）。
- 本机 curl 可用；知乎/baidu 文库/scribd/soujianzhu 全部 403 或登录墙，勿再试（渠道黑名单见 data/standards_raw/README.md）。
- **PDF 图像提取**：pypdf `page.images` 可直接抽取 gqxh 扫描件图块（JPEG+FlateDecode PNG），页面按内容流
  cm 矩阵拼版（tools/extract_gqxh_page.py）；XObject 键带 `/` 前缀需归一处理（已踩坑）；文字层为乱码勿用。
- runpy 以 `py -m structural_strengthening_checker.datagen.gen_plan` 直跑有 RuntimeWarning（包 __init__ 先 import），
  无实际影响；测试内用 `gen_plan.generate()` 调用。
- pytest 测试间共享 `DEMO_PARAMS`（tests/test_engine_gating.py）——改模块参数 schema 时同步该字典。

## 五、M2 DoD 复核（逐项）

- [x] 算例库全例通过（容差内）：bench 14/14（±0.5% 相对容差 + verdict 严格相等），selfcheck 显示 通过 14/未通过 0
- [x] 参数扫描位级锁定：48 落点双跑 sha256 一致 + 金标准哈希锁定（test_param_sweep_bit_level_lock）
- [x] 条款门控测试仍绿：test_engine_gating 全部门控顺序/待核对库断言通过（86 项全绿）
- [x] CLI 演示一次"满足/不满足/需调整"三态：test_calc_three_states_demo + 手工留档（output/demo_*.json）
- [x] 公式本体与表值补核（M2 第一件事）：7 组公式+6 组表值全部以出版文本核对并回写（formula_verification_M2.md）
- [x] 4 模块 compute 实装（含二次受力路径）：CFRP εf0 / 粘钢 εsp,0 / 增大截面 εs0·εs1 / 植筋 ψae 组合式终判
- [x] 台账回写：data/README、data/cases/README、standards_raw README（gqxh 渠道升级+待办勾销）、plan/00·05·06
- [x] git 提交入库
- 偏差说明：无新增偏差；M1 遗留偏差（算例顺延、JGJ145 熔断）中"算例顺延"已闭合，JGJ 145-2013 §6.3
  渠道仍不可达保持待核对（不阻塞 M3）。

## 六、关键命令速查

```bash
# 测试与自检（仓库根）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker selfcheck
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker modules
# 验算（三态演示：把 M/Afe 换成 output/demo_adjust.json、demo_fail.json 的值即得另两态）
printf '{"b":250.0,"h":500.0,"fc":14.3,"As":1520.0,"fy":360.0,"Afe":101.0,"Ecf":240000.0,"M0":0.0,"M":180.0,"ff":2300.0,"ef":0.01,"as":35.0,"xi_b":0.518,"Es":200000.0}' > output/demo_ok.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker calc cfrp_beam_flexure --input output/demo_ok.json
# 基准（14 例全通过）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker bench
# 合成方案生成（确定性，M3 端到端演示用）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker.datagen.gen_plan --out output/gen --seed 20261005 --count 5
# 方案核查（M3 实装点；当前降级路径可跑）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker check data/synthetic/samples/baseline_seed20261005.docx
# PDF 页面拼版（公式核对工具；产物不入仓）
py -X utf8 tools/extract_gqxh_page.py data/_private/GB50367-2013_gqxh.pdf 88,91,141 output/gqxh_pages
# 安装（新环境）
py -m pip install -U pip && NO_PROXY="*" no_proxy="*" py -m pip install -e .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple
```
