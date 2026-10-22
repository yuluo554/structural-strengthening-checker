# RELEASE-M7（M7 严格化整改 → v0.1.1 发布留档）

> 日期：2026-10-22。本文件是 M7 里程碑 DoD 的证据留档，随仓公开。
> 纪律：本文只记载 `文件:行号 [类别] x次数` 形态的扫描结果，不回显任何敏感串原文。
> 上一版本：`v0.1.0-M6`（2026-10-06）——**其 tag 与 Release 附件本轮原封未动**。

## 一、本版改了什么（M7 = 严格化整改）

二次迭代诊断提出 11 条缺陷（D1–D11），用户对 7 个决策全部拍板 A 方案，分 6 批执行。
逐批动作、命令原文与输出见执行记录（`update/03-执行记录.md`，本地留档不入公共仓）；
本文件只留**发布面证据**。

| 缺陷 | 内容 | 处置 |
|---|---|---|
| D1 (P0) | 13 个提交的 author/committer 全是真实个人邮箱，公开可见 | `filter-branch` 全量改写为 GitHub noreply；轻量 tag 重打；Release target 同步 |
| D2 (P1) | `ssc bench` 只读 `bench["issues"]`，忽略 `failed`/`blocked_by_clauses` → 篡改算例真值仍 exit 0 | CLI 纳入两者；新增 `tests/test_bench_cli_gate.py`（CLI 层守门） |
| D3 (P1) | `requires-python >=3.8` 已 EOL；CI 4 腿里 2 条是 3.8 | ≥3.12；CI `{ubuntu-latest,windows-latest}×{3.12,3.13}` |
| D4 (P1) | 脱敏扫描器无自证、gate=4 全是假阳性、结果依赖本机 `user.name`、不扫提交元数据 | 统一 `classify_line` 口径 + 剥发布固有元数据；新增 `--selftest` 与 `--mode metadata`；CI 接入 |
| D5 (P2) | 条款有 `checked_date` 但无「何时该复核」 | 52 条 `source` 加 `next_review` / `review_interval`；新增守门测试 |
| D6 (P2) | 395 MB 未跟踪内容 | **不动**（`dist/`190M + `output/`103M + `build/`53M 全保留，均 gitignore） |
| D7 (P2) | 顶层 `code/` 空目录 | 删除（0 文件、未跟踪） |
| D8 (P2) | 无 EOL 字节级守门 | 新增 `tests/test_eol_guard.py`（索引层判据 + 阳性对照） |
| D9 (P2) | `tolerance_policy` 与 `scenario` 在 src 里 0 命中（纯装饰） | 删 `tolerance_policy`（14 例，已漂移出 3 种措辞）；`scenario` 保留并注明仅人读 |
| D10 (P2) | 版本一致性无守门 | 新增 `tests/test_version_single_source.py` |
| D11 (P2) | `.gitignore` 无 `update/` | 已加 |

## 二、干净环境验证

| 步骤 | 结果 |
|---|---|
| 基线（开发环境，`py -3.12` + 已装 gui/parse extras） | **168 passed, 0 skipped**（收集 168）；改前为 156 |
| 干净 venv（`%TEMP%\v-new`，仅 `.[dev]`） | **150 passed + 2 skipped**（收集 152）；两个 skip 均为显式声明：`test_gui.py:17` 无 PySide6、`test_parsing.py:83` 无 pypdf |
| 真 clone 复验（`%TEMP%\verify-clone`，clone 自 GitHub） | 同上 150 + 2；导入路径指向 **clone 的 src**（非开发仓，`pip -e` 生效） |
| 业务命令（干净 venv） | `selfcheck` → SELFCHECK_OK；`bench` → BENCH_OK / rc 0；`desensitize_scan` 三模式全 rc 0 |
| ★ 负控（干净 clone 内） | 篡改 `flexure_cases.json[0].expected.Mu_kNm=999.99` → **rc 1 + BENCH_FAIL**；恢复 → rc 0 + `git status` 空 |
| 计数口径 | 168（dev）= 150（干净）+ 17（test_gui 整模块 importorskip 不进入收集）+ 1（pypdf 运行期 skip）→ 对账成立，无静默少跑 |

