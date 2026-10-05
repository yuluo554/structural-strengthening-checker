# HANDOFF-M1（M0 骨架 → M1 数据先行交接快照）

> ⚠️ **已过时，仅作历史**：M1 已于 2026-10-05 完成，现行交接快照见 [HANDOFF-M2.md](HANDOFF-M2.md)。
> 用法：新对话输入 `/goal 读取 "plan/HANDOFF-M1.md" 继续完成 M1 数据先行里程碑`（从仓库根运行；路径用相对路径，防本机路径进历史）。
> 上一里程碑：M0 项目启动与骨架（✅ 2026-10-05，plan/00 状态表已回写）。

## 一、当前进度（M0 交付态）

- plan/00-06 齐全：01 题目定稿；02 需求解读（FR-A~F 清单+边界固化）；03 架构（零依赖核心+extras 分层）；04 模块详设（6 类 schema+接口）；05 数据计划与里程碑（M0-M6 DoD+条文核对流程）；06 决策记录（13 条已定+6 条待拍板）。
- 可运行骨架已提交：src 布局包 `structural_strengthening_checker`（core/calc/parsing/checking/report/bench/datagen/gui 七个子包），CLI（`ssc`，selfcheck/modules/calc 门控演示/bench/checklist 真实可用；check/report/gui 受控降级），52 项 pytest 全绿，CI 四矩阵（ubuntu/windows × 3.8/3.12），README/LICENSE/.gitattributes(.gitattributes eol=lf)/pyproject(extras: gui/report/parse/dev/package)。
- 条文门控（FR-A7）引擎级强制并可演示：4 个验算模块均为占位条款 ID（如 `GB50367-2013-CFRP-FLEXURE`），`ssc calc` → exit 3 拒绝进入计算路径。**仓库当前不含任何已核对条文，无任何计算输出——这是纪律不是缺陷。**
- 数据骨架：knowledge 条款库 1 条占位（GB50367-2013-4.5.5）、规则 2 条占位、检查单 2 项占位（全部 status=待核对）；cases/ 空库；standards_raw/ 渠道记录表 4 规范；台账 data/README.md 已登记。

## 二、M1 待办（数据先行，DoD 见 plan/05 §五 M1）

1. 条文核对流程执行（plan/05 §二五步流程）：获取 4 本规范相关条文原文 → 全文存 `data/_private/`（不入仓）→ 按 plan/04 §1.1 schema 入库首批条目：4 个验算模块所需条文（公式/限值/符号表）+ GB 55021 检查单首批条目，逐条挂出处（渠道+定位+checked_date）；
2. 入库后将验算模块 `required_clauses` 的占位 ID 替换为真实 clause_id（src/calc/*.py 四处）；
3. 算例库 ≥12 例（每模块 ≥3 例：一次受力/二次受力/反向例）入 `data/cases/`，逐条来源（书名/页码/例题号），双渠道互证；
4. 合成方案生成器 v1（src/datagen/gen_plan.py：python-docx + 固定 seed + 4 类注入 + truth.json 含 also_expect 语义）；
5. data/README 台账同步登记（来源+sha256+日期）。

## 三、既定口径清单（动了会打挂基准/纪律，改前先对照）

- **条文纪律红线**：status≠已核对（或未登记）的条款不得进入计算路径；引擎级门控在 run_calc 内、先于参数校验（tests/test_engine_gating.py 锁死顺序）。
- **status=已核对 ⇔ source.checked_date 非空**；无出处的值不得以确定语气落库（ClauseStore 加载校验）。
- **算例真值必有来源**（load_cases 强制），容差 ±0.5% + verdict 严格相等；基准评测按"文档全部非 pass 集合"对账，多报 also_expect 之外的问题算误报。
- **规则门控关键词跨类目互斥**（check_gate_mutex + 测试锁死），门控对全部 check_type 生效。
- **核心层（core/calc）只 import stdlib**；PySide6/python-docx/pypdf 只能进 extras 且必须惰性导入（tests/test_lazy_deps.py + test_project_guards.py 守门）。
- **语法限 3.8**：带注解模块一律 `from __future__ import annotations`（守门测试）；CLI 输出禁 emoji（GBK 控制台）。
- 退出码约定：0 成功 / 1 自检失败 / 2 输入或缺 extras / 3 条文门控拦截。
- 品牌隔离：文档不提姊妹项目业务领域；HANDOFF 用法行一律相对路径。
- 基准语义一旦 M4 达标，本清单扩充为"指标门槛+接口签名"完整既定口径，改数据/加类目必重跑基准。

## 四、本机环境坑（只写实测）

- 本机唯一解释器 `py`=3.8.8；跑脚本一律 `py -X utf8`，全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip install）。
- pip 需绕代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...`（实测可编辑安装成功）。
- `ssc.exe` 装在 `...\Python38\Scripts`（不在 PATH）；用 `py -X utf8 -m structural_strengthening_checker ...` 代替。
- 系统 Python 已存量安装 pypdf/python-docx（extras 探测显示 report/parse 已装）——**extras 缺失降级路径靠测试内 monkeypatch 模拟，勿信本机探测**。
- Git Bash 下 `/tmp` 与 Windows Python 不通；临时文件用仓库内 `output/`（已 gitignore）。

## 五、M0 DoD 复核（逐项）

- [x] plan/00-06 齐全且交叉一致
- [x] `py -X utf8 -m structural_strengthening_checker selfcheck` → SELFCHECK_OK（exit 0）
- [x] pytest 全绿（52 项，含门控顺序/互斥/降级/守门测试）
- [x] 未核对条款无法进入计算路径（`ssc calc` exit 3 可复现）
- [x] 干净要素：.gitattributes(eol=lf)、.gitignore（.env/_private/output/dist）、LICENSE(MIT)、CI 四矩阵
- [x] git 提交入库
- 偏差说明：无。

## 六、关键命令速查

```bash
# 测试与自检（仓库根）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker selfcheck
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker modules
# 条文门控演示（预期 exit 3）
printf '{"b":250.0,"h":500.0,"fc":14.3,"As":1520.0,"fy":360.0,"Afe":101.0,"Ecf":240000.0,"M0":0.0,"M":180.0}' > output/smoke_input.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker calc cfrp_beam_flexure --input output/smoke_input.json
# 安装（新环境）
py -m pip install -U pip && NO_PROXY="*" no_proxy="*" py -m pip install -e .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple
```
