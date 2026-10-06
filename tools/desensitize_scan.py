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
退出码：0=硬门全清（复核项另行列出）；1=硬门有命中（处置后复扫）。
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


def sibling_words() -> list:
    return [w for w in base64.b64decode(_SIBLING_B64).decode("utf-8").splitlines() if w]


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


def scan_text(path: Path, rel: str, markers: list, sib: list, hits: list) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        scan_bytes_file(path, rel, markers, sib, hits)
        return
    exempt_abs = rel.replace("\\", "/") == GUARD_TEST
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        # 先剥离 URL 协议头与 github.com/账号名（后者是发布固有公开元数据，见模块文档），
        # 防协议部分被误判为盘符绝对路径、账号名误触个人标记
        line = URL_RE.sub("", raw_line)
        line = re.sub(r"github\.com/[A-Za-z0-9-]+", "", line, flags=re.IGNORECASE)
        if EMAIL_RE.search(line):
            hits.append((rel, lineno, "EMAIL", 1))
        if marker_hit(line, markers):
            hits.append((rel, lineno, "PERSONAL", 1))
        if not exempt_abs:
            if ABS_PATH_USER_RE.search(line):
                hits.append((rel, lineno, "ABS_PATH_USER", 1))
            elif ABS_PATH_SYS_RE.search(line):
                hits.append((rel, lineno, "ABS_PATH_SYS", 1))
            elif ABS_PATH_ANY_RE.search(line):
                hits.append((rel, lineno, "ABS_PATH_ANY", 1))
        for w in sib:
            if w.lower() in line.lower():
                hits.append((rel, lineno, "SIBLING", 1))
                break


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


def main() -> int:
    ap = argparse.ArgumentParser(description="脱敏四步扫描（发布门）")
    ap.add_argument("--repo-only", action="store_true", help="不扫 dist/")
    args = ap.parse_args()

    markers = personal_markers()
    sib = sibling_words()
    hits = []

    files = tracked_files()
    for p in files:
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if p.suffix.lower() == ".docx":
            scan_docx_meta(p, rel, markers, sib, hits)
        scan_text(p, rel, markers, sib, hits)

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
