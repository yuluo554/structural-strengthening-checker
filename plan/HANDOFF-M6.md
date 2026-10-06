# HANDOFF-M6（M5 桌面交付 → M6 脱敏发布交接快照）

> ⚠️ 已过时仅作历史（M6 已完成、项目已完结，收官快照见 plan/HANDOFF-M7.md；本文件仍为口径/实录的有效引用源）。

> 用法：新对话输入 `/goal 读取 "plan/HANDOFF-M6.md" 继续完成 M6 脱敏发布里程碑`（从仓库根运行；路径用相对路径，防本机路径进历史）。
> 上一里程碑：M5 桌面交付（✅ 2026-10-06，plan/00 状态表已回写；GUI/打包决策见 plan/06 M5 各行）。

## 一、当前进度（M5 交付态）

- **四页签 GUI 实装**（`gui/app.py` 惰性入口 + `gui/mainwindow.py`）：
  - 验算表单：模块下拉 + param_schema 动态表单（含义/单位/范围提示，可选字段标注）→ run_calc
    三态结论（颜色区分）+ 特征量/逐步计算/依据条款/提示展示；参数卡 JSON 与 `ssc calc --input`
    同格式互载/保存；验算书 docx 导出；
  - 方案核查：文件选择 → `cli._run_check_pipeline`（唯一共用核查路径）→ 判定明细树
    （判定/规则/名称/结论/依据，VERDICT_LABELS 单一出口着色）+ 证据链详情（原文/段落/数值/假设）；
    解析失败红色降级横幅；报告导出与 `ssc check --report` 同形状（_check_report_json + docx，
    缺 report extras 时 JSON 照写+提示）；
  - 检查单：ChecklistStore 逐项判定（下拉+备注），--doc 等价的自动建议（cli._auto_text_suggestion，
    绝不自动给"不符合"），渲染用 cli._render_filled（与 ssc checklist --fill 同一函数），
    结果 JSON {item_id:{choice,note}} 与 CLI 互通；数据问题（store.issues）停用并展示（exit 1 同口径）；
  - 报告：验算书 FR-D1 / 核查报告 FR-D2 直接调 export_calc_book/export_check_report，
    与 ssc report calc/check 同出口。
  - 纪律：GUI 不新增任何解析/判定行为（plan/06 M5 消费面纪律行）；错误映射退出码语义
    （2 输入/缺依赖、3 条文门控），SSCError 消息框/内联红字，windowed exe 兜底 ctypes MessageBox。
- **PySide6 版本锁定（待拍板 #1 结算）**：3.8.8 上限实测 **6.6.3.1**（pip 自动解析；6.7+ 需 ≥3.9），
  pyproject gui extra 保持 `PySide6>=6.2` 不锁小版本；exe 构建通道用 6.11.2（3.14.5）。
- **find_data_dir 冻结分支（打包数据策略）**：显式 > SSC_DATA_DIR > 内嵌（sys._MEIPASS/data →
  exe目录/data → exe目录/_internal/data）> CWD 上溯；测试 test_packaging 锁死优先级与源码模式不回归。
- **PyInstaller onedir 双 exe**：`SSC.exe`（GUI，console=False）+ `ssc-cli.exe`（console，与 ssc 同一
  cli.main，无 Python 机器脚本化验证用）；tools/ssc.spec（SPECPATH 相对路径坑：脚本路径必须用
  ROOT 绝对路径）+ tools/build_exe.py（构建封装 + 红线断言）。产物约 198MB。
  红线断言：dist 全树无 `_private/standards_raw/synthetic/workings` 成分；内嵌 knowledge 三库 +
  cases JSON 与仓库逐份对账一致。`.gitignore` 加 `!tools/ssc.spec` 例外。
- **构建通道实录（plan/06 决策行）**：3.8.8 通道 7 连崩（unknown opcode/opname AttributeError/
  0xC0000005/"Instruction" not iterable——全部"原则上不可能"错误，清 pyc+冷却不解，判读为该老
  解释器环境级不稳定）；**3.14.5 通道**（`%LOCALAPPDATA%\Python\bin\python.exe`）
  首跑定位真根因：PyInstaller 6.22.3 对 3.14 webbrowser 字节码解析 bug（"Failed to scan the module
  'webbrowser'"）→ spec excludes 加 webbrowser 后一次成功。构建命令：
  `PYTHONDONTWRITEBYTECODE=1 "%LOCALAPPDATA%\Python\bin\python.exe" -X utf8 tools/build_exe.py`。
- **干净验证证据（M5 DoD）**：仓库外中立目录 + 剥离 PATH（env -i 仅 System32）+ 无 SSC_DATA_DIR：
  ssc-cli selfcheck（SELFCHECK_OK）/ bench（BENCH_OK）/ check / checklist / report 五通路全过；
  SSC.exe offscreen 启动存活探针通过。源码守门：test_no_network_imports（全离线断网证据）。
