"""M2 参数扫描回归：固定 seed 随机参数网格 → 输出位级锁定（同输入必同输出）。

口径（plan/05 §三 / plan/06 EOL 决策）：
- 全部随机量出自 random.Random(SEED)，输入四舍五入到固定小数位，杜绝平台浮点表示噪声；
- 锁定对象 = json.dumps(结果载荷, sort_keys=True, separators) 的 sha256（含 warnings/metrics 全文）；
- 双跑一致 + 金标准哈希（GOLDEN_SHA256）双保险：金标准防实现漂移，改公式/改判定必须
  有意识地重算并更新（重算方法：删除 GOLDEN_SHA256 断言 → 跑 test_param_sweep_bit_level_lock
  读失败信息中的 actual → 回填）。
"""

import hashlib
import json
import random

from structural_strengthening_checker.calc import EXPECTED_MODULES
from structural_strengthening_checker.core.clauses import ClauseStore
from structural_strengthening_checker.core.engine import run_calc

SEED = 20261005
N_PER_MODULE = 12
# 首次落定 2026-10-05（M2）：seed=20261005 × 12 落点/模块 × 4 模块（三态分布 满足24/需调整21/不满足3）
GOLDEN_SHA256 = "fe738b0bdee024233038567289c07b59b4f88659e2275ada6997ac4a89046215"


def _r3(rng, lo, hi):
    return round(rng.uniform(lo, hi), 3)


def _grid(module_id):
    rng = random.Random(SEED)
    grids = []
    for _ in range(N_PER_MODULE):
        if module_id == "cfrp_beam_flexure":
            grids.append({
                "b": _r3(rng, 200, 400), "h": _r3(rng, 400, 700),
                "fc": 14.3, "As": _r3(rng, 800, 2600), "fy": 360.0,
                "Afe": _r3(rng, 50, 350), "Ecf": 240000.0,
                "M0": 0.0 if rng.random() < 0.5 else _r3(rng, 40, 120),
                "M": _r3(rng, 100, 320),
                "ff": 2300.0, "ef": 0.01, "as": _r3(rng, 30, 50),
                "xi_b": 0.518, "Es": 200000.0,
            })
        elif module_id == "steel_plate_flexure":
            grids.append({
                "b": _r3(rng, 200, 400), "h": _r3(rng, 400, 700),
                "fc": 14.3, "As": _r3(rng, 800, 2600), "fy": 360.0,
                "Ap": _r3(rng, 150, 1000), "fp": 215.0,
                "M0": 0.0 if rng.random() < 0.5 else _r3(rng, 40, 120),
                "M": _r3(rng, 120, 300),
                "as": _r3(rng, 30, 50), "xi_b": 0.518,
                "Es": 200000.0, "Esp": 206000.0,
            })
        elif module_id == "section_enlarge_flexure":
            grids.append({
                "b": _r3(rng, 200, 400), "h": _r3(rng, 400, 700),
                "bf": 250.0, "hf": _r3(rng, 60, 160),
                "fc": 14.3, "fc2": 16.7,
                "As": _r3(rng, 800, 2600), "fy": 360.0,
                "As2": _r3(rng, 200, 1000), "fy2": 360.0,
                "as": 35.0, "as2": _r3(rng, 35, 70),
                "M0": 0.0 if rng.random() < 0.5 else _r3(rng, 40, 120),
                "M": _r3(rng, 150, 320), "Es": 200000.0,
            })
        else:  # post_rebar_anchor
            grids.append({
                "fc": 14.3,
                "fy": _r3(rng, 300, 400), "d": _r3(rng, 10, 28),
                "ld": _r3(rng, 150, 800),
                "alpha_spt": _r3(rng, 0.7, 1.3), "fbd": _r3(rng, 2.5, 4.5),
                "psi_br": rng.choice([1.0, 1.15, 1.5]),
                "psi_w": 1.1, "psi_T": 1.0,
                "psi_ae": rng.choice([1.0, 1.1, 1.25]),
            })
    return grids


def _collect(repo_data_dir):
    store = ClauseStore(repo_data_dir / "knowledge")
    payloads = []
    for module_id in sorted(EXPECTED_MODULES):
        for i, params in enumerate(_grid(module_id)):
            try:
                result = run_calc(module_id, params, store)
                payloads.append({"module": module_id, "i": i, "result": result})
            except Exception as exc:  # noqa: BLE001  异常也纳入锁定（确定性）
                payloads.append(
                    {"module": module_id, "i": i,
                     "error": "%s: %s" % (type(exc).__name__, exc)}
                )
    blob = json.dumps(payloads, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest(), payloads


def test_param_sweep_bit_level_lock(repo_data_dir):
    """双跑位级一致 + 金标准哈希锁定（防实现漂移）。"""
    sha1, _ = _collect(repo_data_dir)
    sha2, _ = _collect(repo_data_dir)
    assert sha1 == sha2, "同 seed 双跑结果不一致（位级锁定失败）"
    assert sha1 == GOLDEN_SHA256, (
        "参数扫描金标准哈希不符（实现漂移）。如属有意修改，请按本模块 docstring 重算回填："
        "actual=%s" % sha1
    )


def test_param_sweep_all_reach_verdict(repo_data_dir):
    """扫描网格全部落点必须产出三态结论（无异常、无空 capacity）。"""
    _, payloads = _collect(repo_data_dir)
    assert len(payloads) == N_PER_MODULE * len(EXPECTED_MODULES)
    for item in payloads:
        assert "error" not in item, item
        assert item["result"]["verdict"] in ("满足", "不满足", "需调整")
        assert item["result"]["capacity"]["value"] is not None
