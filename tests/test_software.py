"""軟體領域（第二期）：能力規格、規格差異、change 資料夾、任務與測試規劃、check 整合。"""

from __future__ import annotations

import json

import pytest

from dspx.check import run_check
from dspx.commands.code import code as code_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.schema import load_schema
from dspx.engine.software import changes as chg
from dspx.engine.software import delta as dl
from dspx.engine.software import io
from dspx.engine.software import specs as sp

RB = ["--read-back", "覆述內容", "--confirmed", "對"]


def _entry_spec() -> dict:
    return {
        "capability": "task-entry-page",
        "purpose": "任務入口頁",
        "requirements": [
            {"id": "R1", "title": "入口頁列出任務", "statement": "The page SHALL list every task.",
             "verification": ["test"],
             "scenarios": [
                 {"id": "S1", "title": "第一列可見", "when": "開啟頁面", "then": "看到第一列"},
                 {"id": "S2", "title": "空清單", "when": "沒有任務", "then": "顯示提示"}]},
            {"id": "R2", "title": "版面", "statement": "The layout MUST fit 1280px.",
             "verification": ["inspection"],
             "scenarios": [{"id": "S1", "title": "寬度", "when": "1280 寬", "then": "無水平捲動"}]},
        ],
    }


@pytest.fixture
def sw(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    layout = Layout(home)
    sp.write_spec(layout, _entry_spec())
    return layout


def code(*argv) -> int:
    return code_cmd.run(list(argv))


# ── 規格 ─────────────────────────────────────────────────────────────────

def test_spec_list_and_show_one_requirement(sw, capsys):
    assert code("spec", "list") == 0
    assert "task-entry-page — 2 requirement(s)" in capsys.readouterr().out
    assert code("spec", "show", "task-entry-page", "--req", "R2", "--json") == 0
    out = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in out["requirements"]] == ["R2"]
    assert code("spec", "show", "task-entry-page") == 0
    md = capsys.readouterr().out
    assert "### R1 入口頁列出任務" in md and "**WHEN** 開啟頁面" in md
    assert code("spec", "show", "nope") == 1


def test_spec_validation_rules():
    bad = {"capability": "x", "purpose": "p", "requirements": [
        {"id": "R1", "title": "t", "statement": "should list", "verification": ["vibes"],
         "scenarios": []}]}
    errs = sp.validate_spec(bad)
    assert any("SHALL or MUST" in e for e in errs)
    assert any("verification \"vibes\"" in e for e in errs)
    assert any("at least one scenario" in e for e in errs)
    assert sp.validate_spec(_entry_spec()) == []


def test_spec_hand_edit_breaks_seal(sw):
    p = io.spec_path(sw, "task-entry-page")
    p.write_text(p.read_text(encoding="utf-8").replace("第一列可見", "改掉"), encoding="utf-8")
    with pytest.raises(io.SoftwareError, match="integrity seal mismatch"):
        sp.load_spec(sw, "task-entry-page")


def test_split_ref_handles_nested_capability_names():
    assert sp.split_ref("req:ui/entry/R3/S2") == ("ui/entry", "R3", "S2")
    assert sp.split_ref("ui/entry/R3") == ("ui/entry", "R3", None)


# ── 差異：只寫改到的部分；基準指紋 ───────────────────────────────────────

def test_modify_scenario_only_touches_that_scenario():
    spec = _entry_spec()
    cd = {"capability": "task-entry-page", "new": False, "deltas": []}
    d = dl.prepare(spec, cd, {"op": "modify-scenario", "ref": "R1/S1", "then": "第一列完整可見"})
    assert d["base"] == sp.scenario_fp(spec["requirements"][0]["scenarios"][0])
    cd["deltas"].append(d)
    new, conflicts, _ = dl.apply(spec, cd)
    assert not conflicts
    s1, s2 = new["requirements"][0]["scenarios"]
    assert s1["then"] == "第一列完整可見" and s1["when"] == "開啟頁面"
    assert s2 == spec["requirements"][0]["scenarios"][1]


