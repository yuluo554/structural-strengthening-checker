# HANDOFF-M7（M6 脱敏发布 → 项目完结收官快照）

> **⚠️ 本文件为 M6 收官时的历史快照，已被 M7 迭代超越。** 当前版本为 **v0.1.1**（2026-10-22）。
> 上一里程碑：M6 脱敏发布（✅ 2026-10-06）。当前里程碑：M7 严格化整改（✅ 2026-10-22，
> 发布实录见 `plan/RELEASE-M7.md` 与 plan/06 已定决策表 M7 各行）。
> M7 相对本快照的变化摘要：提交元数据已全量改写为 GitHub noreply（13 提交，tag 重打 `07c505df`）；
> 算例门槛真正生效（篡改算例 → exit 1）；脱敏门新增 `--selftest`/`--mode metadata` 且假阳性清零；
> 52 条条款加复核锚；floor 3.8→3.12、CI 改 3.12/3.13 四矩阵；pytest 156→168。

## 一、完结状态

- **发布地址**：https://github.com/yuluo554/structural-strengthening-checker （公开）
- **tag**：`v0.1.0-M6`（指向 90561a0——发布动作用户确认留档提交）
- **Release**：https://github.com/yuluo554/structural-strengthening-checker/releases/tag/v0.1.0-M6
  附 `SSC-v0.1.0-windows-x64.zip`（83.6MB，sha256 `cc05ca19a348cdb5d4ccd9f9ee1fea8689270f4257254e77a7a5a0020e3dda19`，
  onedir 双 exe：SSC.exe 图形界面 + ssc-cli.exe 控制台，内嵌知识库，全离线即用）
- **元信息**：description + topics 10 个（structural-engineering / civil-engineering / code-compliance /
  compliance-checking / gb-55021 / gb-50367 / reinforced-concrete / rule-engine / pyside6 / offline-first）
- **CI 首跑四矩阵全绿**（run 37398155895）：windows/3.8+gui = 155 passed+1 显式 skip；其余三矩阵 138+2
  （gui 模块级 skip + pypdf 缺席 PDF 用例）；全部为声明式条件跳过，计数口径与 dev 156 逐一对账；
  selfcheck / bench 步骤全矩阵通过；
- **技术报告**：`docs/技术报告.md`（Markdown 入仓，验算公式编码方案/条文核对流程/合成数据设计）；
- **发布留档**：`plan/RELEASE-M6.md`（干净环境验证证据 / 脱敏扫描五轮实录与豁免台账 / 发布动作拍板留档）。

## 二、M6 DoD 复核（逐项）

- [x] 干净环境验证：新 clone + 新 venv 按 README 逐字跑通（默认 PyPI 直连一次成功）；
      pytest 收集数对账（139+GUI 17=156，防"双绿但悄悄少跑"）；SELFCHECK_OK；BENCH_OK；
      发布提交终态复验通过
- [x] 脱敏四步：邮箱/姓名/绝对路径/姊妹项目业务词——工具化 `tools/desensitize_scan.py`，
      入仓树+dist 产物本体（316 文件字节级）+docx 元数据全扫；硬门全清（gate=0/review=5，
      复核项均为非个人信息豁免留档）；dist 无个人标记（Python 字节探测逐一验证）
- [x] Release 材料：GitHub 公开仓库 + Release 附 exe zip + 技术报告 Markdown 入仓
- [x] CI 首跑四矩阵全绿（含 bench 门 + windows/3.8 的 gui extras 矩阵）
- [x] 收尾固化：tag v0.1.0-M6 / topics 10 个 / README 快速开始转正（去"当前骨架"字样）/
      缓议项清零（待拍板 #4/#5/#6 全部结算）
- [x] 发布动作逐项用户确认留档（RELEASE-M6 §五：建仓推送/tag+Release/元信息草案/对外动作保持缓议）
- [x] 回写 plan/00·05·06 + README + 本完结快照；git 提交推送入库
- 偏差说明：无新增遗留。真实赛事/对外投稿保持缓议（用户拍板，留档）。

## 三、既定口径存续（完结后仍有效）

- 全部既定口径见 **HANDOFF-M6 §三**（GUI 消费面纪律 / find_data_dir 冻结分支 / spec datas 白名单 /
  spec excludes / 双 exe 结构 / CI extras 矩阵 / test_gui 环境前提；M4 及更早口径摘要在其 §3.2）；
- 决策影响速查（改动前必读）见 **plan/06** 末节——改验算模块清单/真值语义/生成器种子/bench 门槛/
  extras 划分/条款门控语义均有联动守门，不许静默变更；
- 脱敏纪律（完结新增）：`tools/desensitize_scan.py` 为常驻发布门——任何入仓变更后发布前复扫
  （`py -X utf8 tools/desensitize_scan.py`，exit 0 才发布）；GitHub 账号名=公开元数据豁免口径、
  短标记词边界、dist 二进制只跑强标记，三条口径写在扫描器内并留档 RELEASE-M6 §二。

## 四、本机环境坑（完结时有效）

- 全集见 **HANDOFF-M6 §四**（PyInstaller 必走 3.14.5 通道 / webbrowser excludes / spec 脚本路径 /
  中立目录验证 exe / Git Bash 管道吃退出码等），全部继续有效；
- **完结新增两条**：①gh OAuth token 无 workflow scope——推含 `.github/workflows` 的提交被拒，
  用 SSH 密钥通道推送（本机 id_ed25519 已认证 yuluo554）；②Git Bash `grep -r` 不带 `-a` 对二进制
  目录递归不可靠（单文件带 `-a` 可用）——二进制探测一律以 Python 字节读法为准。

## 五、开放项与后续扩展（完结留档，均不阻塞）

- JGJ 145-2013 §6.3 渠道不可达待核对（M1 起熔断留痕，不进计算路径）；
- 裂缝修补方式核查规则 P1/P2 扩展未入库（与规则库 rule_id 联动的预留位）；
- 砌体/钢结构加固验算模块（首期范围外的既定扩展方向）；
- 技术报告 docx 固化（可选后续）；
- 待拍板 #6：真实赛事/对外投稿保持缓议（用户 2026-10-06 拍板，若启动再单独确认）。

## 六、关键命令速查

```bash
# 全部见 HANDOFF-M6 §六（测试/自检/基准/构建/干净验证模板继续有效），新增一条：
# 脱敏发布门复扫（任何发布前必跑，exit 0 才可发布）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/desensitize_scan.py
# GitHub 侧（完结态）
gh run list --limit 3                 # CI 状态
gh release view v0.1.0-M6             # Release 与附件
```
