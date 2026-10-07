"""Public writes and incremental documents must agree with their existing check rules."""

from __future__ import annotations

import json
import io

import pytest
import yaml

from dspx.check import run_check
from dspx.commands._internal import hook as hook_cmd
from dspx.commands.change import change as change_cmd
from dspx.commands.corpus import put as put_cmd
from dspx.commands.deliverable import render as render_cmd
from dspx.commands.governance import decision as decision_cmd
from dspx.commands.governance import info as info_cmd
from dspx.commands.governance import ruling as ruling_cmd
from dspx.commands.query import check as check_cmd
from dspx.commands.query import status as status_cmd
from dspx.engine import change as doc_changes
from dspx.engine import store
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.schema import load_schema
from dspx.engine.software import specs


@pytest.fixture
def project(make_project, write_leaf, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "gpt")
    assert ruling_cmd.run(["add", "--quote", "Use the first row."]) == 0
    assert decision_cmd.run(["add", "--title", "Entry", "--statement", "The first row must be visible.", "--based-on", "RL-gpt-1"]) == 0
    assert decision_cmd.run(["activate", "D-gpt-1"]) == 0
    assert decision_cmd.run(["add", "--title", "Undecided", "--statement", "Draft policy.", "--based-on", "RL-gpt-1"]) == 0
    assert info_cmd.run(["add", "--about", "Platform", "--quote", "Windows and Linux are used."]) == 0
    layout = Layout(home)
    specs.write_spec(layout, {"capability": "entry", "purpose": "Entry", "requirements": [
        {"id": "R1", "title": "Visible row", "statement": "The first row SHALL be visible.", "verification": ["test"],
         "based-on": ["gov:D-gpt-1"], "scenarios": [{"id": "S1", "title": "Entry", "when": "Opened", "then": "The row is visible"}]}]})
    write_leaf(home, "guide", concept={"id": "sec-root", "title": "Guide", "order": 1, "concept": "Guide", "brief": {"audience": "Users", "depth": "Steps", "breadth": "Entry"}})
    write_leaf(home, "guide/intro", concept={"id": "sec-intro", "title": "Intro", "order": 1, "concept": "Introduction"})
    return layout


def _source(project, name, data):
    path = project.project_root / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(path)


def _concept(ref):
    return {"id": "sec-intro", "title": "Intro", "order": 1, "status": "draft", "concept": "Updated introduction", "realizes": [ref]}


def _stage(project):
    assert change_cmd.run(["new", "revise-guide", "--publish", "advisory", "--why", "Update introduction"]) == 0
    assert change_cmd.run(["add-target", "revise-guide", "sec-intro", "--action", "revise"]) == 0
    return ["--change", "revise-guide"]


def _managed_bytes(project):
    return {path.relative_to(project.planning_home).as_posix(): path.read_bytes() for path in project.planning_home.rglob("*") if path.is_file()}


@pytest.mark.parametrize("ref", ["gov:D-gpt-1", "gov:I-gpt-1", "req:entry/R1"])
@pytest.mark.parametrize("staging", [False, True])
def test_put_realizes_accepts_existing_cross_domain_sources(project, ref, staging):
    extra = _stage(project) if staging else []
    official = store.store_path(project, "guide")
    before = official.read_bytes()
    assert put_cmd.run(["guide/intro", "concept", _source(project, "concept.yaml", _concept(ref)), *extra]) == 0
    if staging:
        assert official.read_bytes() == before
        change = doc_changes.load_change(project, "revise-guide")
        article = doc_changes._load_staging_article(change.dir, "guide")
        assert article.record_by_path("guide/intro").concept["realizes"] == [ref]
    else:
        leaves = load_project(project)
        assert next(leaf for leaf in leaves if leaf.section == "guide/intro").concept["realizes"] == [ref]
        assert run_check(leaves, load_schema(), project).ok


@pytest.mark.parametrize("ref", ["gov:D-gpt-404", "gov:I-gpt-404", "gov:D-gpt-2", "req:entry/R404", "req:entry", "gov:garbage", "sec-root"])
@pytest.mark.parametrize("staging", [False, True])
def test_put_realizes_rejects_missing_draft_or_wrong_kind_without_writing(project, ref, staging, capsys):
    extra = _stage(project) if staging else []
    source = _source(project, "bad-concept.yaml", _concept(ref))
    before = _managed_bytes(project)
    capsys.readouterr()
    assert put_cmd.run(["guide/intro", "concept", source, *extra]) == 1
    assert _managed_bytes(project) == before
    err = capsys.readouterr().err
    assert ref in err and "realizes" in err


@pytest.mark.parametrize("ref", ["gov:D-gpt-1", "gov:I-gpt-1", "req:entry/R1"])
@pytest.mark.parametrize("category", ["concept", "decisions"])
def test_cross_domain_realizes_sources_do_not_leak_into_other_relation_types(project, ref, category):
    if category == "concept":
        data = {**_concept(ref), "realizes": [], "governed-by": [ref]}
    else:
        data = {"entries": [{"id": "doc-rule", "kind": "normative", "status": "accepted", "statement": "Existing document rule.", "supersedes": [ref]}]}
    source = _source(project, "relation.yaml", data)
    before = _managed_bytes(project)
    assert put_cmd.run(["guide/intro", category, source]) == 1
    assert _managed_bytes(project) == before


@pytest.mark.parametrize("query", ["check", "status"])
def test_material_first_partial_section_is_diagnosed_without_crashing(project, query, capsys):
    material = project.project_root / "material.md"
    material.write_text("## fact: Environment {#env}\nWindows and Linux are supported.\n", encoding="utf-8")
    assert put_cmd.run(["guide/partial", "material", str(material)]) == 0
    partial = next(leaf for leaf in load_project(project) if leaf.section == "guide/partial")
    assert partial.concept is None and partial.material
    assert render_cmd.run(["guide"]) == 0
    latest = project.docs_latest("guide")
    latest.write_text("<!-- dspx:section guide/partial -->\n## Partial\n\nAlready written prose from the supplied material.\n", encoding="utf-8")
    before = _managed_bytes(project)
    capsys.readouterr()
    if query == "check":
        assert check_cmd.run(["--json"]) == 1
        payload = json.loads(capsys.readouterr().out)
        assert not payload["ok"]
        assert any("guide/partial" in error and "concept" in error and "missing" in error for error in payload["errors"])
    else:
        assert status_cmd.run(["--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert not payload["checkOk"]
        row = next(row for row in payload["sections"] if row["section"] == "guide/partial")
        assert row["state"] == "waiting(missing:concept)" and not row["files"]["concept"]
    assert _managed_bytes(project) == before


@pytest.mark.parametrize("path", [
    "docspec/corpus/guide/article.yaml",
    "docspec/governance/info/I-gpt-1.yaml",
    "docspec/changes/fix-entry/tasks.yaml",
    "docs/guide/archive/v1.md",
])
@pytest.mark.parametrize("tool,expected", [("Read", 0), ("read_file", 0), ("Write", 2), ("replace", 2), ("unknown-tool", 2), (None, 2)])
def test_guard_allows_known_read_tools_without_loosening_write_or_unknown_protection(project, path, tool, expected, monkeypatch):
    payload = {"cwd": str(project.project_root), "tool_input": {"file_path": path}}
    if tool is not None:
        payload["tool_name"] = tool
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert hook_cmd.run(["guard"]) == expected