def test_parallel_changes_on_different_scenarios_do_not_conflict_but_same_one_does():
    spec = _entry_spec()
    a = {"capability": "task-entry-page", "deltas": [
        dl.prepare(spec, {"deltas": []}, {"op": "modify-scenario", "ref": "R1/S1", "then": "A"})]}
    b = {"capability": "task-entry-page", "deltas": [
        dl.prepare(spec, {"deltas": []}, {"op": "modify-scenario", "ref": "R1/S2", "then": "B"})]}
    c = {"capability": "task-entry-page", "deltas": [
        dl.prepare(spec, {"deltas": []}, {"op": "modify-scenario", "ref": "R1/S1", "then": "C"})]}
    after_a, conf, _ = dl.apply(spec, a)
    assert not conf
    assert not dl.apply(after_a, b)[1]
    conf = dl.apply(after_a, c)[1]
    assert conf and "changed since this delta was written" in conf[0]


def test_head_change_and_scenario_change_are_independent():
    spec = _entry_spec()
    head = {"capability": "task-entry-page", "deltas": [
        dl.prepare(spec, {"deltas": []}, {"op": "modify-requirement", "ref": "R1",
                                          "statement": "The page SHALL list all open tasks."})]}
    scn = {"capability": "task-entry-page", "deltas": [
        dl.prepare(spec, {"deltas": []}, {"op": "modify-scenario", "ref": "R1/S2", "then": "x"})]}
    after, conf, _ = dl.apply(spec, scn)
    assert not conf
    assert not dl.apply(after, head)[1]


def test_removed_ids_are_never_reused_and_added_ids_renumber_on_collision():
    spec = _entry_spec()
    rm = {"capability": "task-entry-page", "deltas": [
        dl.prepare(spec, {"deltas": []}, {"op": "remove-requirement", "ref": "R2", "reason": "併入 R1"})]}
    after, conf, _ = dl.apply(spec, rm)
    assert not conf and after["retired"] == {"requirements": ["R2"]}
    add = dl.prepare(after, {"deltas": []}, {
        "op": "add-requirement", "title": "排序", "statement": "Tasks SHALL be sorted.",
        "verification": "test", "scenarios": [{"title": "t", "when": "w", "then": "th"}]})
    assert add["id"] == "R3"                      # R2 已退役，不重用
    # 另一個 change 在 R3 被占用前寫好的新增 → 封存時自動改配
    stale = {"capability": "task-entry-page", "deltas": [dict(add)]}
    after2, _, _ = dl.apply(after, stale)
    after3, conf, renames = dl.apply(after2, stale)
    assert not conf and renames == {"task-entry-page/R3": "task-entry-page/R4"}
    assert [r["id"] for r in after3["requirements"]] == ["R1", "R3", "R4"]


def test_delta_rejects_bad_input():
    spec = _entry_spec()
    with pytest.raises(io.SoftwareError, match="not found"):
        dl.prepare(spec, {"deltas": []}, {"op": "modify-scenario", "ref": "R9/S1", "then": "x"})
    with pytest.raises(io.SoftwareError, match="unknown field"):
        dl.prepare(spec, {"deltas": []}, {"op": "remove-requirement", "ref": "R1", "reason": "r",
                                          "then": "x"})
    with pytest.raises(io.SoftwareError, match="needs --reason"):
        dl.prepare(spec, {"deltas": []}, {"op": "remove-scenario", "ref": "R1/S1"})
    with pytest.raises(io.SoftwareError, match="new capability only takes"):
        dl.prepare(None, {"new": True, "deltas": []}, {"op": "modify-requirement", "ref": "R1",
                                                        "title": "x"})


# ── change 資料夾（全部透過指令）───────────────────────────────────────

