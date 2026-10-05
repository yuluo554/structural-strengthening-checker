# HANDOFF-M5（M4 内置基准 → M5 桌面交付交接快照）

> 用法：新对话输入 `/goal 读取 "plan/HANDOFF-M5.md" 继续完成 M5 桌面交付里程碑`（从仓库根运行；路径用相对路径，防本机路径进历史）。
> 上一里程碑：M4 内置基准达标（✅ 2026-10-06，plan/00 状态表已回写；基准口径决策见 plan/06 M4 各行）。

## 一、当前进度（M4 交付态）

- **check 基准实装**（`bench/check_bench.py`）：现场 `gen_plan.generate`（seed=20261005 固定，
  不背产物；临时目录用后清理）→ 逐份 sha256 对 truth 校验（防生成器漂移）→ 与 ssc check 同
  流水线逐份核查 → 对账口径=文档全部非 pass 集合 vs 期望集合（expected_non_pass ∪ also_expect）。
  指标：检出率（规则实例）/误报数/判定准确率（主期望 verdict 与该 rule_id 最重 verdict 严格相等）。
  当前实测：检出 7/7、误报 0（含基线）、判定准确率 7/7。
- **门槛双向锁死**：REQUIRED_DETECTION_RATE=1.0 / MAX_FALSE_POSITIVES=0 /
  REQUIRED_VERDICT_ACCURACY=1.0 常量在 check_bench 模块定义，tests/test_bench
  （test_check_bench_thresholds_are_dod_values + thresholds 断言）锁死；`ssc bench` 门槛不达
  exit 1（BENCH_FAIL）；CI 四矩阵加 bench 步骤常驻。README 指标表已回填。
- **docx 报告导出实装**（`report/docx_export.py`，M4 补齐 plan/03 排期 M4/M5 的 M4 部分）：
  验算书 FR-D1（输入参数表/逐步计算过程/依据条款/结论/签署栏/免责声明）+ 核查报告 FR-D2
  （概要/明细含证据链/整改建议汇总/签署栏/免责声明）；签署栏=验算书 计算/校核/审核、
  核查报告 核查/复核/批准（决策见 plan/06，待拍板 #3 已结算）；0 外链由 tests/test_report
  全包件关系 is_external=False 断言守门（FR-D4）。出口：`ssc report calc/check` 子命令 +
  `ssc check --report DIR` 双写 check_report.json+check_report.docx（缺 report extras →
  JSON 照写+提示，不破"核查完成即 exit 0"口径）。
- **共用核查流水线**：`cli._run_check_pipeline(plan_path, data_dir)` 是 ssc check 与
  ssc report check 的唯一核查路径（提取→参数卡→三级判定；ParseError 降级、OSError/
  ValueError/MissingExtraError 上抛由调用方映射退出码）。
- `checking/engine.worst_verdict(verdicts)` 升为公共接口（原 _worst）；VERDICT_LABELS
  移至 checking.engine 单一出口（CLI 与 docx 报告共用）。
- pytest **129 项全绿**（M3 118 → +基准 4 +报告 7）；selfcheck SELFCHECK_OK（52 条/4 规则
  互斥 OK/11 检查单/bench 14/14）；`ssc bench` BENCH_OK。
- 遗留不变：JGJ 145-2013 §6.3 渠道不可达保持待核对（不阻塞）；裂缝修补规则 P1/P2 扩展未入库。

## 二、M5 待办（桌面交付，DoD 见 plan/05 §五 M5）

1. **PySide6 前置 spike**：本机 3.8.8 可用版本上限实测（约 6.6/6.7），锁定版本写 plan/06；
   待拍板 #1 拍板；
2. **四页签界面实装**（gui/app.py，M0 骨架已在）：验算表单（模块选择+参数表单按 param_schema
   生成+三态结论展示）/方案核查（文件选择+三级判定明细+证据链）/检查单（--interactive 的 GUI
   形态）/报告（export_calc_book/export_check_report 直接入库函数，CLI 与 GUI 共用）；全部消费
   既有 API，不另起第二套行为；
3. **PyInstaller 打包 exe**：onedir 为默认（plan/03），onefile 待拍板 #2 拍板；数据文件内嵌
   策略在 M5 决策（plan/06 遗留项：find_data_dir 打包形态的查找路径）；打包产物不得携带
   data/_private/；
4. **M5 DoD**：断网环境全功能演示通过；exe 在无 Python 机器可跑（干净验证）；docx 导出测试绿
   （含 0 外链断言，M4 已常驻 tests/test_report）；
5. 回写 plan/00·05·06 + README + HANDOFF-M6；打包/exe 决策入 06。

## 三、既定口径清单（M4 定稿版：指标门槛 + 接口签名，动了会打挂基准/纪律，改前先对照）

### 3.1 基准指标门槛（M4 DoD 常量，放宽=改 DoD，默认不允许）

