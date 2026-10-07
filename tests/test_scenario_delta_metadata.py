"""Own additions must obey the same delta schema as baseline modifications.

These cases exercise the CLI, sealed persistence, semantic sign-off scope, and
an actual engine test run/archive. No migration or new delta metadata is assumed.
"""

from __future__ import annotations

import json
import shlex
import sys

import pytest

from dspx.commands.code import code as code_cmd
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg, evidence as ev, io, scope, specs as sp
from dspx.engine.software import validate_all


SCENARIO_MODES = ("new-inline", "existing-inline", "new-added-scenario",
                  "existing-added-scenario", "baseline-scenario")


def code(*args):
    return code_cmd.run(list(args))


def managed_bytes(layout):
    return {p.relative_to(layout.planning_home).as_posix(): p.read_bytes()
            for p in layout.planning_home.rglob("*") if p.is_file()}


@pytest.fixture
def project(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    monkeypatch.delenv("DOCSPEC_ACTOR_ID", raising=False)
    layout = Layout(home)
    app = layout.project_root / "app"
    app.mkdir()
    (app / "labels.py").write_text("def format_label(value):\n    return value.strip().upper()\n", encoding="utf-8")
    (app / "test_labels.py").write_text(
        "from labels import format_label\n\ndef test_labels():\n"
        "    assert format_label(' north ') == 'NORTH'\n"
        "    assert format_label('south') == 'SOUTH'\n", encoding="utf-8")
    runner = shlex.join([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    io.config_path(layout).parent.mkdir(parents=True, exist_ok=True)
    io.config_path(layout).write_text(
        "repos:\n  app:\n    path: app\n    test-command: " + json.dumps(runner) + "\n",
        encoding="utf-8")
    sp.write_spec(layout, {"capability": "entry", "purpose": "Format labels", "requirements": [
        {"id": "R1", "title": "Format a label", "statement": "The service SHALL format labels in uppercase.",
         "verification": ["test"], "scenarios": [
             {"id": "S1", "title": "North label", "when": "input north", "then": "output NORTH"}]}]})
    return layout


def setup_change(layout, mode):
    cap = "new-entry" if mode.startswith("new-") else "entry"
    flag = "--new" if mode.startswith("new-") else "--modified"
    assert code("change", "new", "metadata", "--why", "Clarify the label behavior", flag, cap) == 0
    if mode in ("new-inline", "existing-inline", "new-added-scenario"):
        assert code("change", "delta", "metadata", "--capability", cap, "--purpose", "Format labels",
                    "--op", "add-requirement", "--title", "Format a label",
                    "--statement", "The service SHALL format labels in uppercase.", "--verification", "test",
                    "--scenario", "North label | input north | output NORTH") == 0
    rid = "R2" if mode == "existing-inline" else "R1"
    sid = "S1"
    if mode.endswith("added-scenario"):
        assert code("change", "delta", "metadata", "--capability", cap, "--op", "add-scenario",
                    "--ref", rid, "--title", "South label", "--when", "input south", "--then", "output SOUTH") == 0
        sid = "S2"
    if mode == "baseline-scenario":
        assert code("change", "delta", "metadata", "--capability", cap, "--op", "modify-scenario",
                    "--ref", "R1/S1", "--title", "Clarified north label") == 0
    assert code("task", "add", "metadata", "--title", "Format the labels", "--implements", f"{cap}/{rid}",
                "--files", "app:labels.py", "--verify", "test", "--tests", "T1") == 0
    covers = f"{cap}/{rid}/{sid}"
    if mode == "new-added-scenario":
        covers = f"{cap}/{rid}/S1,{cap}/{rid}/S2"
    assert code("testplan", "add", "metadata", "--location", "app:test_labels.py::test_labels",
                "--covers", covers, "--by", "gemini") == 0
    assert code("testplan", "sign", "metadata", "--by", "gemini") == 0
    return cap, rid, sid


def change_and_scenario(layout, cap, rid, sid):
    change = chg.load_change(layout, "metadata")
    preview, conflicts, _ = chg.preview_specs(layout, change)
    assert conflicts == []
    return change, sp.find_scenario(sp.find_requirement(preview[cap], rid), sid)


@pytest.mark.parametrize("mode", SCENARIO_MODES)
@pytest.mark.parametrize("wrong_field", [("--reason", "Explain the clarification"),
                                          ("--verification", "inspection"),
                                          ("--statement", "The service SHALL change its rule.")])
def test_cli_rejects_inappropriate_scenario_fields_without_changing_sealed_records(project, mode, wrong_field):
    cap, rid, sid = setup_change(project, mode)
    original = managed_bytes(project)
    change = chg.load_change(project, "metadata")
    saved_scope = scope.task_scope(project, change, change["tasks"]["tasks"][0])
    assert code("change", "delta", "metadata", "--capability", cap, "--op", "modify-scenario",
                "--ref", f"{rid}/{sid}", "--title", "Still only a scenario title", *wrong_field) == 1
    assert managed_bytes(project) == original
    change = chg.load_change(project, "metadata")
    assert scope.task_scope(project, change, change["tasks"]["tasks"][0]) == saved_scope
    assert ev.signoff_problems(project, change["tests"]["tests"], change) == []


@pytest.mark.parametrize("mode", ("new-inline", "existing-inline"))
@pytest.mark.parametrize("op", ("modify-requirement", "rename-requirement"))
@pytest.mark.parametrize("wrong_field", [("--reason", "Explain the clarification"),
                                          ("--when", "a field for scenarios")])
def test_cli_rejects_inappropriate_requirement_fields_before_own_addition_write(project, mode, op, wrong_field):
    cap, rid, _ = setup_change(project, mode)
    original = managed_bytes(project)
    assert code("change", "delta", "metadata", "--capability", cap, "--op", op,
                "--ref", rid, "--title", "A clarified requirement", *wrong_field) == 1
    assert managed_bytes(project) == original
    assert chg.load_change(project, "metadata")["deltas"][cap]["deltas"][0]["id"] == rid


@pytest.mark.parametrize("mode", SCENARIO_MODES)
def test_engine_rejects_unknown_field_before_writing_or_resealing(project, mode):
    cap, rid, sid = setup_change(project, mode)
    original = managed_bytes(project)
    with pytest.raises(io.SoftwareError, match="unknown field"):
        chg.add_delta(project, "metadata", cap,
                      {"op": "modify-scenario", "ref": f"{rid}/{sid}", "title": "Clarified", "unrecognized": "bad"})
    assert managed_bytes(project) == original
    chg.load_change(project, "metadata")  # Existing seals must still verify.


@pytest.mark.parametrize("mode", SCENARIO_MODES[:-1])
def test_own_scenario_edits_never_overwrite_assigned_id_from_raw_metadata(project, mode):
    cap, rid, sid = setup_change(project, mode)
    chg.add_delta(project, "metadata", cap,
                  {"op": "modify-scenario", "ref": f"{rid}/{sid}", "title": "Clarified label", "id": "S99"})
    change, scenario = change_and_scenario(project, cap, rid, sid)
    assert scenario is not None and scenario["id"] == sid and scenario["title"] == "Clarified label"
    assert not any(s.get("id") == "S99" for delta in change["deltas"][cap]["deltas"]
                   for s in delta.get("scenarios", []))


@pytest.mark.parametrize("mode", SCENARIO_MODES)
@pytest.mark.parametrize("metadata", ({"id": "S99"}, {"base": "untrusted-base"}))
def test_scenario_edit_with_only_metadata_is_rejected_without_touching_seals(project, mode, metadata):
    cap, rid, sid = setup_change(project, mode)
    original = managed_bytes(project)
    with pytest.raises(io.SoftwareError):
        chg.add_delta(project, "metadata", cap,
                      {"op": "modify-scenario", "ref": f"{rid}/{sid}", **metadata})
    assert managed_bytes(project) == original
    chg.load_change(project, "metadata")


@pytest.mark.parametrize("mode", ("new-inline", "existing-inline"))
@pytest.mark.parametrize("op", ("modify-requirement", "rename-requirement"))
def test_own_requirement_title_edit_does_not_replace_its_assigned_id(project, mode, op):
    cap, rid, sid = setup_change(project, mode)
    chg.add_delta(project, "metadata", cap,
                  {"op": op, "ref": rid, "title": "Clarified label requirement", "id": "R99"})
    change, scenario = change_and_scenario(project, cap, rid, sid)
    assert scenario is not None and scenario["id"] == sid
    added = next(d for d in change["deltas"][cap]["deltas"] if d["op"] == "add-requirement")
    assert added["id"] == rid and added["title"] == "Clarified label requirement"
    assert ev.signoff_problems(project, change["tests"]["tests"], change) == []


@pytest.mark.parametrize("mode", ("new-inline", "existing-inline"))
@pytest.mark.parametrize("field,value", [("title", "A clarified heading"),
                                          ("statement", "The service SHALL output canonical labels."),
                                          ("verification", "test,inspection")])
def test_valid_requirement_fields_remain_editable_and_validate(project, mode, field, value):
    cap, rid, sid = setup_change(project, mode)
    assert code("change", "delta", "metadata", "--capability", cap, "--op", "modify-requirement",
                "--ref", rid, "--" + field, value) == 0
    change, scenario = change_and_scenario(project, cap, rid, sid)
    assert scenario is not None
    added = next(d for d in change["deltas"][cap]["deltas"] if d["op"] == "add-requirement")
    assert added[field] == (value.split(",") if field == "verification" else value)
    assert set(added) <= {"op", *sp.REQ_FIELDS}


def test_cli_delta_reason_help_names_only_removal_operations(capsys):
    with pytest.raises(SystemExit) as exit_info:
        code_cmd._parser().parse_args(["change", "delta", "metadata", "--help"])
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    reason_help = output.split("--reason REASON", 2)[-1].split("--scenario", 1)[0]
    assert "remove-requirement" in reason_help and "remove-scenario" in reason_help


@pytest.mark.parametrize("mode", SCENARIO_MODES)
@pytest.mark.parametrize("field", ("title", "when", "then"))
def test_valid_scenario_edits_keep_or_expire_signoff_by_actual_semantic_scope(project, mode, field):
    cap, rid, sid = setup_change(project, mode)
    before, _ = change_and_scenario(project, cap, rid, sid)
    task = before["tasks"]["tasks"][0]
    saved = {"scope": scope.task_scope(project, before, task)}
    signed = before["tests"]["tests"][0]["signed"]
    if mode == "baseline-scenario":
        assert code("change", "undelta", "metadata", "--capability", cap, "--ref", f"{rid}/{sid}") == 0
    value = {"title": "A presentation-only label", "when": "input west", "then": "output WEST"}[field]
    assert code("change", "delta", "metadata", "--capability", cap, "--op", "modify-scenario",
                "--ref", f"{rid}/{sid}", f"--{field}", value) == 0
    after, scenario = change_and_scenario(project, cap, rid, sid)
    assert scenario[field] == value
    assert set(scenario) <= set(sp.SCN_FIELDS)
    assert after["tests"]["tests"][0]["signed"] == signed  # Queries/edits cannot auto-sign.
    problems = ev.signoff_problems(project, after["tests"]["tests"], after)
    explanation = ev.scope_problem(project, after, after["tasks"]["tasks"][0], saved)
    if field == "title":
        assert problems == []
        assert explanation is None
    else:
        assert problems and any("scenario" in problem for problem in problems)
        assert explanation and f"{cap}/{rid}/{sid}" in explanation


@pytest.mark.parametrize("mode", ("new-inline", "existing-inline", "existing-added-scenario"))
def test_valid_own_scenario_edits_validate_run_and_archive_without_illegal_fields(project, mode):
    cap, rid, sid = setup_change(project, mode)
    assert code("change", "delta", "metadata", "--capability", cap, "--op", "modify-scenario",
                "--ref", f"{rid}/{sid}", "--title", "Clarified label behavior") == 0
    change, scenario = change_and_scenario(project, cap, rid, sid)
    assert set(scenario) <= set(sp.SCN_FIELDS)
    assert chg.validate_change(project, change)[0] == []
    assert code("change", "status", "metadata", "--json") == 0
    assert code("evidence", "run", "metadata", "1") == 0
    assert code("archive", "metadata", "--dry-run") == 0
    assert code("archive", "metadata") == 0
    assert chg.change_state(project, "metadata") == "archived"
    spec = sp.load_spec(project, cap)
    assert sp.validate_spec(spec) == []
    assert set(sp.find_scenario(sp.find_requirement(spec, rid), sid)) <= set(sp.SCN_FIELDS)
    assert validate_all(project)[0] == []
