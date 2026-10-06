# RELEASE-M6（M6 脱敏发布留档）

> 日期：2026-10-06。本文件是 M6 里程碑 DoD 的证据留档（plan/05 §五 M6），随仓公开。
> 纪律：本文只记载 文件:行号 [类别] x次数 形态的扫描结果，不回显任何敏感串原文。

## 一、干净环境验证（新 clone + 新 venv 按 README 逐字跑通）

| 步骤 | 结果 |
|---|---|
| 基线（dev 环境） | pytest 156 项全绿（exit 0）；`--collect-only` 收集数 **156**（15 个测试文件），与 HANDOFF-M6 记录一致 |
| 新 clone | 中立目录 `%LOCALAPPDATA%\Temp\ssc_m6_clean`，clone 自本地仓库 → HEAD d1d45d4（M5 交付提交） |
| 新 venv | py -3.8 -m venv .venv（Python 3.8.8）；`pip install -U pip` → pip 25.0.1 |
| 按 README 逐字安装 | `pip install -e .[dev]` **默认 PyPI 直连一次成功**（未动用清华镜像，无网络偏离）；依赖 pytest 8.3.5 / python-docx 1.1.2 / lxml 6.1.3 等 |
| pytest（干净 venv） | exit 0；收集数 **139**；**138 passed + 2 skipped（均显式声明，-rs 可见）** |
| 收集数对账 | 139（干净）+ 17（test_gui 模块在无 PySide6 时整模块 importorskip，不进入收集）= **156 与 dev 逐一对应，无静默少跑**；另 1 个运行期 skip 为 parse extras 缺席时的 PDF 用例（tests/test_parsing.py 显式条件跳过，同为既定口径） |
| selfcheck | SELFCHECK_OK（exit 0；gui/parse extras 缺席按需提示，属设计行为） |
| bench | BENCH_OK（exit 0；检出率/误报/判定准确率门槛全达，check 基准 6/6 逐份 OK） |
| 安装态确认 | 导入路径 = 干净 clone 的 src（pip 可编辑安装生效，非 conftest 回退路径） |

**结论：干净环境验证通过。** 真异机验证与物理断网演示留发布验收复核（M5 起以等效证据背书，口径未变）。

## 二、脱敏四步扫描（工具化 + 三轮实录）

