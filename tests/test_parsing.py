"""M3 解析层：docx/PDF 提取完整版 + 参数卡抽取（含防幻觉证据审计）。

生成器语料依赖 python-docx（dev extras）；PDF 用例依赖 pypdf（parse extras），
缺失时整文件跳过（CI dev 矩阵跑 docx 部分）。
"""

import pytest

from structural_strengthening_checker.core.errors import ParseError
from structural_strengthening_checker.parsing.docx_text import (
    extract_docx_paras,
    extract_paras,
)
from structural_strengthening_checker.parsing.param_card_builder import build_param_card

pytest.importorskip("docx", reason="dev extras 未安装 python-docx 时跳过解析层测试")

import docx as docx_mod  # noqa: E402


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    """现场生成合成方案语料（seed 固定可复现，M3 端到端演示用）。"""
    from structural_strengthening_checker.datagen import gen_plan

    out = tmp_path_factory.mktemp("corpus")
    truth = gen_plan.generate(out, seed=20261005, count=5)
    return out, truth


def _paras(corpus_dir, name):
    return extract_docx_paras(corpus_dir / name)


# ---------------------------------------------------------------------------
# 文本提取
# ---------------------------------------------------------------------------

def test_docx_paras_indexes_and_text(corpus):
    corpus_dir, _ = corpus
    paras = _paras(corpus_dir, "baseline_seed20261005.docx")
    assert len(paras) == 15
    assert paras[0].index == 1
    assert all(p.page == 1 for p in paras)
    assert any("钢对钢拉伸抗剪强度标准值" in p.text for p in paras)


def test_docx_chinese_path(tmp_path, corpus):
    corpus_dir, _ = corpus
    src = corpus_dir / "baseline_seed20261005.docx"
    dst = tmp_path / "加固方案_中文路径测试.docx"
    dst.write_bytes(src.read_bytes())
    paras = extract_paras(dst)
    assert len(paras) == 15


def test_corrupt_docx_raises_parse_error(tmp_path):
    bad = tmp_path / "损坏方案.docx"
    bad.write_bytes(b"PK\x03\x04 not a real zip payload")
    with pytest.raises(ParseError):
        extract_paras(bad)


def test_missing_file_raises_parse_error(tmp_path):
    with pytest.raises(ParseError):
        extract_paras(tmp_path / "不存在.docx")


def test_unsupported_suffix_still_value_error(tmp_path):
    fake = tmp_path / "plan.txt"
    fake.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_paras(fake)


def test_empty_docx_zero_paras(tmp_path):
    blank = tmp_path / "空白.docx"
    docx_mod.Document().save(str(blank))
    assert extract_paras(blank) == []


def test_pdf_no_text_layer_extracts_empty(tmp_path):
    pytest.importorskip("pypdf", reason="parse extras 未安装 pypdf 时跳过 PDF 用例")
    import pypdf

    pdf_path = tmp_path / "无文本层.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    with open(str(pdf_path), "wb") as fh:
        writer.write(fh)
    assert extract_paras(pdf_path) == []


# ---------------------------------------------------------------------------
# 参数卡抽取（基线语料 = 全合规版本，四条规则的核查对象齐备）
# ---------------------------------------------------------------------------

def test_baseline_card_full_extraction(corpus):
    corpus_dir, _ = corpus
    card = build_param_card(_paras(corpus_dir, "baseline_seed20261005.docx"))
    assert [m.name for m in card.methods] == [
        "粘贴碳纤维复合材加固", "增大截面加固法", "植筋（后锚固连接）",
    ]
    adh = [(i.kind, i.value, i.unit, i.label) for i in card.adhesive_indices]
    assert ("钢对钢拉伸抗剪强度标准值", 15.8, "MPa", "A") in adh
    assert [(i.kind, i.value) for i in card.anchor_depths] == [("植筋", 320.0)]
    kinds = {i.kind: i for i in card.design_params}
    assert kinds["植筋直径"].value == 12.0
    assert kinds["钢筋牌号"].label == "HRB400"
    assert kinds["混凝土强度等级"].value == 40.0
    assert kinds["胶粘剂等级"].label == "A"
    assert card.unloading and card.unloading[0].kind == "卸载"
    assert card.appraisal_first is not None
    assert card.notes == []
    assert card.evidence_issues() == []


def test_case03_appraisal_missing_case04_unloading_missing(corpus):
    corpus_dir, truth = corpus
    card3 = build_param_card(_paras(corpus_dir, "case03_seed20261005.docx"))
    assert card3.appraisal_first is None  # 鉴定小节整段删除
    # 材料段"安全性鉴定要求"（GB 50728 引文）不得误判为程序性鉴定证据
    card4 = build_param_card(_paras(corpus_dir, "case04_seed20261005.docx"))
    assert card4.unloading == []  # 卸载段删除
    # 多重组合 case05：三处注入同落
    card5 = build_param_card(_paras(corpus_dir, "case05_seed20261005.docx"))
    assert card5.appraisal_first is None
    assert [(i.kind, i.value) for i in card5.anchor_depths] == [("植筋", 150.0)]
    assert card5.adhesive_indices[0].value == 12.0


def test_all_quotes_are_source_substrings(corpus):
    corpus_dir, truth = corpus
    for doc in truth["docs"]:
        card = build_param_card(_paras(corpus_dir, doc["doc_name"]))
        assert card.evidence_issues() == [], doc["doc_name"]
        for item in card.adhesive_indices + card.anchor_depths + card.unloading:
            assert item.evidence.quote in card.source_text


def test_evidence_substring_guard_drops_item():
    """防幻觉闸：人工构造非子串 quote 的卡片项必须被丢弃并留痕（FR-B5）。"""
    from structural_strengthening_checker.parsing.docx_text import Para

    paras = [Para(index=1, page=1, text="方案正文：采用结构胶粘剂加固。")]
    card = build_param_card(paras)
    assert card.source_text == "方案正文：采用结构胶粘剂加固。"
    # 直接向卡片塞入伪造项再走 _safe_add 等价路径：用 evidence_issues 复核
    from structural_strengthening_checker.parsing.param_card import ValueItem, Evidence

    card.adhesive_indices.append(
        ValueItem(kind="钢对钢拉伸抗剪强度标准值", value=99.0, unit="MPa",
                  evidence=Evidence(para=1, quote="这句是编造的，不在原文里"))
    )
    issues = card.evidence_issues()
    assert len(issues) == 1 and "不是原文子串" in issues[0]


def test_full_text_includes_methods_for_gating(corpus):
    corpus_dir, _ = corpus
    card = build_param_card(_paras(corpus_dir, "case04_seed20261005.docx"))
    # R-CONST-001 门控词是加固方法名：即使卸载段已删，方法段仍在 → 门控必须激活
    assert "碳纤维" in card.full_text()
    assert "增大截面" in card.full_text()