## 三、脱敏四步扫描（M7 终扫，含 dist 产物本体）

```
[SCAN] 个人标记数=4 姊妹词=7 入仓文件=103 dist文件=277
[SUMMARY] repo_hits=5 dist_hits=0 total_files_hit=5
REVIEW plan/HANDOFF-M6.md:141 [ABS_PATH_SYS] x1
REVIEW plan/HANDOFF-M6.md:142 [ABS_PATH_ANY] x1
REVIEW plan/RELEASE-M6.md:38 [ABS_PATH_ANY] x1
REVIEW plan/RELEASE-M6.md:49 [ABS_PATH_SYS] x1
REVIEW plan/RELEASE-M6.md:50 [ABS_PATH_ANY] x1
[SUMMARY] gate=0 review=5
[VERDICT] SCAN_CLEAN
```

5 条 REVIEW 与本版 §二 的豁免台账同源（`HANDOFF-M6` 两处系统盘常量/省略号示例路径 +
`RELEASE-M6` 豁免台账自引三处），均为非个人信息，M6 起即如此，本轮未新增。
**dist 277 个文件字节级扫描 0 命中。**

### 本版新增的两道门

| 门 | 命令 | 结果 |
|---|---|---|
| 自证 | `tools/desensitize_scan.py --selftest` | `DESENSITIZE_SELFTEST_OK 10 项反证全部命中（阳性 5 / 阴性 5）` / rc 0 |
| 提交元数据 | `tools/desensitize_scan.py --mode metadata` | `mode=metadata 提交数=14` / `gate=0` / rc 0 |

### 负控（两道门都验证过「真会红」）

| 负控 | 做法 | 结果 |
|---|---|---|
| selftest | 把 `EMAIL_RE` 前缀改成永不匹配 | `阳性未报出: EMAIL` / `selftest 7/8` / `SELFTEST_FAIL` / rc 1 |
| metadata | 克隆本仓后用真实域邮箱造一个空提交 | `GATE_HIT commit author [EMAIL_METADATA]` ×2 / `gate=2` / rc 1 |

### 可复现性修复（D4 第③条）

改前 `personal_markers()` 会把本机 `git config user.name` 当标记，任何提到账号名的行都判 PERSONAL
——换台机器结果就不同。改后账号名按「发布固有公开元数据」整体剥除，实测模拟异机
（`USERNAME`/`USERPROFILE`/`HOME` 全换）仍 `gate=0 / SCAN_CLEAN`。

### 发布当轮发现并修掉的一个真漏洞（noreply 豁免的右边界）

写完本文件首版后重跑扫描，`plan/RELEASE-M7.md` 的「改写前/后对照」表被判 `[EMAIL]` —— 
因为它引用了 noreply 地址。这暴露两个问题：

1. **文档里引用 noreply 地址被当泄漏**：`--mode metadata` 已把 noreply 定为提交元数据唯一合法形态，
   文本扫描却不认，两处口径不一致 → 已补剥离规则（第 ③ 条）。
2. ★ **首版的剥离正则没有右边界**：`[A-Za-z0-9._%+-]+@users.noreply.github.com` 会匹配
   `…@users.noreply.github.com.evil.com` 的前缀并整条放行 —— 一个真实存在的伪造后缀漏洞。
   已加 `(?![A-Za-z0-9.-])` 钉住域名结尾。

边界用例 8 项逐一验证（真 QQ / 其他 noreply 域 / gmail 必须报；真 noreply 不报；
伪装子域必须报；noreply 后接空格/右括号/中文均不报），并把这个伪装子域用例**固化为
`--selftest` 的阳性项**，防将来退化。

### 自指假阳性（本轮踩到并修掉）