- 验算基准：通过率 100%（14/14，±0.5% 相对容差 + verdict 严格相等）；
- check 基准：检出率 1.0 / 误报 0 / 判定准确率 1.0——常量在 `bench/check_bench.py`
  （REQUIRED_DETECTION_RATE / MAX_FALSE_POSITIVES / REQUIRED_VERDICT_ACCURACY），
  tests/test_bench 双向锁死；README 指标表与之一致；
- `ssc bench` 一条命令复现双基准，门槛不达 exit 1；CI 四矩阵 bench 步骤常驻；
- 对账口径（plan/05 §四真值语义）：期望集合=expected_non_pass ∪ also_expect；
  报告集合=CheckReport.non_pass_rule_ids()（含 EVIDENCE 级）；多报=误报；
  判定准确率按 worst_verdict(该 rule_id 全部 verdict) 与 injected[].expected_verdict 严格相等；
- **check 基准现场生成**：run_check_bench 默认 seed=20261005、count=5（+1 基线=6 docs），
  现场生成不背产物；生成后逐份 sha256 对 truth 校验，漂移计 issue 拒判。

### 3.2 接口签名（M4 定稿，改动需同步全部消费方与测试）

- `checking.engine.check_plan(card, rules, store, parse_failed=False) -> CheckReport`；
  `CheckReport.non_pass_rule_ids()`（保序去重非 pass 集合）、`summary()`、`degraded` 标记；
- `checking.engine.worst_verdict(verdicts: List[str]) -> str`（公共最重判定，原 _worst；
  fail > suspicious > needs_confirm > pass，空列表兜底 needs_confirm）；`VERDICT_LABELS`
  公共常量（中文标签单一出口，CLI/docx 共用）；
- `bench.check_bench.run_check_bench(data_dir, work_dir=None, seed=..., count=5,
  store=None, rules=None) -> dict`（work_dir 显式给出则产物保留；`thresholds_met(result)`
  是 selfcheck/CLI/测试共用的门槛判定出口）；`reconcile_doc(truth_doc, report)` 单文档对账；
- `report.docx_export.export_calc_book(result, out_path) -> Path`（FR-D1）；
  `export_check_report(report, out_path, card=None) -> Path`（FR-D2；card 可选签名扩展，
  见 plan/06 M4 决策）；`DISCLAIMER` 常量；缺 extras 抛 MissingExtraError；
- `cli._run_check_pipeline(plan_path, data_dir)`：ssc check 与 ssc report check 唯一共用
  核查路径——改降级行为只改这里，防两套行为漂移；
- `gen_plan.generate(out_dir, seed, count)` 与 `run_calc(module_id, params, store)` 形状不变
  （M1/M2 定稿）。

### 3.3 全部历史纪律（继续有效）

- **条文纪律红线**：status≠已核对（或未登记）的条款不得进入计算路径（run_calc 门控先于参数
  校验）；核查层同构——规则 status≠已核对 → needs_confirm，数值判定前 store.require_verified
  （ANCHOR_SUPPORT_CLAUSES）。
- **status=已核对 ⇔ source.checked_date 非空**；无出处的值不得以确定语气落库。
- **代码表值↔条款库双出口一致**：test_code_tables_match_clause_json（calc/common）+
  test_check_layer_limits_match_clause_json（checking/engine 锚固常量与 fy 映射）双向锁死。
- **算例真值必有来源**；容差 ±0.5%（相对）+ verdict 严格相等；真值键名=CalcResult.metrics 键。
- **参数扫描金标准哈希**：tests/test_param_sweep.py GOLDEN_SHA256——改公式/判定/warnings 文案
  都会变哈希，有意修改按模块 docstring 流程重算回填。
- **三态判定口径（M2 定稿）**：满足/需调整/不满足（plan/04 §1.3）。
- **方案核查三级判定口径（M3 定稿）**：fail=文档自身可证不足；suspicious=介于多档适用限值间
  "不能排除"；needs_confirm=证据不足/无法建立限值/规则依据未核对/解析降级；pass=该规则筛查
  未发现问题。R-ANCH-001 需求下限口径与 R-ADH-001 区间口径改动会打挂 check 基准。
- **解析降级纪律（plan/03 §三）**：ParseError/零段落 → 全部规则 needs_confirm，不产生任何 fail。
- **规则门控关键词跨类目互斥**；R-CONST-001 门控词=加固方法名。
- **生成器确定性**：random.Random(seed)；docx zip 时间戳归一 (1980,1,1)；truth.json 无时间戳；
  注入与 rule_id 一一对应（INJECTION_RULE_MAP）。**改生成器文案=改语料=改 sha256 台账+
  端到端测试+check 基准，三处同步。**
- **appraisal_first 证据词表**：程序性鉴定证据词，刻意排除裸词"鉴定/检测"——改词表须重跑端到端。
- **核心层只 import stdlib**；PySide6/python-docx/pypdf 只能进 extras 且必须惰性导入
  （test_lazy_deps + test_project_guards 守门）。
- **语法限 3.8**：`from __future__ import annotations`；CLI 输出禁 emoji（GBK）。
- **可选参数 schema 约定**：param_schema 可带 `"required": false`；条件必填在 compute 内抛
  ValidationError。
