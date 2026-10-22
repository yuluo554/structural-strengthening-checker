"""EOL 字节级守门（D8）：仓库存储层不得出现 CR，CRLF 文件必须被点名。

为什么判「存储层」而不是 worktree：本机 `core.autocrlf=true`，检出时会把 LF 重写成
CRLF。所以 worktree 里有 CR **不代表仓库有这个缺陷**——判据必须是索引/blob 那一层。
`git ls-files --eol` 同时给出 `i/`（索引）与 `w/`（worktree）两侧，本守门只看 `i/`。

两类文件都要扫：
  ① 已跟踪文件 → `i/lf` 或 `i/-text`（二进制）合法；`i/crlf` / `i/mixed` 非法。
  ② 未跟踪且未被忽略的文件 → 会被下一次 `git add` 收进去，按真实字节查 CR。

口径不手工维护 SKIP 名单：凡 git 认定为二进制（`attr/-text`、`i/-text`）的自然豁免，
文本文件一律在门内。这样「新增一个 data/ 子目录」不会被漏检。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(REPO_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout


def tracked_cr_offenders() -> list:
    """索引层带 CR 的已跟踪文本文件（逐条给 `路径 i/xxx w/xxx`）。"""
    offenders = []
    for line in _git("ls-files", "--eol").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        head, path = parts[0], parts[1]
        fields = head.split()
        index_state = fields[0] if fields else ""
        # i/lf 与 i/-text（二进制）合法；i/crlf / i/mixed / i/none 之外的形态都点名
        if index_state in ("i/lf", "i/-text", "i/none"):
            continue
        offenders.append(f"{path} {index_state}")
    return offenders


def untracked_cr_offenders() -> list:
    """未跟踪且未被忽略的文件里，真实字节带 CR 的（这些会被下次 add 收进仓库）。"""
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "ls-files", "-z", "--others",
         "--exclude-standard"],
        cwd=str(REPO_ROOT), capture_output=True, check=True,
    ).stdout.decode("utf-8", "replace")
    offenders = []
    for name in out.split("\0"):
        if not name.strip():
            continue
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        if b"\0" in path.read_bytes()[:8192]:  # 二进制豁免（同 git 的启发式）
            continue
        if b"\r" in path.read_bytes():
            offenders.append(name)
    return offenders


def all_offenders() -> list:
    return tracked_cr_offenders() + untracked_cr_offenders()


def test_tracked_files_store_lf_only():
    """已跟踪文件的索引层必须是 LF（或 git 判定的二进制）。"""
    offenders = tracked_cr_offenders()
    assert offenders == [], (
        "索引层含 CR（.gitattributes 要求 eol=lf）：\n  " + "\n  ".join(offenders)
    )


def test_untracked_files_have_no_cr():
    """未跟踪且未被忽略的文件不得含 CR（它们会被下次 add 收进仓库）。"""
    offenders = untracked_cr_offenders()
    assert offenders == [], (
        "未跟踪文件含 CR，提交前须转 LF：\n  " + "\n  ".join(offenders)
    )


def test_guard_is_sensitive_to_crlf():
    """★ 阳性对照：造一个会被提交的 CRLF 文件 → 守门必须点名它。

    没有这条，本文件只是「一个永远绿的断言」——无法区分「仓库干净」与「守门失效」。
    用独立文件名（不叫 probe_crlf.txt），这样手工放 `probe_crlf.txt` 做人工探针时，
    只会打红真正的门（test_untracked_files_have_no_cr），不会连带打红本条自证。
    """
    probe = REPO_ROOT / "probe_crlf_selftest.txt"
    assert not probe.exists(), f"阳性对照文件名被占用：{probe}"
    try:
        probe.write_bytes(b"a\r\nb\r\n")
        offenders = untracked_cr_offenders()
        assert "probe_crlf_selftest.txt" in offenders, (
            f"守门对 CRLF 不敏感（未点名 probe_crlf_selftest.txt），实得 {offenders}"
        )
    finally:
        probe.unlink(missing_ok=True)
    assert not probe.exists()
