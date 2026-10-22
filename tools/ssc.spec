# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec（M5，plan/06 决策）：onedir 双 exe——SSC.exe（GUI）+ ssc-cli.exe（控制台）。

构建（仓库根运行）:
    py -X utf8 -m PyInstaller --noconfirm --clean tools/ssc.spec
    py -X utf8 tools/build_exe.py        # 带红线断言的构建封装（推荐）

数据内嵌（plan/06 决策）：仅 data/knowledge/** 与 data/cases/*.json。
data/_private/（规范全文，版权红线）、standards_raw/、synthetic/、cases/workings/ 一律不入包，
tools/build_exe.py 构建后遍历 dist 断言。运行期查找走 core/paths 冻结分支（sys._MEIPASS 优先）。

要求 PyInstaller>=6（项目 floor 3.12；PyInstaller 6.x 起支持 3.12/3.13）；
PySide6/python-docx/pypdf 由构建环境安装的 extras（gui/report/parse）带入。
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # spec 位于 tools/，上级即仓库根

datas = [(str(ROOT / "data" / "knowledge"), "data/knowledge")]
datas += [(str(p), "data/cases") for p in sorted((ROOT / "data" / "cases").glob("*.json"))]

common = dict(
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hookspath=[],
    runtime_hooks=[],
    # 本机不用的 stdlib 重模块排除：缩小 modulegraph 字节码扫描面（稳定性+体积）；
    # webbrowser：3.14 构建通道下 PyInstaller 6.22.3 对其字节码模式有解析 bug（实录
    # plan/06，"Failed to scan the module 'webbrowser'"），本工具不使用浏览器
    excludes=["tkinter", "test", "unittest", "pydoc_data", "lib2to3", "webbrowser"],
    noarchive=False,
)

gui_a = Analysis([str(ROOT / "tools" / "exe_entry_gui.py")], **common)
cli_a = Analysis([str(ROOT / "tools" / "exe_entry_cli.py")], **common)
pyz_gui = PYZ(gui_a.pure)
pyz_cli = PYZ(cli_a.pure)

exe_gui = EXE(
    pyz_gui,
    gui_a.scripts,
    [],
    exclude_binaries=True,
    name="SSC",
    debug=False,
    console=False,
    icon=None,
)
exe_cli = EXE(
    pyz_cli,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name="ssc-cli",
    debug=False,
    console=True,
    icon=None,
)

# PyInstaller 5.x 有 a.zipfiles TOC（6.x 移除/为空）——getattr 双版本兼容
zipfiles = []
for _a in (gui_a, cli_a):
    zipfiles.extend(getattr(_a, "zipfiles", []))

coll = COLLECT(
    exe_gui,
    exe_cli,
    gui_a.binaries,
    gui_a.datas,
    cli_a.binaries,
    cli_a.datas,
    *zipfiles,
    strip=False,
    upx=False,
    name="SSC",
)
