"""合成加固方案生成器 v1：python-docx + 固定 seed，注入已知错误输出真值 JSON。

真值语义一次定清（评测按"文档全部非 pass 集合"对账，plan/05 §四）：
- 注入项记主期望 expected_verdict（M1 全部为 fail，与规则库 severity 对应）；
- 同一注入隐含的其余结论记 also_expect（M1 四类注入互不隐含，恒为空列表；
  后续扩展注入若触达多规则，必须在此显式登记，防止误报口径漂移）；
- 多报 also_expect 之外的问题算误报（误报 0 目标口径）。

确定性纪律：
- 全部随机量来自 random.Random(seed)，固定 seed 可复现；
- python-docx 产出的 zip 带当前时间戳，save 后统一重写 zip 归一化时间戳，
  保证同 seed 两次运行产物 sha256 一致（M1 DoD：生成器两次运行产物一致）。

互斥坑当场记录（生成期已处理）：
- 四类注入分别作用于不同章节/段落，删除型注入（missing_*）只删目标段落，
  不触碰其他注入的宿主段落——多注入组合互不打架；
- 胶粘剂指标段为单值段落，adhesive_grade_low 整段替换（先清旧行再写新值），
  避免同参数两处注入打架；
- 锚固深度同理单值替换。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from ..core.errors import MissingExtraError

# 注入错误类型与规则库 rule_id 一一对应（plan/05 §四，rule_id 联动）
INJECTION_RULE_MAP = {
    "adhesive_grade_low": "R-ADH-001",         # 胶粘剂安全性能指标低于限值（GB 55021-2021 表B.0.2）
    "anchor_depth_insufficient": "R-ANCH-001",  # 锚固/植筋深度不足（GB 50367-2013 15.2.3）
    "missing_appraisal_first": "R-APP-001",     # 漏"先鉴定后加固"环节（GB 55021-2021 1.0.3）
    "missing_unloading": "R-CONST-001",         # 构造措施缺失：卸载/支撑要求未提（GB 55021-2021 6.1.5）
}

INJECTION_TYPES = tuple(INJECTION_RULE_MAP)

DEFAULT_SEED = 20261005

# 合规基线文案（clean_baseline）：四条规则在基线文档上均应 pass
BASELINE_TITLE = "某教学楼结构加固方案（合成基线，固定 seed 生成）"
BASELINE_SECTIONS = [
    (
        "一、工程概况与加固方案",
        [
            "本工程为既有教学楼混凝土结构加固工程，根据加固设计委托要求编制本加固方案。",
            "加固方法：梁采用粘贴碳纤维复合材加固，柱采用增大截面加固法，梁柱节点钢筋连接采用植筋。",
        ],
    ),
    (
        "二、检测鉴定结论",
        [
            "本工程已按先检测、鉴定的程序完成结构安全性鉴定和抗震鉴定，鉴定报告编号：JD-2026-088。",
            "鉴定结论：梁受弯承载力不满足要求，柱轴压比偏大，需进行承载能力加固；加固设计以鉴定报告为依据。",
        ],
    ),
    (
        "三、加固设计说明",
        [
            "加固材料：混凝土强度等级 C40，植筋采用 HRB400 带肋钢筋，直径 12mm。",
            "结构胶：采用 A 级改性环氧结构胶粘剂，钢对钢拉伸抗剪强度标准值 15.8MPa，性能符合 GB 50728-2011 第 4.2.2 条安全性鉴定要求。",
            "植筋锚固深度：锚固深度设计值 320mm，经设计计算确定（不低于按 GB 50367-2013 式 15.2.3 计算的基本锚固深度乘修正系数），不采用厂商技术手册推荐值。",
            "加固后正截面受弯承载力经验算满足现行标准规定，并已验算受剪承载力。",
        ],
    ),
    (
        "四、构造措施与施工要求",
        [
            "卸载要求：加固施工前按设计规定卸除活荷载，对被加固构件设置临时支撑，卸载经验收后方可施工。",
            "施工质量检验与竣工验收：加固施工完成后按 GB 50550-2010 进行施工质量检验和竣工验收，合格后方允许投入使用。",
        ],
    ),
]

# 注入宿主段落定位（与基线段落一一对应；删除型注入只删目标段）
_ADH_HOST = "钢对钢拉伸抗剪强度标准值"
_ANCH_HOST = "锚固深度设计值"
_APPRAISAL_TITLE = "二、检测鉴定结论"
_UNLOAD_HOST = "卸载要求"


def _import_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        raise MissingExtraError("report", "合成加固方案 docx 生成") from exc
    return docx


def _normalize_zip(path: Path) -> None:
    """重写 zip：所有条目时间戳归一为 (1980,1,1,0,0,0)，保证同内容 docx 字节一致。"""
    tmp = path.with_suffix(".docx.tmp")
    with zipfile.ZipFile(path, "r") as zin, zipfile.ZipFile(
        tmp, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            entry = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = info.external_attr
            zout.writestr(entry, data)
    tmp.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section_entries() -> List[List[str]]:
    """拍平基线段落（标题+正文），供逐段操作。"""
    entries: List[str] = []
    for title, paras in BASELINE_SECTIONS:
        entries.append(title)
        entries.extend(paras)
    return entries


def _apply_injections(paras: List[str], injections: List[str]) -> List[str]:
    """按注入类型改写段落副本。四类注入宿主互不重叠（见模块注释互斥坑记录）。"""
    out = list(paras)
    for kind in injections:
        if kind == "adhesive_grade_low":
            # 先清旧行再写新值：单值段整段替换（同参数两处注入打架的规避）
            for i, p in enumerate(out):
                if _ADH_HOST in p:
                    out[i] = (
                        "结构胶：采用 A 级改性环氧结构胶粘剂，钢对钢拉伸抗剪强度标准值 "
                        "12.0MPa，性能符合 GB 50728-2011 第 4.2.2 条安全性鉴定要求。"
                    )
                    break
        elif kind == "anchor_depth_insufficient":
            for i, p in enumerate(out):
                if _ANCH_HOST in p:
                    out[i] = (
                        "植筋锚固深度：锚固深度设计值 150mm（按 GB 50367-2013 式 15.2.3 计算的"
                        "基本锚固深度乘修正系数后不低于此值），不采用厂商技术手册推荐值。"
                    )
                    break
        elif kind == "missing_appraisal_first":
            # 删除鉴定结论小节（标题+该节全部正文段）
            idx = out.index(_APPRAISAL_TITLE)
            del out[idx : idx + 3]
        elif kind == "missing_unloading":
            out = [p for p in out if _UNLOAD_HOST not in p]
        else:  # pragma: no cover - INJECTION_TYPES 受控
            raise ValueError(f"未知注入类型: {kind}")
    return out


def _write_docx(docx_mod: Any, paras: List[str], out_path: Path) -> None:
    doc = docx_mod.Document()
    doc.add_heading(BASELINE_TITLE, level=0)
    for p in paras:
        if re.match(r"^[一二三四五六七八九十]+、", p):
            doc.add_heading(p, level=1)
        else:
            doc.add_paragraph(p)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    _normalize_zip(out_path)


def generate(out_dir: Path, seed: int = DEFAULT_SEED, count: int = 5) -> Dict[str, Any]:
    """生成 1 份合规基线 + count 份注入文档 + truth.json。返回 truth 结构。"""
    docx_mod = _import_docx()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    baseline_paras = _section_entries()

    # 注入计划：count>=4 时先保证每类注入各出现一次，其余按 seed 随机组合（1~3 类）
    plan: List[List[str]] = []
    base_types = list(INJECTION_TYPES)
    for kind in base_types[:count]:
        plan.append([kind])
    for _ in range(max(0, count - len(base_types))):
        k = rng.randint(2, 3)
        plan.append(rng.sample(base_types, k))

    truth_docs: List[Dict[str, Any]] = []
    baseline_path = out_dir / f"baseline_seed{seed}.docx"
    _write_docx(docx_mod, baseline_paras, baseline_path)
    truth_docs.append(
        {
            "doc_name": baseline_path.name,
            "doc_sha256": _sha256(baseline_path),
            "clean_baseline": True,
            "injected": [],
            "expected_non_pass": [],
        }
    )

    for i, injections in enumerate(plan, start=1):
        paras = _apply_injections(baseline_paras, injections)
        path = out_dir / f"case{i:02d}_seed{seed}.docx"
        _write_docx(docx_mod, paras, path)
        injected = [
            {
                "type": kind,
                "rule_id": INJECTION_RULE_MAP[kind],
                "param": {
                    "adhesive_grade_low": "adhesive_indices[钢对钢拉伸抗剪强度标准值]=12.0MPa",
                    "anchor_depth_insufficient": "anchor_depths[植筋]=150mm",
                    "missing_appraisal_first": "appraisal_first 缺失",
                    "missing_unloading": "unloading 描述缺失",
                }[kind],
                "expected_verdict": "fail",
                "also_expect": [],
            }
            for kind in injections
        ]
        truth_docs.append(
            {
                "doc_name": path.name,
                "doc_sha256": _sha256(path),
                "clean_baseline": False,
                "injected": injected,
                "expected_non_pass": [item["rule_id"] for item in injected],
            }
        )

    truth = {
        "generator": "structural_strengthening_checker.datagen.gen_plan v1",
        "seed": seed,
        "truth_semantics": (
            "评测按文档全部非 pass 集合对账：expected_non_pass 为主期望集合（全部 fail），"
            "注入隐含的其余结论记 also_expect（v1 四类注入互不隐含，恒为空）；"
            "多报 also_expect 之外的问题算误报。"
        ),
        "docs": truth_docs,
    }
    truth_path = out_dir / "truth.json"
    truth_path.write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return truth


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gen_plan", description="合成加固方案生成器 v1（固定 seed，注入已知错误输出真值）"
    )
    parser.add_argument("--out", required=True, help="输出目录")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子（默认固定）")
    parser.add_argument("--count", type=int, default=5, help="注入文档数量（另有 1 份合规基线）")
    args = parser.parse_args(argv)
    truth = generate(Path(args.out), seed=args.seed, count=args.count)
    print(f"生成完成: {len(truth['docs'])} 份文档（1 基线 + {args.count} 注入），seed={args.seed}")
    for d in truth["docs"]:
        marks = ",".join(item["rule_id"] for item in d["injected"]) or "clean_baseline"
        print(f"  - {d['doc_name']}  sha256={d['doc_sha256'][:12]}  [{marks}]")
    print(f"真值: {Path(args.out) / 'truth.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