def _decision(layout) -> str:
    ruling_cmd.run(["add", "--quote", "第一列必須完整可見", *RB])
    decision_cmd.run(["add", "--title", "入口頁", "--statement", "第一列完整可見",
                      "--based-on", "RL-claude-1"])
    return "D-claude-1"


def test_change_folder_is_created_by_commands(sw, capsys):
    assert code("change", "new", "entry-fix", "--why", "第一列被遮住", "--what", "修正版面",
                "--modified", "task-entry-page") == 0
    folder = io.change_dir(sw, "entry-fix")
    assert sorted(p.name for p in folder.iterdir()) == [
        "design.yaml", "proposal.yaml", "tasks.yaml", "tests.yaml"]
    assert code("change", "delta", "entry-fix", "--capability", "task-entry-page",
                "--op", "modify-scenario", "--ref", "R1/S1", "--then", "第一列完整可見") == 0
    assert (folder / "specs" / "task-entry-page.yaml").is_file()
    # 現行規格沒動
    assert sp.load_spec(sw, "task-entry-page") == _entry_spec()
    assert code("change", "show", "entry-fix") == 0
    md = capsys.readouterr().out
    assert "**modify-scenario** R1/S1" in md and "## Tasks" in md


def test_change_new_validates_capabilities_and_id(sw, capsys):
    assert code("change", "new", "Bad_ID", "--why", "x") == 1
    assert code("change", "new", "a", "--why", "x", "--new", "task-entry-page") == 1
    assert code("change", "new", "b", "--why", "x", "--modified", "nope") == 1
    assert code("change", "new", "c", "--why", "x") == 0
    assert code("change", "new", "c", "--why", "x") == 1
    assert "already exists" in capsys.readouterr().err


def test_delta_for_unlisted_capability_is_refused(sw, capsys):
    code("change", "new", "c", "--why", "x")
    assert code("change", "delta", "c", "--capability", "task-entry-page", "--op",
                "modify-scenario", "--ref", "R1/S1", "--then", "y") == 1
    assert "not listed in this change's proposal" in capsys.readouterr().err


def test_new_capability_via_from_file(sw, tmp_path):
    code("change", "new", "lib", "--why", "資料庫", "--new", "dataset-library")
    f = tmp_path / "d.yaml"
    f.write_text("""
capability: dataset-library
purpose: 管理資料集
deltas:
  - op: add-requirement
    title: 列出資料集
    statement: The library SHALL list datasets.
    verification: [test]
    scenarios:
      - {title: 有資料, when: 開啟, then: 列出}
      - {title: 無資料, when: 開啟, then: 提示}
""", encoding="utf-8")
    assert code("change", "delta", "lib", "--from", str(f)) == 0
    ch = chg.load_change(sw, "lib")
    d = ch["deltas"]["dataset-library"]
    assert d["new"] is True and d["purpose"] == "管理資料集"
    assert [s["id"] for s in d["deltas"][0]["scenarios"]] == ["S1", "S2"]
    preview, conflicts, _ = chg.preview_specs(sw, ch)
    assert not conflicts and preview["dataset-library"]["requirements"][0]["id"] == "R1"


def test_parallel_active_changes_reserve_requirement_ids(sw):
    for cid in ("a", "b"):
        code("change", "new", cid, "--why", "x", "--modified", "task-entry-page")
        code("change", "delta", cid, "--capability", "task-entry-page", "--op", "add-requirement",
             "--title", "t", "--statement", "It SHALL work.", "--verification", "test",
             "--scenario", "s | w | t")
    ids = [chg.load_change(sw, c)["deltas"]["task-entry-page"]["deltas"][0]["id"] for c in ("a", "b")]
    assert ids == ["R3", "R4"]


# ── 引用檢查：任務、測試規劃、決策 ─────────────────────────────────────

def _status(capsys, cid="entry-fix"):
    rc = code("change", "status", cid, "--json")
    return rc, json.loads(capsys.readouterr().out)