- pytest **156 项全绿**（M4 129 → +GUI 17（offscreen，PySide6 缺席时 importorskip 跳过）+
  打包纪律 10）；SELFCHECK_OK；`ssc bench` BENCH_OK。
- CI：windows/3.8 矩阵 extras 改为 `dev,gui`（GUI 测试常驻一个矩阵），其余矩阵 `dev`。
- 遗留不变：JGJ 145-2013 §6.3 渠道不可达待核对（不阻塞）；裂缝修补规则 P1/P2 扩展未入库。

## 二、M6 待办（脱敏发布，DoD 见 plan/05 §五 M6）

1. **干净环境验证**：新 clone + 新 venv 按 README 逐字跑通；pytest 收集数对账
   （`pytest --collect-only -q` 计数 vs dev 环境，防"双绿但悄悄少跑"——电力两票 M6 实录形态）；
   注意 conftest 在未安装包时回退 src 路径（骨架期便利），验证时以"按 README 安装后"为准；
2. **脱敏四步**：邮箱/姓名/绝对路径/姊妹项目业务词扫描（tools 扫描脚本或手工清单）；
   `test_no_personal_paths_in_source` 已守 src，注意 tools/ 与 plan/ 不在其扫描面（手工核对）；
   dist 产物本体也要扫（exe 内嵌路径、docx 元数据）；
3. **Release 材料**：GitHub 公开仓库（待拍板 #4：description/topics 届时给用户确认）；
   Release 附 dist/SSC（onedir 打 zip）；技术报告载体（待拍板 #5：Markdown 入仓+可选 docx）；
4. **CI 首跑四矩阵全绿**（含 bench 门 + windows/3.8 的 gui extras 矩阵）；
5. **收尾固化**：tag（如 v0.1.0-M6）/topics/README"快速开始"转正（去掉"当前骨架"字样）/
   缓议项清零（plan/06 待拍板 #6 对外动作分级授权——**发布动作逐项用户确认留档**）；
6. 回写 plan/00·05·06 + README + HANDOFF-M7 或项目完结记录。

## 三、既定口径清单（M5 增补版：M4 口径全部继续有效，以下为 M5 新增）

### 3.1 M5 新增口径（动了会打挂测试/守门）

- **GUI 消费面纪律**：四页签只消费既有 API（run_calc / cli._run_check_pipeline /
  _check_report_json / _auto_text_suggestion / _render_filled / export_calc_book /
  export_check_report / VERDICT_LABELS / DISCLAIMER）；改这些接口签名必须同步 gui/mainwindow.py
  与 tests/test_gui.py；
- **find_data_dir 优先级**：显式 > SSC_DATA_DIR > 内嵌（冻结三分支）> CWD 上溯；
  test_packaging 五个分支测试锁死；非冻结模式行为不得变；
- **spec datas 白名单**：仅 `data/knowledge/**` + `data/cases/*.json`；加新数据目录时同步
  test_spec_datas_only_knowledge_and_cases 与 build_exe.py 红线断言；
- **spec excludes**：`tkinter/test/unittest/pydoc_data/lib2to3/webbrowser`——webbrowser 是 3.14
  构建通道的 PyInstaller 解析 bug 绕过项，删掉会打挂构建；
- **双 exe 结构**：SSC.exe（GUI/console=False）+ ssc-cli.exe（console=True）；test_spec_builds_both_exes
  锁死；入口脚本 tools/exe_entry_gui.py（含 ctypes 兜底错误框）/exe_entry_cli.py；
- **CI extras 矩阵**：windows/3.8 = `dev,gui`（GUI 测试常驻唯一矩阵），其余 = `dev`；
  test_gui 全模块 importorskip，PySide6 缺席=整模块 1 个 skip（收集数对账时注意这不是静默少跑——
  是显式声明的跳过，-rs 可见）；
- **test_gui 环境前提**：QT_QPA_PLATFORM=offscreen 必须在首次导入 PySide6 前设置（模块顶部）；
  消息框/文件对话框全部 monkeypatch（屏蔽模态）。

### 3.2 M4 及更早口径（摘要，全文见 HANDOFF-M5 §三）

- 基准门槛 1.0/0/1.0 双向锁死；接口签名（check_plan/worst_verdict/run_check_bench/export_*）；
- 条文纪律红线（status 门控先于一切数值判定）；代码表值↔条款库双出口；
- 生成器确定性（seed + zip 归一）；三态/三级判定口径；解析降级纪律（ParseError→全 needs_confirm）；
- 核心层只 import stdlib；PySide6/python-docx/pypdf 只进 extras 惰性导入；
- 3.8 语法限（`from __future__ import annotations`；CLI 禁 emoji）；报告纪律（免责声明+0 外链+空签署栏）。

## 四、本机环境坑（M5 增补）

