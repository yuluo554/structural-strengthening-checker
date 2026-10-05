"""docx/PDF 文本提取（M3 实装完整版）。依赖全部惰性导入，缺失抛 MissingExtraError。

骨架已实现的确定性行为：docx 逐段提取（段落序号保留，供证据定位）；
PDF 用 pypdf 逐页提取（页码=证据 page）。中文路径与编码为回归测试项。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..core.errors import MissingExtraError


@dataclass
class Para:
    index: int  # 全文档段落序号（从 1 起）
    page: int  # PDF 有页码；docx 统一记 1（页码定位 M3 增强）
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
    document = docx.Document(str(path))
    paras = []
    for i, p in enumerate(document.paragraphs, start=1):
        text = p.text.strip()
        if text:
            paras.append(Para(index=i, page=1, text=text))
    return paras


def extract_pdf_paras(path: Path) -> List[Para]:
    pypdf = _import_pypdf()
    reader = pypdf.PdfReader(str(path))
    paras = []
    seq = 0
    for page_no, page in enumerate(reader.pages, start=1):
        for line in (page.extract_text() or "").splitlines():
            text = line.strip()
            if text:
                seq += 1
                paras.append(Para(index=seq, page=page_no, text=text))
    return paras


def extract_paras(path: Path) -> List[Para]:
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return extract_docx_paras(path)
    if suffix == ".pdf":
        return extract_pdf_paras(path)
    raise ValueError(f"不支持的方案文件类型: {suffix}（当前支持 .docx/.pdf）")
