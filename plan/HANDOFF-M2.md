# HANDOFF-M2（M1 数据先行 → M2 公式引擎交接快照）

> ⚠️ **已过时仅作历史（M2 已于 2026-10-05 完成，交接快照见 plan/HANDOFF-M3.md）**。
> 保留本文供回溯 M1→M2 时的状态与口径推导。
> 用法（历史）：新对话输入 `/goal 读取 "plan/HANDOFF-M2.md" 继续完成 M2 公式引擎里程碑`。
> 上一里程碑：M1 数据先行（✅ 2026-10-05，plan/00 状态表已回写；偏差说明见 data/README.md）。

## 一、当前进度（M1 交付态）

- 条款库首批 **49 条**（`data/knowledge/clauses/` 四文件）：GB 50367-2013×31（10.2 纤维复合材 / 9.2 粘钢 / 5.2 增大截面 / 15.2 植筋 / 4.4 胶粘剂 / 3.1.7-3.1.8 / 5.1.5，全部 status=已核对，逐条挂建标库正文页+条文说明页 URL，checked_date=2026-10-05）；GB 55021-2021×16（正文强制条款 + 附录A 碳纤维指标 + 附录B 胶安全性能指标，cnass.cn+newswz.cn 双 PDF 副本互证）；GB 50728-2011×1（4.2.2）；JGJ 145-2013×1（**待核对**，渠道熔断留痕）。
- 规则库 **4 条**（adhesive/anchoring/appraisal/unloading，关键词跨类目互斥测试锁死），限值依据全部指向已核对条款；R-ADH-001 ref=GB55021-2021-B.0.2（粘钢胶 A≥15/B≥12 MPa、纤维胶 A≥14/B≥10 MPa，全文强制）。
- GB 55021 检查单 **11 项**（真实条号回填，含 1.0.3 先鉴定后加固 / 2.0.2-2.0.7 / 6.1.2/6.1.5/6.1.8/6.1.9 / 6.2.3）。
- 算例库：**3 例植筋真值算例**（PR-001 正向 / PR-002 反向"需调整" / PR-003 悬挑；来源=自编算例+手工计算书 `data/cases/workings/post_rebar_workings.md`，依据文本已核公式 式15.2.3/式15.2.5，αspt/fbd 为场景输入系数非表值断言）+ **9 例 pending 骨架**（`data/cases/pending/`，3 受弯模块×一次受力/二次受力/反向，不入基准）。
- 合成方案生成器 **v1 实装**（`src/.../datagen/gen_plan.py`）：固定 seed（默认 20261005）、4 类注入与规则 rule_id 联动、truth.json 含 doc_sha256/expected_verdict/also_expect、**zip 时间戳归一化保证双跑 sha256 逐字节一致**（已双跑对账）；样本 4 docx+truth.json 入仓 `data/synthetic/samples/`（sha256 登记 data/README）。
- 4 个验算模块 `required_clauses` 占位 ID 已替换为真实 clause_id（7/8/4/6 条），全部已核对 → `ssc modules` 4 模块 **READY**；`ssc calc` 到达 M2 stub（exit 2 未实装）；门控 exit 3 演示改由临时待核对数据目录复现（tests/test_cli.py）。
- M0 占位条目（clauses_skeleton/rules_skeleton）已删除；**4.5.5 章节归属已修正**（4.5 是钢丝绳；胶粘剂=4.4，限值经 4.4.3→GB 50728-2011 §4.2.2，现行强制取 GB 55021-2021 附录B）——详见 data/README 偏差记录。
- pytest **72 项全绿**；SELFCHECK_OK；CI 四矩阵不变（dev extras 已加 python-docx）。

## 二、M2 待办（公式引擎与 4 个验算模块，DoD 见 plan/05 §五 M2）

1. **公式本体补核（M2 第一件事）**：以正式出版文本（纸版或授权电子版）核对式(10.2.3-1~4)、式(9.2.3-1~4)、式(5.2.3-1/2)、式(5.2.4-1/2)、式(5.2.5)、式(9.2.9)、式(10.2.8) 的公式形态——当前全部为图片未核对（条文说明已确认结构：力矩平衡式力矩中心取受拉区边缘/轴力平衡式/ψf·ψsp 平截面推导式/x≥2a′ 保证受压钢筋屈服）；同步补核表值：表10.2.8（αf）、表9.2.9（αsp）、表15.2.3（αspt）、表15.2.4（fbd）、表4.3.4-1~3（ff）、表4.3.5（εf）；
2. 条款-公式-符号表实装（core/clauses 的 limits/symbols 已挂值；表值 null 的 M2 回填）；4 个验算模块 compute 实装（含二次受力路径：CFRP εf0 / 粘钢 εsp,0 / 增大截面 εs0·εs1 / 植筋 ψN·ψae 组合式补核后实装）；
3. 算例库回填：pending/ 9 例按核对后公式计算真值移入 `data/cases/`（或取得外部算例按台账规则替换）；植筋 3 例追加 ψae 组合式终判扩展与查表算例（αspt/fbd 表值核对后）；
4. 参数扫描回归：随机参数网格（固定 seed）→ 输出位级锁定（同输入必同输出），配 CR 守门测试（plan/06 EOL 策略决策）；
5. `ssc calc` 实装：输出 CalcResult（逐步骤挂公式编号与依据条款），"满足/不满足/需调整"三态可演示；
6. M2 DoD：算例库全例通过（容差 ±0.5%）；参数扫描位级锁定；条款门控测试仍绿；CLI 演示三态。

## 三、既定口径清单（动了会打挂基准/纪律，改前先对照）