`--selftest` 的夹具若写字面量，会被扫描器扫到自身并打红（首跑出现 4 条 `GATE_HIT tools/desensitize_scan.py`）。
**没有**给扫描器加「豁免本文件」——那等于给门开后门；改为夹具**分段拼接**，使源码里不出现完整字面量。

## 四、提交元数据改写（D1，P0）

| 项 | 改写前 | 改写后 |
|---|---|---|
| author/committer 唯一值 | 真实个人邮箱（13/13 提交） | `282769740+yuluo554@users.noreply.github.com` |
| tag `v0.1.0-M6` | 轻量 → `90561a08…` | 轻量 → `07c505df…`（**形态未变**） |
| Release target | `main` | `07c505df66b572a55ac52f6a794a6eef9c30b340` |
| Release 附件 | 87,655,021 B / `sha256:cc05ca19…` | **完全相同**（附件是构建产物，不受历史改写影响） |

**内容零丢失自证**：用改写前的 `git bundle` 备份克隆出参照仓，逐提交比对 tree sha，
**13 个提交的 tree 逐一相同**；HEAD tree `4920ceb9…`、tag tree `843b2798…` 两端亦相同。
即改写只动身份字段，未改变任何文件内容。

改写前备份：`%TEMP%\ssc-before-rewrite.bundle`（360,519 B，`git bundle verify` 通过）。

## 五、Release 材料（v0.1.1）

| 项 | 值 |
|---|---|
| 版本 | **0.1.1**（`pyproject.toml` == `__init__.__version__` == README 首屏，守门测试锁死） |
| 产物 | `dist/SSC/` onedir 双 exe：`SSC.exe`（GUI）+ `ssc-cli.exe`（控制台） |
| 发布形态 | `output/SSC-v0.1.1-windows-x64.zip`，**79,537,764 B**，`sha256:deea94e3e033a54673914653d3cda568756c3d6ce8d8d9559243b7278ce257c5`（不入仓） |
| zip **打包**可复现 | 对**同一份 `dist/SSC`** 用固定时间戳重打两次，digest 逐字节相同 |
| ★ exe **构建**不可复现 | 重新跑 PyInstaller 后，277 个条目里 **274 个逐字节相同**，仅 `SSC.exe` / `ssc-cli.exe` / `_internal/base_library.zip` 三者字节变化（大小不变）。这是 PyInstaller 构建产物注入时间戳/引导哈希的固有行为；`SOURCE_DATE_EPOCH=1792713600` 实测**不能**消除。结论：**下载件可自校验**（给定 sha256），但不能由源码重建出同一字节 —— 与 setuptools 打 wheel 同类 |
| 红线断言 | 358 个路径，无 `_private/standards_raw/synthetic/workings` 成分；内嵌 knowledge 三库 + cases 与仓库逐份 JSON 对账一致 |
| 内嵌数据 | 含 `next_review` / `review_interval`（与源码同基线；旧 M6 exe 无此字段） |
| exe 冒烟 | `--version` → `ssc 0.1.1`；`selfcheck` → SELFCHECK_OK；`bench` → BENCH_OK；`modules` 4 模块全 READY；`check <docx>` → 规则判定与建议正常；`SSC.exe` offscreen 启动 12s 存活无报错 |
| ★ exe 侧 D2 负控 | 解压后以 `--data-dir <篡改副本> bench` → `[x] 算例真值比对失败 1 例` + `BENCH_FAIL` + **rc 1**（冻结产物上门槛真的生效） |

### ★ 构建通道变更（本版需留档的实质变化）

旧 M6 产物是 **cp314**（Python 3.14.5）通道构建；本版是 **cp312**（Python 3.12.10）通道。
差异实测：316 文件 / 198.3 MB → **277 文件 / 186.8 MB**（移除一批 3.14 专属 `.pyd`，
Qt 翻译/样式文件按 3.12 的 PySide6 6.6.3.1 收集）。功能面无退化——上表 exe 冒烟全通路已逐项验证。

