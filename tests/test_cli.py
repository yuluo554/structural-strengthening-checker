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


# ---------------------------------------------------------------------------
# M3：ssc check 端到端（合成方案语料对账）+ ssc checklist 核对流
# ---------------------------------------------------------------------------

def test_check_end_to_end_corpus_reconciliation(repo_cwd, tmp_path, capsys):
    """M3 DoD：生成器语料端到端——报告非 pass 集合 == truth.expected_non_pass（误报 0 口径）。"""
    from structural_strengthening_checker.datagen import gen_plan

    out = tmp_path / "corpus"
    truth = gen_plan.generate(out, seed=20261005, count=5)
    for doc in truth["docs"]:
        code = main(["check", "--json", str(out / doc["doc_name"])])
        report = json.loads(capsys.readouterr().out)
        assert code == 0, doc["doc_name"]
        # 真值语义为"集合对账"（plan/05 §四）：比较与顺序无关
        assert sorted(report["non_pass_rule_ids"]) == sorted(doc["expected_non_pass"]), doc["doc_name"]
        assert report["disclaimer"], doc["doc_name"]
    # 基线显式断言：4 条规则全 pass
    code = main(["check", "--json", str(out / "baseline_seed20261005.docx")])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["summary"] == {"fail": 0, "suspicious": 0, "needs_confirm": 0, "pass": 4}


def test_check_report_flag_writes_json(repo_cwd, tmp_path, capsys):
    from structural_strengthening_checker.datagen import gen_plan

    out = tmp_path / "corpus"
    gen_plan.generate(out, seed=20261005, count=1)
    report_dir = tmp_path / "report"
    code = main(["check", str(out / "case01_seed20261005.docx"), "--report", str(report_dir)])
    assert code == 0
    data = json.loads((report_dir / "check_report.json").read_text(encoding="utf-8"))
    assert data["non_pass_rule_ids"] == ["R-ADH-001"]


def test_check_corrupt_docx_degrades_no_fail(repo_cwd, tmp_path, capsys):
    bad = tmp_path / "损坏方案.docx"
    bad.write_bytes(b"PK\x03\x04 garbage not zip")
    code = main(["check", str(bad)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "解析失败" in out
    assert "不符合 0" in out
    assert "待人工确认 4" in out  # 全部规则降级 needs_confirm


def test_check_chinese_filename(repo_cwd, tmp_path, capsys):
    from structural_strengthening_checker.datagen import gen_plan

    out = tmp_path / "corpus"
    gen_plan.generate(out, seed=20261005, count=1)
    dst = tmp_path / "加固方案_中文文件名.docx"
    dst.write_bytes((out / "baseline_seed20261005.docx").read_bytes())
    code = main(["check", str(dst)])
    out_txt = capsys.readouterr().out
    assert code == 0, out_txt
    assert "不符合 0" in out_txt


def test_check_missing_plan_file_friendly(repo_cwd, tmp_path, capsys):
    """文件不存在=输入错误（exit 2 友好提示），不是解析失败降级路径。"""
    code = main(["check", str(tmp_path / "不存在.docx")])
    out = capsys.readouterr().out
    assert code == 2
    assert "无法读取" in out


def _write_answers(tmp_path, answers):
    path = tmp_path / "answers.json"
    path.write_text(json.dumps(answers, ensure_ascii=False), encoding="utf-8")
    return path


def test_checklist_doc_suggestions_and_out(repo_cwd, tmp_path, capsys):
    from structural_strengthening_checker.datagen import gen_plan

    out = tmp_path / "corpus"
    gen_plan.generate(out, seed=20261005, count=1)
    answers_path = tmp_path / "suggest.json"
    code = main(["checklist", "--doc", str(out / "baseline_seed20261005.docx"),
                 "--out", str(answers_path)])
    out_txt = capsys.readouterr().out
    assert code == 0, out_txt
    assert "建议 符合" in out_txt  # auto_text 条目检出关键词
    data = json.loads(answers_path.read_text(encoding="utf-8"))
    assert len(data) == 11
    assert data["GB55021-6.1.5"]["choice"] == "符合"


def test_checklist_fill_renders_summary(repo_cwd, tmp_path, capsys):
    answers = {
        "GB55021-1.0.3": {"choice": "符合", "note": "鉴定报告 JD-2026-088"},
        "GB55021-6.1.5": {"choice": "不符合", "note": "未写卸载"},
    }
    path = _write_answers(tmp_path, answers)
    code = main(["checklist", "--fill", str(path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "[符合] GB55021-1.0.3" in out
    assert "[不符合] GB55021-6.1.5" in out
    assert "备注: 未写卸载" in out


def test_checklist_fill_invalid_choice_flagged(repo_cwd, tmp_path, capsys):
    path = _write_answers(tmp_path, {"GB55021-1.0.3": {"choice": "差不多"}})
    code = main(["checklist", "--fill", str(path)])
    out = capsys.readouterr().out
    assert code == 0  # 渲染层标注非法选项，不中断
    assert "非法选项" in out


def test_checklist_fill_bad_file_exit(repo_cwd, tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["checklist", "--fill", str(bad)]) == 1


def test_checklist_interactive_flow(repo_cwd, tmp_path, capsys, monkeypatch):
    import io

    from structural_strengthening_checker.datagen import gen_plan

    out = tmp_path / "corpus"
    gen_plan.generate(out, seed=20261005, count=1)
    # 依次输入：1（符合）+备注 / s 跳过 / 4（待确认）+空备注 / q 结束
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n依据鉴定报告\ns\n4\n\nq\n"))
    answers_path = tmp_path / "filled.json"
    code = main(["checklist", "--interactive", "--out", str(answers_path)])
    out_txt = capsys.readouterr().out
    assert code == 0, out_txt
    data = json.loads(answers_path.read_text(encoding="utf-8"))
    assert data["GB55021-1.0.3"] == {"choice": "符合", "note": "依据鉴定报告"}
    assert "GB55021-2.0.2" not in data  # s 跳过
    assert data["GB55021-2.0.3"] == {"choice": "待确认", "note": ""}
    assert len(data) == 2  # q 提前结束
    assert "待确认" in out_txt
