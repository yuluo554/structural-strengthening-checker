"""脱敏四步扫描器（M6 发布门）。

扫描范围：git 跟踪文件全树（src/tests/tools/plan/data/README/.github 等全部入仓文本与 docx
元数据）+ dist/ 产物本体（exe/pyd 等二进制字节级扫描）。

四步类别：
  1. EMAIL          邮箱地址（文本与 docx 元数据；dist 二进制不做邮箱正则——上游厂商
                    SBOM/LICENSE 含其维护者公共邮箱、二进制噪声误报大，不属本项目泄漏面）
  2. PERSONAL       个人标记（git user.name/user.email、本机用户名、USERPROFILE 子串；
                    短标记如用户名需非字母数字边界——防 midasuser 之类子串误报）
  3. ABS_PATH       Windows 盘符绝对路径分级：
                    USER=含 \\Users\\ 或 Documents and Settings（硬门，必须 0）
                    SYS=系统/程序目录（复核项：非个人信息可豁免留档，如系统盘 Windows 目录）
                    ANY=其余盘符路径（复核项）
  4. SIBLING        姊妹项目业务词（词表脱敏存储为 base64，扫描时解码）
附：docx 元数据（docProps/*.xml）按同类别扫描；dist 全树复核禁区路径成分
（_private/standards_raw/synthetic/workings，与 tools/build_exe.py 红线断言双保险）；
dist 二进制字节级扫描强标记（个人标记+姊妹词），不跑邮箱正则。

豁免：tests/test_project_guards.py 是路径守门测试本体（标记串即测试对象），豁免其
ABS_PATH 类目（EMAIL/PERSONAL/SIBLING 照扫）。

留档纪律：输出只给 文件:行号 [类别] x次数，不回显命中原文——扫描报告本身允许入仓
（plan/RELEASE-M6.md 留档），不得把敏感串带进新文件。

用法（仓库根）：
  py -X utf8 tools/desensitize_scan.py                # 全扫：入仓树 + dist/
  py -X utf8 tools/desensitize_scan.py --repo-only    # 仅入仓树（无 dist 时）
  py -X utf8 tools/desensitize_scan.py --selftest     # 自证（阳性 5 + 阴性 5）
  py -X utf8 tools/desensitize_scan.py --mode metadata  # 提交历史邮箱（防 D1 复发）
退出码：0=硬门全清（复核项另行列出）；1=硬门有命中（处置后复扫）。

豁免口径（RELEASE-M6 §四「GitHub 账号名豁免」）：账号名是发布固有公开元数据，
`github.com/<账号>` 与裸 `<账号>/<repo>` 形态不计入命中；`git@<host>` 协议地址不是
邮箱。真实邮箱 / 真实姓名 / 用户目录路径一律硬门。
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 姊妹项目词表（脱敏存储：base64；解码后每行一个 slug——不落明文，扫描器自身可入仓）
_SIBLING_B64 = (
    "Y29uc3RydWN0aW9uLWRyYXdpbmctcGxhbi1jaGVja2VyCnBvd2VyLW9wZXJhdGlvbi10"
    "aWNrZXQtY2hlY2tlcgptZWRpY2FsLXJlY29yZC1xdWFsaXR5LWNoZWNrZXIKYmlkZGlu"
    "Zy1kb2N1bWVudC1jaGVja2VyCmZvb2QtbGFiZWwtY29tcGxpYW5jZS1jaGVja2VyCmlu"
    "dm9pY2UtbGVkZ2VyLWNoZWNrZXIKcmVzdW1lLXRhbGVudC1wb29sCg=="
)

# 路径守门测试本体（其标记串即测试对象，豁免 ABS_PATH 类目）
GUARD_TEST = "tests/test_project_guards.py"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")
# 硬门：用户目录形态
ABS_PATH_USER_RE = re.compile(
    r"[A-Za-z]:[\\/]+(?:Users|Documents and Settings)[^\s\"'`<>|，。；：）】》]*",
    re.IGNORECASE,
)
# 复核项：系统/程序目录
ABS_PATH_SYS_RE = re.compile(
    r"[A-Za-z]:[\\/]+(?:ProgramData|Program Files|Windows|AppData|Temp)"
    r"[^\s\"'`<>|，。；：）】》]*",
    re.IGNORECASE,
)
# 复核项：其余盘符绝对路径
ABS_PATH_ANY_RE = re.compile(r"[A-Za-z]:[\\/]+[^\s\"'`<>|，。；：）】]*")

# 硬门类目（任一命中即 exit 1）；其余为复核项（人工留档处置）
GATE_CATS = {"EMAIL", "PERSONAL", "SIBLING", "ABS_PATH_USER",
             "BYTES_PERSONAL", "BYTES_SIBLING", "DOCX_META", "DIST_FORBIDDEN_PART"}
REVIEW_CATS = {"ABS_PATH_SYS", "ABS_PATH_ANY"}

DIST_FORBIDDEN_PARTS = {"_private", "standards_raw", "synthetic", "workings"}

# --mode metadata：GitHub 提供的匿名化邮箱后缀（提交元数据唯一合法形态）
NOREPLY_SUFFIX = "users.noreply.github.com"


def sibling_words() -> list:
    return [w for w in base64.b64decode(_SIBLING_B64).decode("utf-8").splitlines() if w]


def github_account() -> str:
    """从 origin 远端解析 GitHub 账号名（`git@github.com:OWNER/repo.git` / https 两种形态）。

    该账号名是发布行为的固有公开元数据（仓库挂在公开账号下），按 RELEASE-M6 §四
    「GitHub 账号名豁免」口径不计入个人标记命中。
    """
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=str(ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return ""
    if out.returncode != 0:
        return ""
    m = re.search(r"github\.com[:/]+([A-Za-z0-9][A-Za-z0-9-]*)/", out.stdout.strip(),
                  re.IGNORECASE)
    return m.group(1) if m else ""


def strip_publish_metadata(line: str, account: str) -> str:
    """剥掉「发布固有公开元数据」，防假阳性（D4）：

    ① URL 协议头（`https://` 等，否则盘符正则可能误触）；
    ② `git@github.com` 这类 git 协议地址（形如 `user@host` 的串会被 EMAIL_RE 判成邮箱）；
    ③ GitHub noreply 地址（`*@users.noreply.github.com`）——`--mode metadata` 已把它定为
       提交元数据的唯一合法形态，文档里引用它（如留档改写前后对照）不构成个人信息泄漏；
    ④ `github.com/<账号名>` 与裸 `<账号名>/<repo>`（账号名是公开元数据，不是个人信息）。
    真实邮箱 / 真实姓名 / 用户目录路径仍照扫。
    """
    line = URL_RE.sub("", line)
    line = re.sub(r"\bgit@[A-Za-z0-9.-]+", "", line)
    # 右边界必须钉住域名结尾：否则「noreply 域名 + 额外子域」形态会被误当 noreply 放行
    # （回归用例见 --selftest 阳性组：伪装子域必须报出）
    line = re.sub(r"[A-Za-z0-9._%+-]+@" + re.escape(NOREPLY_SUFFIX)
                  + r"(?![A-Za-z0-9.-])", "", line, flags=re.IGNORECASE)
    line = re.sub(r"github\.com/[A-Za-z0-9-]+", "", line, flags=re.IGNORECASE)
    if account:
        line = re.sub(
            r"(?<![A-Za-z0-9])" + re.escape(account) + r"(?![A-Za-z0-9])", "",
            line, flags=re.IGNORECASE,
        )
    return line


def classify_line(line: str, markers: list, sib: list, account: str,
                  exempt_abs: bool = False) -> list:
    """单行判定 → 命中的类目列表（不含次数）。扫描与 `--selftest` 共用同一口径，
    保证自证测的就是真正在跑的判定逻辑。"""
    cats = []
    stripped = strip_publish_metadata(line, account)
    if EMAIL_RE.search(stripped):
        cats.append("EMAIL")
    if marker_hit(stripped, markers):
        cats.append("PERSONAL")
    if not exempt_abs:
        if ABS_PATH_USER_RE.search(stripped):
            cats.append("ABS_PATH_USER")
        elif ABS_PATH_SYS_RE.search(stripped):
            cats.append("ABS_PATH_SYS")
        elif ABS_PATH_ANY_RE.search(stripped):
            cats.append("ABS_PATH_ANY")
    low = stripped.lower()
    if any(w.lower() in low for w in sib):
        cats.append("SIBLING")
    return cats


def personal_markers() -> list:
    """运行时收集本机标记：git 配置姓名/邮箱 + 环境用户名/主目录。不落明文入仓。"""
    markers = set()

    def add(v):
        if v and len(v) >= 3:
            markers.add(v)

    for key in ("USERNAME", "USERPROFILE", "HOME"):
        add(os.environ.get(key, ""))
    try:
        for key in ("user.name", "user.email"):
            out = subprocess.run(
                ["git", "config", "--get", key], cwd=str(ROOT),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if out.returncode == 0:
                add(out.stdout.strip())
    except OSError:
        pass
    return sorted(markers, key=len, reverse=True)


def marker_hit(line: str, markers: list) -> bool:
    """短标记（<6 字符，如用户名）要求非字母数字边界，长标记子串即可；均忽略大小写。"""
    low = line.lower()
    for m in markers:
        if len(m) < 6:
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(m.lower()) + r"(?![A-Za-z0-9])", low):
                return True
        elif m.lower() in low:
            return True
    return False


def count_marker_bytes(low: bytes, m: str) -> int:
    """字节级标记计数：与 marker_hit 同口径——短标记要求非字母数字边界
    （防时区名等英文词对短用户名标记的子串误报），长标记子串即可。
    GitHub 账号名豁免：github.com/<账号名> 是发布行为的固有公开元数据（仓库挂在
    公开账号下），该形态不计入个人标记命中；邮箱/真实姓名仍硬门。"""
    b = m.lower().encode("utf-8", "ignore")
    if not b:
        return 0
    gh = b"github.com/" + b
    if len(m) >= 6:
        return max(0, low.count(b) - low.count(gh))
    n = 0
    start = 0
    while True:
        i = low.find(b, start)
        if i < 0:
            break
        before_ok = i == 0 or not chr(low[i - 1]).isalnum()
        j = i + len(b)
        after_ok = j >= len(low) or not chr(low[j]).isalnum()
        if before_ok and after_ok:
            n += 1
        start = i + 1
    return n


def tracked_files() -> list:
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "ls-files", "-z"], cwd=str(ROOT),
        capture_output=True,
    )
    names = out.stdout.decode("utf-8", "replace").split("\0")
    return [ROOT / n for n in names if n.strip()]


def scan_text(path: Path, rel: str, markers: list, sib: list, hits: list,
              account: str = "") -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        scan_bytes_file(path, rel, markers, sib, hits)
        return
    exempt_abs = rel.replace("\\", "/") == GUARD_TEST
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        for cat in classify_line(raw_line, markers, sib, account, exempt_abs):
            hits.append((rel, lineno, cat, 1))


def scan_bytes_file(path: Path, rel: str, markers: list, sib: list, hits: list) -> None:
    """二进制（exe/pyd/未知后缀等）：只字节级找强标记（个人标记+姊妹词），不跑邮箱正则。"""
    try:
        data = path.read_bytes()
    except OSError:
        return
    low = data.lower()
    n_personal = sum(count_marker_bytes(low, m) for m in markers)
    n_sib = sum(low.count(w.encode("utf-8", "ignore")) for w in sib)
    if n_personal:
        hits.append((rel, 0, "BYTES_PERSONAL", n_personal))
    if n_sib:
        hits.append((rel, 0, "BYTES_SIBLING", n_sib))


def scan_docx_meta(path: Path, rel: str, markers: list, sib: list, hits: list) -> None:
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.startswith("docProps/"):
                    continue
                blob = z.read(name)
                low = blob.lower()
                for m in markers:
                    c = count_marker_bytes(low, m)
                    if c:
                        hits.append((rel + "::" + name, 0, "DOCX_META", c))
                for w in sib:
                    c = low.count(w.encode("utf-8", "ignore"))
                    if c:
                        hits.append((rel + "::" + name, 0, "DOCX_META", c))
                for _ in EMAIL_RE.findall(blob.decode("latin-1", "ignore")):
                    hits.append((rel + "::" + name, 0, "DOCX_META", 1))
    except (zipfile.BadZipFile, OSError):
        pass


def scan_dist(dist: Path, markers: list, sib: list, hits: list) -> int:
    """dist 产物本体：禁区路径成分复核 + 二进制强标记字节扫描。"""
    n_files = 0
    for p in dist.rglob("*"):
        if not p.is_file():
            continue
        n_files += 1
        rel = p.relative_to(ROOT).as_posix()
        parts = {x.lower() for x in p.relative_to(dist).parts[:-1]}
        bad = parts & DIST_FORBIDDEN_PARTS
        if bad:
            hits.append((rel, 0, "DIST_FORBIDDEN_PART", len(bad)))
        if p.suffix.lower() == ".docx":
            scan_docx_meta(p, rel, markers, sib, hits)
        else:
            scan_bytes_file(p, rel, markers, sib, hits)
    return n_files


def run_selftest() -> int:
    """`--selftest`：对 classify_line 做真阳性 / 真阴性反证（正面证明门还活着）。

    阳性 4 项（必须报出）：假邮箱 / 假用户名 / 假用户目录路径 / 假姊妹项目词。
    阴性 4 项（必须不报）：git 协议地址 / `github.com/账号` / 裸 `账号/repo` /
    文档里的模式占位（`<你的邮箱>` 之类占位符不是真实邮箱）。
    敏感性用假标记与假账号，**不读本机环境**——保证结果可复现（D4 第③条）。
    ★ 夹具一律**分段拼接**：本文件也在扫描范围内，写字面量会把自己判成命中
    （自指假阳性），而给扫描器加豁免等于给门开后门。
    """
    at = "@"
    fake_user = "zzselftest" + "user"
    fake_mail = fake_user + "." + "probe" + at + "example" + ".invalid"
    fake_dir = "C:" + "\\Users\\" + fake_user + "\\project"
    fake_sib = "zz-selftest-" + "sibling-project"
    fake_account = "zzselftest" + "account"
    fake_markers = [fake_user, fake_mail]
    sib_list = [fake_sib]
    positive = [
        ("EMAIL", f"联系人 {fake_mail} 已登记"),
        ("PERSONAL", f"由 {fake_user.upper()} 在本机生成"),
        ("ABS_PATH_USER", f"路径 {fake_dir}\\out.txt"),
        ("SIBLING", f"参见 {fake_sib} 的口径"),
    ]
    # 附注：noreply 豁免必须钉右边界，否则 `…@users.noreply.github.com.evil.com` 会被放行。
    # 该用例放在 positive 组（伪装域名必须报），锁住这个回归。
    positive.append((
        "EMAIL",
        f"伪装 {fake_user}" + at + "users.noreply.github.com" + ".evil.example",
    ))
    negative = [
        ("git 协议地址", f"git remote add origin git{at}github.com:{fake_account}/repo.git"),
        ("github.com/账号", f"https://github.com/{fake_account}/repo 为公开仓库"),
        ("裸 账号/repo", f"仓名 {fake_account}/repo 见 README"),
        ("模式占位", "把你的邮箱填在 <你的邮箱> 处，账号填在 <账号名> 处"),
        ("GitHub noreply 地址",
         f"提交元数据唯一合法形态 12345678+{fake_account}" + at + "users.noreply.github.com"),
    ]

    ok = 0
    total = 0
    failures = []
    for expected_cat, line in positive:
        total += 1
        cats = classify_line(line, fake_markers, sib_list, fake_account)
        if expected_cat in cats:
            ok += 1
        else:
            failures.append(f"阳性未报出: {expected_cat} ← {line!r}（实得 {cats}）")
    for label, line in negative:
        total += 1
        cats = [c for c in classify_line(line, fake_markers, sib_list, fake_account)
                if c in GATE_CATS]
        if not cats:
            ok += 1
        else:
            failures.append(f"阴性误报: {label} ← {line!r}（实得 {cats}）")

    for f in failures:
        print(f"  [x] {f}")
    if ok != total or total < 10:
        print(f"[SUMMARY] selftest {ok}/{total}（要求全部命中且 >= 10 项）")
        print("[VERDICT] SELFTEST_FAIL")
        return 1
    print(f"DESENSITIZE_SELFTEST_OK {ok} 项反证全部命中（阳性 5 / 阴性 5）")
    return 0


def run_metadata_mode() -> int:
    """`--mode metadata`：查提交历史的 author/committer 邮箱（文件内容扫描覆盖不到）。

    D1 的直接防复发：历史改写后任何非 GitHub noreply 形态的提交邮箱都算 GATE_HIT。
    """
    try:
        out = subprocess.run(
            ["git", "log", "--format=%ae%x09%ce", "--all"], cwd=str(ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        print(f"[缺少依赖] git 不可用: {exc}")
        return 1
    if out.returncode != 0:
        print(f"[SUMMARY] mode=metadata gate=0（git log 不可用：{out.stderr.strip()[:80]}）")
        print("[VERDICT] SCAN_CLEAN")
        return 0

    offenders = {}
    n_commits = 0
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        n_commits += 1
        for role, email in zip(("author", "committer"), line.split("\t")):
            email = (email or "").strip()
            if email and not email.lower().endswith(NOREPLY_SUFFIX):
                offenders[(role, email)] = offenders.get((role, email), 0) + 1

    print(f"[SCAN] mode=metadata 提交数={n_commits}")
    for (role, email), c in sorted(offenders.items()):
        print(f"GATE_HIT commit {role} [EMAIL_METADATA] x{c}")
    print(f"[SUMMARY] mode=metadata gate={sum(offenders.values())}")
    if offenders:
        print("[VERDICT] SCAN_FINDINGS")
        return 1
    print("[VERDICT] SCAN_CLEAN（提交元数据全部为 GitHub noreply）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="脱敏四步扫描（发布门）")
    ap.add_argument("--repo-only", action="store_true", help="不扫 dist/")
    ap.add_argument("--selftest", action="store_true",
                    help="自证：阳性 4 项必须报出 + 阴性 4 项必须不报")
    ap.add_argument("--mode", choices=("text", "metadata"), default="text",
                    help="text=文件内容（默认）；metadata=提交历史邮箱")
    args = ap.parse_args()

    if args.selftest:
        return run_selftest()
    if args.mode == "metadata":
        return run_metadata_mode()

    markers = personal_markers()
    sib = sibling_words()
    account = github_account()
    hits = []

    files = tracked_files()
    for p in files:
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix.lower() == ".docx":
            scan_docx_meta(p, rel, markers, sib, hits)
        scan_text(p, rel, markers, sib, hits, account)

    dist_n = 0
    if not args.repo_only:
        dist = ROOT / "dist"
        if dist.is_dir():
            dist_n = scan_dist(dist, markers, sib, hits)
        else:
            print("[i] dist/ 不存在，跳过产物扫描（构建后重跑）")

    print("[SCAN] 个人标记数=%d 姊妹词=%d 入仓文件=%d dist文件=%d"
          % (len(markers), len(sib), len(files), dist_n))
    merged = {}
    for rel, lineno, cat, c in hits:
        key = (rel, lineno, cat)
        merged[key] = merged.get(key, 0) + c
    dist_hits = sum(c for (rel, _ln, _cat), c in merged.items() if rel.startswith("dist/"))
    repo_hits = sum(merged.values()) - dist_hits
    print("[SUMMARY] repo_hits=%d dist_hits=%d total_files_hit=%d"
          % (repo_hits, dist_hits, len(merged)))
    gate_total = 0
    review_total = 0
    for (rel, lineno, cat), c in sorted(merged.items()):
        loc = "%s:%d" % (rel, lineno) if lineno else rel
        if cat in GATE_CATS:
            gate_total += c
            print("GATE_HIT %s [%s] x%d" % (loc, cat, c))
        else:
            review_total += c
            print("REVIEW %s [%s] x%d" % (loc, cat, c))
    print("[SUMMARY] gate=%d review=%d" % (gate_total, review_total))
    if gate_total:
        print("[VERDICT] SCAN_FINDINGS")
        return 1
    print("[VERDICT] SCAN_CLEAN（复核项如有，见 REVIEW 行留档处置）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