口径说明：M5 定稿「冻结产物与构建解释器绑定、与 `requires-python` 无关」仍然成立；
本版改用 cp312 是因为本迭代把 floor 抬到 3.12 后，3.12 是**受支持面内的最低版本**，
用它构建可保证产物能覆盖全部受支持解释器语义（3.13 运行 cp312 字节码仍在支持范围内）。
M5 记录的「3.8 通道 7 次构建崩溃」与「3.14 通道 webbrowser 解析 bug」两条历史坑不变。

## 六、CI（整改提交 run `39700060745` head `1d0bd52`；发布提交 run `39702267844` head `cc9c2427`）

| job | 结论 | steps |
|---|---|---|
| test (windows-latest, 3.12, dev,gui) | success | 12/12 |
| test (windows-latest, 3.13, dev) | success | 12/12 |
| test (ubuntu-latest, 3.12, dev) | success | 12/12 |
| test (ubuntu-latest, 3.13, dev) | success | 12/12 |

注解：windows 两 job **0 条**；ubuntu 两 job 各 **1 条** —— 均为 `notice` 级
`ubuntu-latest 将于 2026-10-19 起迁移 Ubuntu 26` 的前瞻提示，**非 Node20 弃用**（改前每 job 1 条 Node20，
升级 actions v4/v5 → v7 后已清零）。实测运行镜像仍是 `Image: ubuntu-24.04`，尚未真迁移；
3.12/3.13 在 Ubuntu 26 同样受支持，故未回退到 EOL 的 `ubuntu-22.04`。

## 七、DoD 逐项

- [x] 提交元数据无个人邮箱（13/13 + 本版全部提交），`--mode metadata` 常驻 CI 防复发
- [x] tag 与 Release 指向一致，M6 附件 digest 未变
- [x] 算例门槛真正生效（源码侧 + 干净 clone 侧 + **冻结 exe 侧** 三重负控均为 rc 1）
- [x] `blocked_by_clauses` 纳入判定
- [x] 脱敏门自证（8/8）+ 假阳性清零（gate=4 → 0）+ 结果可复现 + 覆盖提交元数据
- [x] 52 条条款 + 2 份 data README 有复核锚（status 与 checked_date 一字未动：51 已核对 / 1 待核对）
- [x] EOL 字节级守门（索引层判据 + 阳性对照）
- [x] 版本单一来源守门
- [x] 测试不退化：156 → **168**（新增 12 项，既有断言零删除）
- [x] 干净环境全量复验 + CI 全绿


## 八、发布执行实录（2026-10-22）

| 动作 | 结果 |
|---|---|
| 提交 | `cc9c2427e802b10bb685eb071a6629592058a917`（M7 发布 v0.1.1）→ pushed origin/main |
| tag `v0.1.1` 初版 | **annotated `4b1f098d…` → peeled `cc9c2427…`**（曾与 HEAD 零滞后，后因下述缺陷修复而移指） |
| Release | https://github.com/yuluo554/structural-strengthening-checker/releases/tag/v0.1.1 （Latest，非 draft / 非 prerelease） |
| 附件（初版，已替换） | `SSC-v0.1.1-windows-x64.zip` 79,538,731 B，`sha256:71a4a91444c0c2a6d6b0e40f3a646e3bb875454aa53b17c0d0c16836a8239415` |
| **三方 sha256 对撞** | 本地打包值 = GitHub `assets[].digest` = **真下载后自算值** → 三者逐字符相同 ✅ |
| 真下载复验 | 通道 `gh api -H "Accept: application/octet-stream" .../releases/assets/664247032`（本机直连与代理均不可达，见 §八 第 3 条）；落盘 79,538,731 B → 解压 277 文件 → `ssc-cli.exe --version` = `ssc 0.1.1`、`selfcheck` = SELFCHECK_OK、`bench` = BENCH_OK ✅ |
| CI（发布提交） | run `39702267844`（head `cc9c2427`）**4 job × 12 step 全 success**，`bad=[]` |
| `v0.1.0-M6` 是否被波及 | **未变**：tag 仍 `07c505df…`；Release 附件仍 87,655,021 B / `cc05ca19…` ✅ |