- **条文纪律红线**：status≠已核对（或未登记）的条款不得进入计算路径；引擎级门控在 run_calc 内、先于参数校验（tests/test_engine_gating.py 锁死顺序；M1 后门控覆盖用临时待核对库逐模块断言，仓库数据门控放行到 M2 stub 另有断言）。
- **status=已核对 ⇔ source.checked_date 非空**；无出处的值不得以确定语气落库（ClauseStore 加载校验）；**表值未核对的一律 value:null+note 留痕，禁止记忆值预填**。
- **算例真值必有来源**（load_cases 强制）；植筋 3 例的真值口径=仅文本已核量（ls、ψN），αspt/fbd 是场景输入系数；容差 ±0.5% + verdict 严格相等；基准评测按"文档全部非 pass 集合"对账，多报 also_expect 之外的问题算误报。
- **规则门控关键词跨类目互斥**（check_gate_mutex + 测试锁死），门控对全部 check_type 生效；R-CONST-001 属"缺失型"检查，门控词用加固方法名（卸载关键词做门控会漏激活——M1 实测记录）。
- **生成器确定性**：全部随机量出自 random.Random(seed)；docx zip 时间戳归一 (1980,1,1)；truth.json 不含时间戳；注入与 rule_id 一一对应（INJECTION_RULE_MAP），also_expect 恒空直到出现多规则注入。
- **核心层（core/calc）只 import stdlib**；PySide6/python-docx/pypdf 只能进 extras 且必须惰性导入（tests/test_lazy_deps.py + test_project_guards.py 守门）；dev extras 已含 python-docx（CI 跑生成器测试）。
- **语法限 3.8**：带注解模块一律 `from __future__ import annotations`（守门测试）；CLI 输出禁 emoji（GBK 控制台）。
- 退出码约定：0 成功 / 1 自检失败 / 2 输入或缺 extras / 3 条文门控拦截。
- 品牌隔离：文档不提姊妹项目业务领域；HANDOFF 用法行一律相对路径。
- 版权红线：规范全文永不入仓（_private/）；入仓条目=要点转述+≤2句短摘录+出处+status。
- 基准语义一旦 M4 达标，本清单扩充为"指标门槛+接口签名"完整既定口径，改数据/加类目必重跑基准。

## 四、本机环境坑（只写实测）

- 本机唯一解释器 `py`=3.8.8；跑脚本一律 `py -X utf8`，全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip install）。
- pip 需绕代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...`。
- `ssc.exe` 装在 `...\Python38\Scripts`（不在 PATH）；用 `py -X utf8 -m structural_strengthening_checker ...` 代替。
- 系统 Python 已存量安装 python-docx/pypdf（report/parse extras 探测已装）；gui 未装——extras 缺失降级路径靠测试内 monkeypatch 模拟，勿信本机探测。
- Git Bash 下 `/tmp` 与 Windows Python 不通；临时文件用仓库内 `output/`（已 gitignore）。
- 本机 curl 可用；知乎/baidu 文库/scribd 全部 403 或登录墙，勿再试（渠道黑名单见 data/standards_raw/README.md）。
- runpy 以 `py -m structural_strengthening_checker.datagen.gen_plan` 直跑有 RuntimeWarning（包 __init__ 先 import），无实际影响；测试内用 `gen_plan.generate()` 调用。

## 五、M1 DoD 复核（逐项）

- [x] 条款库首批条目（4 模块所需条文 + GB 55021 检查单条目）全部挂出处与 status：49 条，100% 挂出处或熔断留痕（test_m1_data.py 断言）
- [x] 算例库逐条来源：3 例真值（计算书来源+互证）+ 9 例 pending 骨架；**偏差：12 例目标按 plan/05 §三 "(M2 定稿)" 顺延**，熔断记录 data/standards_raw/README.md
- [x] 合成方案生成器 v1（基线+4 类注入）+ 真值语义注释（gen_plan.py 模块注释）
- [x] data 台账登记齐（data/README 登记表+sha256+偏差记录；standards_raw 渠道记录含黑名单）
- [x] schema 守门测试全绿（pytest 72 项）
- [x] `ssc selfcheck` 显示 status 统计（49 条：48/1；规则 4；检查单 11；算例 3）
- [x] 生成器固定 seed 两次运行产物一致（sha256 逐字节对账通过）
- [x] 4 模块 required_clauses 替换为真实 clause_id 且全部已核对（test_repo_module_required_clauses_all_verified）
- [x] git 提交入库
- 偏差说明：见"二/三"与 data/README（算例顺延、4.5.5 修正、JGJ145 熔断、废止条文清单未核对）。

## 六、关键命令速查

```bash
# 测试与自检（仓库根）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker selfcheck
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker modules
# 验算（仓库条款已核对 → 到达 M2 stub，exit 2 未实装）
printf '{"b":250.0,"h":500.0,"fc":14.3,"As":1520.0,"fy":360.0,"Afe":101.0,"Ecf":240000.0,"M0":0.0,"M":180.0}' > output/smoke_input.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker calc cfrp_beam_flexure --input output/smoke_input.json
# 门控演示（exit 3，需临时待核对数据目录，见 tests/test_cli.py::test_calc_gate_demo_exit3）
# 合成方案生成（确定性，双跑 sha256 一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker.datagen.gen_plan --out output/gen --seed 20261005 --count 5
# 基准（3 例植筋算例，M2 前如实报 failed=3 未实装）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker bench
# 安装（新环境）
py -m pip install -U pip && NO_PROXY="*" no_proxy="*" py -m pip install -e .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple
```
