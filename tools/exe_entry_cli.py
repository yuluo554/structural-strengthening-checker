"""PyInstaller CLI 入口（ssc-cli.exe，console）：与 ssc 完全同一 cli.main。

用途：无 Python 机器上脚本化验证（selfcheck/bench/check/report 全通路），
是"exe 在无 Python 机器可跑"的逐项证据出口；GUI 用户日常不接触本 exe。
"""

from __future__ import annotations

import sys

from structural_strengthening_checker.cli import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