def test_status_requires_tasks_and_test_coverage(sw, capsys):
    code("change", "new", "entry-fix", "--why", "x", "--modified", "task-entry-page")
    code("change", "delta", "entry-fix", "--capability", "task-entry-page", "--op",
         "modify-scenario", "--ref", "R1/S1", "--then", "完整可見")
    capsys.readouterr()
    rc, out = _status(capsys)
    assert rc == 1
    assert any("no task implements it" in e for e in out["errors"])
    assert any("no planned test covers it" in e for e in out["errors"])

    assert code("testplan", "add", "entry-fix", "--location", "tests/test_entry.py::test_first_row",
                "--covers", "task-entry-page/R1/S1") == 0
    assert code("task", "add", "entry-fix", "--title", "修版面", "--implements", "task-entry-page/R1",
                "--files", "src/entry.py", "--verify", "test", "--tests", "T1") == 0
    capsys.readouterr()
    rc, out = _status(capsys)
    assert rc == 0, out["errors"]
    assert out["tasks"] == {"not-started": 1}
    tasks = chg.load_change(sw, "entry-fix")["tasks"]["tasks"]
    assert tasks[0]["status"] == "not-started"          # 完成欄位存在，由引擎寫


def test_non_test_verification_needs_a_matching_task(sw, capsys):
    code("change", "new", "layout", "--why", "x", "--modified", "task-entry-page")
    code("change", "delta", "layout", "--capability", "task-entry-page", "--op",
         "modify-requirement", "--ref", "R2", "--statement", "The layout MUST fit 1024px.")
    code("task", "add", "layout", "--title", "改寬度", "--implements", "task-entry-page/R2",
         "--verify", "test", "--tests", "T9")
    capsys.readouterr()
    rc, out = _status(capsys, "layout")
    assert any("verified by inspection but no implementing task" in e for e in out["errors"])
    assert any("unplanned test \"T9\"" in e for e in out["errors"])


def test_task_rules_repo_and_test_file_warning(sw, capsys):
    io.config_path(sw).write_text("repos:\n  labelvault: tools/labelvault\n", encoding="utf-8")
    code("change", "new", "entry-fix", "--why", "x", "--modified", "task-entry-page")
    code("change", "delta", "entry-fix", "--capability", "task-entry-page", "--op",
         "modify-scenario", "--ref", "R1/S1", "--then", "y")
    code("testplan", "add", "entry-fix", "--location", "labelvault:tests/test_e.py::test_a",
         "--covers", "task-entry-page/R1/S1")
    code("task", "add", "entry-fix", "--title", "a", "--implements", "task-entry-page/R1",
         "--files", "labelvault:tests/test_e.py,other:src/x.py", "--verify", "test", "--tests", "T1",
         "--depends-on", "2")
    code("task", "add", "entry-fix", "--title", "b", "--verify", "inspection", "--depends-on", "1")
    capsys.readouterr()
    _rc, out = _status(capsys)
    assert any("unregistered repo \"other\"" in e for e in out["errors"])
    assert any("dependency cycle" in e for e in out["errors"])
    assert any("tests belong to the test role" in e for e in out["errors"])


def test_decision_references_must_be_active(sw, capsys):
    did = _decision(sw)
    code("change", "new", "entry-fix", "--why", "x", "--modified", "task-entry-page")
    code("change", "design", "entry-fix", "--decision", did, "--goal", "第一列可見")
    code("change", "delta", "entry-fix", "--capability", "task-entry-page", "--op",
         "modify-requirement", "--ref", "R1", "--based-on", did, "--title", "列出任務")
    capsys.readouterr()
    _rc, out = _status(capsys)
    assert any("draft decision" in w for w in out["warnings"])
    decision_cmd.run(["activate", did])
    decision_cmd.run(["withdraw", did])
    capsys.readouterr()
    _rc, out = _status(capsys)
    assert any("withdrawn decision" in e for e in out["errors"])
    ch = chg.load_change(sw, "entry-fix")
    assert chg.validate_change(sw, ch, strict=True)[0]


