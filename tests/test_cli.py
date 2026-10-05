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
        assert "[GATED]" in out  # 骨架期全部未就绪（条文待核对）


def _write_params(tmp_path, module_id, params):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(params, ensure_ascii=False), encoding="utf-8")
    return path


def test_calc_gate_demo_exit3(repo_cwd, tmp_path, capsys):
    """门控演示：条文未核对 → exit 3 + 指向核对流程的消息。"""
    params_path = _write_params(tmp_path, "cfrp_beam_flexure", VALID_CFRP_PARAMS)
    code = main(["calc", "cfrp_beam_flexure", "--input", str(params_path)])
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


def test_bench_reports_empty_honestly(repo_cwd, capsys):
    code = main(["bench"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert '"total": 0' in out  # 算例库 M1 填充，骨架期如实报 0


def test_checklist_lists_items(repo_cwd, capsys):
    code = main(["checklist"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "GB55021-APPRAISAL-FIRST" in out


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
}