- **退出码约定**：0 成功（check/checklist/report 导出完成即 0，结论看报告）/ 1 自检失败或一般
  错误 / 2 输入或缺 extras / 3 条文门控拦截；`ssc bench` 门槛不达 exit 1（M4 增补）。
- **报告纪律（FR-D3/D4）**：免责声明强制（report/docx_export.DISCLAIMER）；产物 0 外链
  （tests/test_report 全包件关系断言）；签署栏占位空栏不虚构签署人。
- **品牌隔离**：文档不提姊妹项目业务领域；HANDOFF 用法行一律相对路径。
- **版权红线**：规范全文永不入仓（_private/）；入仓条目=要点转述+≤2句短摘录+出处+status。

## 四、本机环境坑（只写实测，M3 版 + M4 增补）

- 本机唯一解释器 `py`=3.8.8；跑脚本一律 `py -X utf8`，全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip）。
- pip 需绕代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...`。
- `ssc.exe` 装在 `...\Python38\Scripts`（不在 PATH）；用 `py -X utf8 -m structural_strengthening_checker ...` 代替。
- Git Bash 下 `/tmp` 与 Windows Python 不通；临时文件用仓库内 `output/`（已 gitignore）。
- pytest 输出摘要行可能被 warnings 块淹没——看退出码（`echo $?`）或 `--tb=no -p no:warnings`。
- runpy 直跑 `py -m ...datagen.gen_plan` 有 RuntimeWarning，无实际影响；测试内用 `gen_plan.generate()`。
- pytest 测试间共享 `DEMO_PARAMS`（tests/test_engine_gating.py）——改模块参数 schema 时同步该字典。
- 系统 Python 已存量安装 python-docx/pypdf/Pillow——extras 缺失降级路径靠测试内 monkeypatch
  （`monkeypatch.setitem(sys.modules, "docx", None)`），勿信本机探测。
- **M4 增补**：python-docx 的 `document.paragraphs` 不含表格单元格文字——断言签署栏/表格内容
  必须遍历 `document.tables`（tests/test_report._doc_text 已示范）。
- **M4 增补**：函数内条件性 `from xxx import Name` 会让 Name 变成整个函数的局部名，先到的
  except 分支引用即 UnboundLocalError——共用异常类型提到函数首行导入。
- 知乎/baidu 文库/scribd/soujianzhu/morgain 全部 403 或登录墙，勿再试；渠道黑名单见
  data/standards_raw/README.md；规范全文检索走 Z.ai WebSearch 可命中机构挂载全文。

## 五、M4 DoD 复核（逐项）

- [x] 验算算例通过率 100%（bench 14/14 常驻）
- [x] 方案核查检出率达标：7/7 规则实例检出（检出率 1.0）
- [x] 误报 0：基线 0 误报 + 注入文档无非期望非 pass 结论（含 EVIDENCE 级对账）
- [x] 判定准确率 1.0：主期望 verdict 与最重 verdict 逐一严格相等
- [x] 基准一条命令复现：`ssc bench`（双基准 + 门槛判定 + BENCH_OK/BENCH_FAIL 出口）
- [x] 基准进 CI：四矩阵 bench 步骤常驻（门槛不达红）
- [x] 指标门槛进测试断言：tests/test_bench（常量锁死+达标断言+语料退化拒判）+ test_cli 出口
- [x] 指标表进 README：内置基准指标表回填（数值+门槛+复现命令）
- [x] docx 报告导出补齐（FR-D1/D2 + 免责声明 + 签署栏 + 0 外链断言）
- [x] 既定口径固化："指标门槛+接口签名"完整清单回写 HANDOFF-M5 §三
- [x] 台账/plan 回写：plan/00·05·06、README
- [x] git 提交入库
- 偏差说明：无新增偏差。遗留不变：JGJ 145-2013 §6.3 待核对；裂缝修补规则 P1/P2 扩展未入库
  （抽取槽位就绪、基准不受影响）；plan/03 命令面 `ssc report` 的 GUI 侧消费留 M5。

## 六、关键命令速查

```bash
# 测试与自检（仓库根）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest --tb=no -p no:warnings -q
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker selfcheck
# 内置基准（双基准一条命令：验算真值比对 + 方案核查对账）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker bench
# 方案核查（端到端三出口；--report 双写 JSON+docx）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker check data/synthetic/samples/case01_seed20261005.docx
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker check data/synthetic/samples/baseline_seed20261005.docx --report output/m4_report
# 报告导出（docx，FR-D1/D2；calc 需先把算例 input 字段存成参数卡 JSON）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker report check data/synthetic/samples/case01_seed20261005.docx --out output/check_report.docx
# 检查单三种用法
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker checklist --doc data/synthetic/samples/baseline_seed20261005.docx --out output/ckl.json
# 合成方案生成（基准内部自动现场生成；手工生成用）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker.datagen.gen_plan --out output/gen --seed 20261005 --count 5
# 安装（新环境）
py -m pip install -U pip && NO_PROXY="*" no_proxy="*" py -m pip install -e .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple
```