- **PyInstaller 构建：一律走 3.14.5 通道**（`%LOCALAPPDATA%\Python\bin\python.exe`），
  3.8.8 通道 7 连崩实录见 plan/06——不要在 3.8 上重试构建，直接用 3.14；
- **3.14 通道也有坑**：PyInstaller 6.22.3 对 webbrowser 字节码解析 bug（已 excludes 绕过）；
  PySide6 装的是 6.11.2（与 3.8 通道的 6.6.3.1 并存，各归各的 site-packages，互不干扰）；
- **spec 脚本路径**：PyInstaller 把相对路径解析到 SPECPATH（tools/）而非 CWD——Analysis 的脚本
  必须用 `str(ROOT / "tools" / ...)` 绝对路径（实录：tools/tools/ 不存在）；
- **PyInstaller 没有 --workers 参数**（与 Nuitka 记混）；`*.spec` 被 .gitignore 通配吞掉——
  例外规则 `!tools/ssc.spec` 已加，新增 spec 同理；
- **验证 exe 别在仓库树内跑**：CWD 上溯会命中仓库 data/knowledge，证不了内嵌数据——用
  `%LOCALAPPDATA%\Temp` 类中立目录 + `env -i` 剥离 PATH；
- **Git Bash 管道吃退出码**（`cmd | tail` 后 `$?` 是 tail 的）：判定成败的命令重定向日志文件后
  裸跑 echo $?;
- **QAction 在 QtGui 不在 QtWidgets**（Qt6）；PySide6 6.11.2/6.6.3.1 双通道行为一致；
- 历史坑全集见 HANDOFF-M5 §四（py -X utf8 / NO_PROXY 清华镜像 / output/ 临时目录 /
  pytest 摘要被 warnings 淹没 / document.paragraphs 不含表格文字 / 函数内条件 import 的
  UnboundLocalError 等，全部继续有效）。

## 五、M5 DoD 复核（逐项）

- [x] PySide6 前置 spike：3.8.8 上限 6.6.3.1 实测锁定，plan/06 落表（待拍板 #1 结算）
- [x] 四页签界面实装（全部消费既有 API；GUI 测试 17 项 offscreen 常驻）
- [x] find_data_dir 打包形态查找路径（冻结三分支 + 测试锁死）
- [x] PyInstaller 打包 exe：onedir 双 exe（待拍板 #2 结算 onedir）；数据内嵌策略定稿并断言
- [x] 打包产物不携带 data/_private/（build_exe.py 红线断言 + test_packaging 双守门）
- [x] exe 无 Python 机器可跑（干净验证：中立目录 + 剥离 PATH 五通路 + GUI 存活探针）
- [x] 断网环境全功能演示（全离线静态守门 + 干净环境全通路；物理断网复核留验收）
- [x] docx 导出测试绿（156 项全绿，0 外链断言常驻）
- [x] 回写 plan/00·05·06 + README + HANDOFF-M6；打包/exe 决策入 06
- [x] git 提交入库
- 偏差说明：无新增遗留。3.8.8 构建通道不稳定与 3.14 webbrowser 绕过均已实录 plan/06；
  物理断网演示与真·异机验证建议 M6 发布验收时复核（当前为等效证据背书）。

## 六、关键命令速查

```bash
# 测试与自检（仓库根，3.8 通道）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest --tb=no -p no:warnings -q
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker selfcheck
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker bench
# 桌面界面（3.8 通道，PySide6 6.6.3.1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m structural_strengthening_checker gui
# exe 构建（必须 3.14 通道；构建+红线断言一体）
PYTHONDONTWRITEBYTECODE=1 "%LOCALAPPDATA%\Python\bin\python.exe" -X utf8 tools/build_exe.py
# 仅重跑既有产物断言
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/build_exe.py --skip-build
# exe 干净验证模板（中立目录 + 剥离 PATH；%LOCALAPPDATA%\Temp\ssc_verif）
cd "$LOCALAPPDATA/Temp/ssc_verif" && env -i PATH="/c/Windows/System32:/c/Windows" SystemRoot="C:\\Windows" \
  "D:\...\dist\SSC\ssc-cli.exe" selfcheck
# 3.14 通道跑 GUI 冒烟（PYTHONPATH=src，未安装包时）
PYTHONPATH=src QT_QPA_PLATFORM=offscreen "%LOCALAPPDATA%\Python\bin\python.exe" -X utf8 <script>.py
# 安装（新环境，同 M4）
py -m pip install -U pip && NO_PROXY="*" no_proxy="*" py -m pip install -e .[dev] -i https://pypi.tuna.tsinghua.edu.cn/simple
# GUI 开发安装
NO_PROXY="*" no_proxy="*" py -m pip install -e .[gui,report,parse] -i https://pypi.tuna.tsinghua.edu.cn/simple
```