def test_stale_base_is_reported_when_spec_moves(sw, capsys):
    code("change", "new", "entry-fix", "--why", "x", "--modified", "task-entry-page")
    code("change", "delta", "entry-fix", "--capability", "task-entry-page", "--op",
         "modify-scenario", "--ref", "R1/S1", "--then", "y")
    spec = _entry_spec()
    spec["requirements"][0]["scenarios"][0]["then"] = "別的 change 已封存"
    sp.write_spec(sw, spec)
    ch = chg.load_change(sw, "entry-fix")
    _e, warns = chg.validate_change(sw, ch)
    assert any("changed since this delta was written" in w for w in warns)
    errs, _w = chg.validate_change(sw, ch, strict=True)
    assert any("changed since this delta was written" in e for e in errs)


def test_objection_round_trip_requires_a_different_agent(sw, monkeypatch, capsys):
    code("change", "new", "entry-fix", "--why", "x", "--modified", "task-entry-page")
    code("testplan", "add", "entry-fix", "--location", "tests/t.py::a",
         "--covers", "task-entry-page/R1/S1")
    monkeypatch.setenv("DOCSPEC_AGENT", "gpt")          # 實作者
    assert code("testplan", "object", "entry-fix", "T1", "--reason", "THEN 讀錯") == 0
    assert code("testplan", "respond", "entry-fix", "O1", "--resolution", "rejected",
                "--reason", "x") == 1
    assert "different agent" in capsys.readouterr().err
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")       # 測試角色
    assert code("testplan", "respond", "entry-fix", "O1", "--resolution", "test-fixed",
                "--reason", "已改斷言") == 0
    o = chg.load_change(sw, "entry-fix")["tests"]["objections"][0]
    assert o["resolution"] == "test-fixed" and o["responded-by"] == "claude" and o["by"] == "gpt"


def test_check_reports_software_errors(sw):
    code("change", "new", "entry-fix", "--why", "x", "--modified", "task-entry-page")
    code("change", "delta", "entry-fix", "--capability", "task-entry-page", "--op",
         "modify-scenario", "--ref", "R1/S1", "--then", "y")
    res = run_check(load_project(sw), load_schema(), sw)
    # 2026/09/30 裁定：文件管文件、軟體管軟體——軟體錯誤另列，不讓文件的 check 變紅。
    assert res.ok
    assert any("no task implements it" in e for e in res.software_errors)


def test_size_warning(sw, capsys):
    io.config_path(sw).write_text("change-size-warning: {tasks: 1}\n", encoding="utf-8")
    code("change", "new", "big", "--why", "x")
    code("task", "add", "big", "--title", "a", "--verify", "inspection")
    code("task", "add", "big", "--title", "b", "--verify", "inspection")
    capsys.readouterr()
    _rc, out = _status(capsys, "big")
    assert any("large change" in w for w in out["warnings"])


def test_task_and_testplan_remove_guards(sw, capsys):
    code("change", "new", "c", "--why", "x", "--modified", "task-entry-page")
    code("testplan", "add", "c", "--location", "tests/t.py::a", "--covers", "task-entry-page/R1/S1")
    code("task", "add", "c", "--title", "a", "--verify", "test", "--tests", "T1")
    code("task", "add", "c", "--title", "b", "--verify", "inspection", "--depends-on", "1")
    assert code("testplan", "remove", "c", "T1") == 1          # 任務 1 用到
    assert code("task", "remove", "c", "1") == 1                # 任務 2 依賴它
    assert code("task", "remove", "c", "2") == 0
    assert code("task", "remove", "c", "1") == 0
    assert code("testplan", "remove", "c", "T1") == 0
    ch = chg.load_change(sw, "c")
    assert ch["tasks"]["tasks"] == [] and ch["tests"]["tests"] == []
