"""CLI 冒烟：selfcheck/modules/calc 门控演示/bench/checklist/受控降级路径。"""

import json

import pytest

from structural_strengthening_checker.cli import main


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "selfcheck" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["--version"])
    assert ei.value.code == 0
    assert "ssc" in capsys.readouterr().out


def test_selfcheck_green_on_repo_data(repo_cwd, capsys):
    code = main(["selfcheck"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "SELFCHECK_OK" in out
    assert "验算模块: 4 个" in out


def test_modules_lists_four(repo_cwd, capsys):
    assert main(["modules"]) == 0
    out = capsys.readouterr().out
    for module_id in (
        "cfrp_beam_flexure",
        "steel_plate_flexure",
        "section_enlarge_flexure",
        "post_rebar_anchor",
    ):
        assert module_id in out
        # M1 数据先行：所需条款全部已核对 → READY（计算体仍为 M2 stub）
        assert "[READY]" in out


def _write_params(tmp_path, module_id, params):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    return path


def test_calc_repo_data_computes_exit0(repo_cwd, tmp_path, capsys):
    """M2 计算体实装：仓库条款已核对 → 门控放行 → 输出结论行 + CalcResult JSON，exit 0。"""
    params_path = _write_params(tmp_path, "cfrp_beam_flexure", VALID_CFRP_PARAMS)
    code = main(["calc", "cfrp_beam_flexure", "--input", str(params_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "验算结论: [满足]" in out
    assert '"verdict": "满足"' in out
    assert '"Mu_kNm"' in out


def test_calc_three_states_demo(repo_cwd, tmp_path, capsys):
    """M2 DoD：CLI 演示 满足/需调整/不满足 三态。"""
    cases = {
        "满足": VALID_CFRP_PARAMS,  # CF-001-P 口径：Mu=244 > M=180
        "需调整": dict(VALID_CFRP_PARAMS, M=260.0, Afe=50.0),  # CF-003-R 口径：Mu=230 < 260
        "不满足": dict(VALID_CFRP_PARAMS, M=350.0),  # x_M 超出 0.85·ξb·h0 → 方法不可行
    }
    for verdict, params in cases.items():
        params_path = _write_params(tmp_path, "cfrp_beam_flexure", params)
        code = main(["calc", "cfrp_beam_flexure", "--input", str(params_path)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert f"验算结论: [{verdict}]" in out, verdict


def test_calc_gate_demo_exit3(repo_cwd, tmp_path, capsys):
    """门控演示：临时数据目录注入待核对条款 → exit 3 + 指向核对流程的消息。"""
    data_dir = tmp_path / "data"
    clauses_dir = data_dir / "knowledge" / "clauses"
    clauses_dir.mkdir(parents=True)
    from structural_strengthening_checker.core.engine import CALC_REGISTRY

    clauses = [
        {
            "clause_id": cid,
            "standard": "GB 0000-0000",
            "clause_no": "0.0.0",
            "title": "t",
            "gist": "g",
            "status": "待核对",
            "source": {"channel": None, "checked_date": None},
        }
        for cid in CALC_REGISTRY["cfrp_beam_flexure"].required_clauses
    ]
    (clauses_dir / "c.json").write_text(
        json.dumps(clauses, ensure_ascii=False), encoding="utf-8"
    )
    params_path = _write_params(tmp_path, "cfrp_beam_flexure", VALID_CFRP_PARAMS)
    code = main(
        [
            "--data-dir", str(data_dir),
            "calc", "cfrp_beam_flexure", "--input", str(params_path),
        ]
    )
    out = capsys.readouterr().out
    assert code == 3, out
    assert "条款门控" in out
    assert "plan/05" in out


def test_calc_unknown_module_exit1(repo_cwd, tmp_path, capsys):
    params_path = _write_params(tmp_path, "x", {})
    code = main(["calc", "no_such_module", "--input", str(params_path)])
    assert code == 1
    assert "未注册" in capsys.readouterr().out


def test_calc_bad_json_exit2(repo_cwd, tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    code = main(["calc", "cfrp_beam_flexure", "--input", str(bad)])
    assert code == 2
    assert "JSON" in capsys.readouterr().out


def test_calc_missing_file_exit2(repo_cwd, tmp_path, capsys):
    code = main(["calc", "cfrp_beam_flexure", "--input", str(tmp_path / "nope.json")])
    assert code == 2
    assert "无法读取" in capsys.readouterr().out


def test_bench_passes_all_m2_cases(repo_cwd, capsys):
    code = main(["bench"])
    out = capsys.readouterr().out
    assert code == 0, out
    # M2 回填后 14 例（5 植筋 + 9 受弯）全部通过（±0.5% 容差 + verdict 严格相等）
    assert '"total": 14' in out
    assert '"passed": 14' in out
    assert '"failed": 0' in out
    assert '"blocked_by_clauses": 0' in out


def test_checklist_lists_items(repo_cwd, capsys):
    code = main(["checklist"])
    out = capsys.readouterr().out
    assert code == 0, out
    # M1 按原文回填真实条号（GB 55021-2021）
    assert "GB55021-1.0.3" in out


def test_check_missing_extra_or_planned(repo_cwd, tmp_path, capsys):
    """未装 parse extras（或已装但 M3 未实装）都不得 traceback。"""
    fake = tmp_path / "plan.txt"
    fake.write_text("x", encoding="utf-8")
    code = main(["check", str(fake)])
    out = capsys.readouterr().out
    assert code in (0, 2)
    assert ("缺少依赖" in out) or ("M3" in out) or ("不支持" in out)


VALID_CFRP_PARAMS = {
    "b": 250.0,
    "h": 500.0,
    "fc": 14.3,
    "As": 1520.0,
    "fy": 360.0,
    "Afe": 101.0,
    "Ecf": 240000.0,
    "M0": 0.0,
    "M": 180.0,
    "ff": 2300.0,
    "ef": 0.01,
    "as": 35.0,
    "xi_b": 0.518,
    "Es": 200000.0,
}