附：本机 `curl` 直连 github.com 超时（rc 28），`--proxy 127.0.0.1:7897` 亦不可达（rc 7），
与 M6 记录的「本机代理不可达」一致；`gh api` 走 API 通道可正常取附件。

### ★ 发布后 20 分钟内的自我更正（D-M7-1，已处理）

本文件首版发布后，我按留档内容重跑扫描时发现 **脱敏扫描器 noreply 豁免有真实缺陷**：
剥离正则 `[A-Za-z0-9._%+-]+@users\.noreply\.github\.com` **没有右边界**，
于是「合法 noreply 域名 + 额外子域」这类**伪造后缀**会被整条放行 —— 邮箱硬门可被绕过
（具体构造见 `tools/desensitize_scan.py --selftest` 的阳性组，不在本文写字面量，避免留档自身被判命中）。

处置（用户拍板「移动 tag + 重传附件」）：

| 项 | 初版 | 修正后 |
|---|---|---|
| 扫描器 | 无右边界 | 加 `(?![A-Za-z0-9.-])` 钉住域名结尾 |
| selftest | 阳性 4 + 阴性 4 = 8 项 | **阳性 5 + 阴性 5 = 10 项**（新增：伪装子域必须报；noreply 不报） |
| exe | — | 重打包（`tools/` 不在 exe 内，但重新构建以保持 dist 与源码同基线） |
| zip | 79,538,731 B / `71a4a914…` | **79,537,764 B / `deea94e3…`** |
| tag | 指向 `cc9c2427` | **移指修正提交**，annotated 重打并 force push |
| Release | 已发布 | 附件替换 + 说明更新 |

边界用例 8 项逐一实测（真 QQ / 其他 noreply 域 / gmail → 必须报；真 noreply → 不报；
伪装子域 → 必须报；noreply 后接空格 / 右括号 / 中文 → 不报），全对；其中伪装子域用例已
**固化为 selftest 阳性项**防退化。

教训（写进方法库）：**「豁免」类规则必须钉两端边界**。只钉左端（`[A-Za-z0-9._%+-]+@`）
而放任右端，等于让任何以合法域名为前缀的伪造串都通过。这条与 M6 的「短标记要词边界」
是同一类错误，只不过发生在域的右侧。

## 九、遗留与偏差

1. **GUI 真窗口目检未做**（用户明确跳过）。已有证据：`test_gui.py` 17 项 offscreen 全绿、
   `SSC.exe` offscreen 启动 12s 存活无报错。**未做的**是人工看四页签的实际渲染与交互。
2. **JGJ 145-2013 §6.3 仍「待核对」**：本版未改其 status（改成已核对是造假）。
   三条既有失败渠道（济南审图 PDF 文字层失效 / 建标库未定位 / 道客巴巴登录墙）未突破。
3. **`output/` 103 MB 的来源仍未验证**（沿袭 M6 未知项）；按 DEC-6=A 未触碰任何工作区目录。
4. **`gb50367-2013.json` worktree 仍是 mixed CRLF**（本机 `core.autocrlf=true` 的检出痕迹，
   索引层纯净 0 CR）；刻意未"修"，否则在本机产生一次全文件 diff。
5. **`tolerance_policy` 已删**：若有下游消费者直接读该字段会失效。仓内 `src/` 0 命中（本就是装饰字段），
   口径已收敛到 `expected.tolerance`，`data/cases/README.md` 已注明。
6. **`build_exe.py` 的 docstring 用法示例已过时**（`ssc-cli.exe --cli selfcheck` 中的 `--cli` 不存在，
   正确是 `ssc-cli.exe selfcheck`）。属文档瑕疵，未在本版改动（不在授权改动面内）。
