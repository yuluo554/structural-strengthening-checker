"""docx/PDF 文本提取（M3 完整版）。依赖全部惰性导入，缺失抛 MissingExtraError。

确定性行为（plan/03 §三降级纪律）：
- docx 逐段提取（段落序号=原文档序号，供证据定位）；PDF 用 pypdf 逐页提取（页码=证据 page）；
- 损坏/加密/无文本层 → ParseError（受控异常），由 CLI 按"可解析段落 0"整体降级
  needs_confirm 清单，绝不 traceback、绝不产生 fail；
- 中文路径直接用 pathlib 传给底层库（Windows/CI 均为回归测试项）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..core.errors import MissingExtraError, ParseError


@dataclass
class Para:
    index: int  # 全文档段落序号（从 1 起）
    page: int  # PDF 有页码；docx 统一记 1（docx 无分页概念，页码定位在报告层说明）
    text: str


def _import_docx():
    try:
        import docx  # noqa: F401  python-docx
    except ImportError as exc:
        raise MissingExtraError("parse", "docx/PDF 文本提取") from exc
    return docx


def _import_pypdf():
    try:
        import pypdf  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError("parse", "PDF 文本提取") from exc
    return pypdf


def extract_docx_paras(path: Path) -> List[Para]:
    docx = _import_docx()
    try:
        document = docx.Document(str(path))
    except MissingExtraError:
        raise
    except Exception as exc:  # 损坏 zip / 非 OOXML / 版本不兼容等，统一受控降级
        raise ParseError(f"docx 解析失败: {path.name}（{type(exc).__name__}: {exc}）") from exc
    paras = []
    for i, p in enumerate(document.paragraphs, start=1):
        text = p.text.strip()
        if text:
            paras.append(Para(index=i, page=1, text=text))
    return paras


def extract_pdf_paras(path: Path) -> List[Para]:
    pypdf = _import_pypdf()
    try:
        reader = pypdf.PdfReader(str(path))
    except MissingExtraError:
        raise
    except Exception as exc:
        raise ParseError(f"PDF 打开失败: {path.name}（{type(exc).__name__}: {exc}）") from exc
    if getattr(reader, "is_encrypted", False):
        raise ParseError(f"PDF 已加密，不支持自动提取: {path.name}")
    paras = []
    seq = 0
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            text_blob = page.extract_text() or ""
        except Exception as exc:  # 单页内容流损坏：记空页继续，整体仍可用
            text_blob = ""
            paras.append(
                Para(index=len(paras) + 1, page=page_no,
                     text=f"[第{page_no}页文本提取失败: {type(exc).__name__}]")
            )
            continue
        for line in text_blob.splitlines():
            text = line.strip()
            if text:
                seq += 1
                paras.append(Para(index=seq, page=page_no, text=text))
    return paras


def extract_paras(path: Path) -> List[Para]:
    path = Path(path)
    if not path.is_file():
        raise ParseError(f"方案文件不存在: {path}")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_paras(path)
    if suffix == ".pdf":
        return extract_pdf_paras(path)
    raise ValueError(f"不支持的方案文件类型: {suffix}（当前支持 .docx/.pdf）")