**工具**：`tools/desensitize_scan.py`（入仓，可复现）。口径：
- 扫描面：git 跟踪文件全树（95 文件，src/tests/tools/plan/data/README/.github 全含）+ dist 产物本体（316 文件，字节级）+ docx 元数据（docProps/*.xml）+ dist 禁区路径成分复核（与 build_exe.py 红线断言双保险）；
- 四步类别：EMAIL / PERSONAL（git 姓名·邮箱·本机用户名·主目录，运行时收集不落明文）/ ABS_PATH（USER=用户目录【硬门】；SYS=系统目录【复核】；ANY=其余盘符【复核】）/ SIBLING（姊妹项目词表 base64 脱敏存储）；
- 短标记（<6 字符）要求非字母数字边界（防 midasuser / caucasus 之类子串误报）；
- 判定：硬门类目任一命中 exit 1；SYS/ANY 为复核项，人工留档处置；
- 留档纪律：输出不含敏感串原文（本文件因此可随仓公开）。

### 处置实录（第 1 轮发现 → 处置 → 第 3 轮全清）

| 轮次 | 发现 | 处置 |
|---|---|---|
| R1 | plan/00 第 5 行 [SIBLING]：项目系列前作 ①~⑦ 名称与领域枚举 | 掩码为"同系列第 8 题（①~⑦ 名称与领域清单按脱敏纪律不入公开仓）"；姊妹词表以 base64 形式存于扫描器，词表明文不入仓 |
| R1 | plan/06 第 49 行、plan/HANDOFF-M6 多行 [ABS_PATH+PERSONAL]：3.14 构建通道解释器的用户目录绝对路径 | 全部改写为 `%LOCALAPPDATA%\Python\bin\python.exe`（相对主目录形式，可复现性不变、用户名移除） |
| R1 | tests/test_gui.py 第 189 行 [ABS_PATH_ANY]：测试夹具含盘符路径 "Z:/…" | 改为无盘符文件名（测试语义不变：路径串存在性） |
| R1 | plan/HANDOFF-M4 第 108 行 [PERSONAL]："midasuser.com" 内含用户名子串 | 误报，非真实标记——扫描器引入短标记词边界规则后消除 |
| R2 | dist 5 个 Qt 二进制 [BYTES_PERSONAL] | 误报定位：Qt6Core.dll 内嵌 Windows 时区名 "caucasus standard time"（含 a-s-u-s 序列）；字节扫描补齐与文本扫描同口径的短标记边界规则后消除。其余个人标记（主目录路径/姓名/邮箱）在 dist 316 文件中 0 命中（Python 字节探测逐一验证） |
| R1 | dist 多文件 [BYTES_MARKER]（PIL/PySide6/cryptography SBOM/base_library.zip 等） | 上游厂商二进制内的公共邮箱（SBOM/LICENSE 维护者元数据）与二进制噪声；非本项目泄漏面。口径定稿：dist 字节扫描只跑强标记（个人标记+姊妹词），不跑邮箱正则 |

### 复核项豁免台账（R3 剩余，全部非个人信息）

| 位置 | 类别 | 豁免理由 |
|---|---|---|
| plan/HANDOFF-M6.md:139 [ABS_PATH_SYS] | `SystemRoot="C:\\Windows"`（exe 干净验证模板） | Windows 系统盘常量，env -i 剥离环境后必须显式给出，不含任何个人/机器信息 |
| plan/HANDOFF-M6.md:140 [ABS_PATH_ANY] | `"D:\...\dist\SSC\ssc-cli.exe"`（示例路径） | 已是省略号掩码形态，非真实路径 |

### 最终结论（R3）

```
[SUMMARY] repo_hits=2 dist_hits=0 total_files_hit=2   （2 项均为上表复核项）
[SUMMARY] gate=0 review=2
[VERDICT] SCAN_CLEAN
```

**脱敏四步（邮箱/姓名/绝对路径/姊妹项目业务词）+ dist 产物本体扫描：全部通过。**

### 方法论备注

- 二进制探测以 Python 字节读法为准；`grep -r` 不带 `-a` 对二进制目录递归不可靠（单文件带 `-a` 可用），本实录中的 grep 探测矛盾已用 Python 探测仲裁；
- LICENSE 版权行与 pyproject authors 均为 "structural-strengthening-checker contributors"，无个人署名；
- 开发期守门 tests/test_project_guards.py::test_no_personal_paths_in_source 只覆盖 src（扫描面所限），plan/ 与 tools/ 由本扫描器覆盖，两层互补。

## 三、Release 材料（本地就绪，发布动作待用户逐项确认）

- **exe 产物**：`dist/SSC/`（onedir 双 exe：SSC.exe GUI + ssc-cli.exe 控制台；构建红线断言已过——dist 全树无 `_private/standards_raw/synthetic/workings` 成分，内嵌 knowledge 三库 + cases 与仓库逐份对账一致）；发布形态为 zip 包（`output/SSC-v0.1.0-windows-x64.zip`，83.6MB，sha256 `cc05ca19a348cdb5d4ccd9f9ee1fea8689270f4257254e77a7a5a0020e3dda19`，不入仓，挂 GitHub Release）；
- **技术报告**：`docs/技术报告.md`（Markdown 入仓，结算 plan/06 待拍板 #5 的默认方案；docx 固化为可选项，发布后按需）；
- **发布动作确认清单**（plan/06 待拍板 #4/#6——逐项用户确认后执行，本文件留档）：
  1. GitHub 建仓 `github.com/yuluo554/structural-strengthening-checker`（公开）+ push（description/topics 草案见确认请求）；
  2. tag `v0.1.0-M6` + GitHub Release 附 exe zip；
  3. topics 设置；
  4. 对外动作分级授权（待拍板 #6：是否参加真实赛事/对外投稿）。

## 四、M6 遗留与偏差

- 无新增技术遗留。JGJ 145-2013 §6.3 渠道不可达待核对（M1 起留痕，不阻塞）；裂缝修补规则 P1/P2 扩展未入库（既定范围外）；
- 姊妹项目名称与领域清单按脱敏纪律不入仓（本文件与 plan/00 同步掩码）——原清单仅存于本地 plan 历史与项目方法论文档；
- py 测试计数口径：dev 156 = 干净 clone 139 + GUI 17（模块级条件跳过，声明式，-rs 可见）。
