"""Check reports its real coverage without making new completion decisions."""

from __future__ import annotations

import json
import subprocess

import pytest
import yaml

from dspx.check import run_check
from dspx.commands.change import change
from dspx.commands.code import code
from dspx.commands.corpus import get, put
from dspx.commands.deliverable import render
from dspx.commands.query import check
from dspx.engine import change as chg
from dspx.engine.layout import Layout
from dspx.engine.model import load_project
from dspx.engine.schema import load_schema
from dspx.engine.software import specs


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _inject(path, section, text):
    lines = path.read_text(encoding="utf-8").splitlines()
    index = lines.index(f"<!-- dspx:section {section} -->") + 1
    while index < len(lines) and not lines[index].startswith("#"):
        index += 1
    assert index < len(lines)
    lines[index + 1:index + 1] = ["", text, ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def coverage_case(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    for section, order in [("manual/action", 1), ("manual/limits", 2), ("other/reference", 1)]:
        write_leaf(home, section, concept={
            "id": "c-" + section.replace("/", "-"), "title": section, "order": order,
            "concept": "Describe the synthetic local operation.",
            "brief": {"audience": "teachers", "depth": "short", "breadth": "one operation", "kind": "how-to"},
        })
    monkeypatch.chdir(home.parent)
    layout = Layout(home)
    for article in ["manual", "other"]:
        assert render.run([article]) == 0
    _inject(layout.docs_latest("manual"), "manual/action", "Open the local application.")
    _inject(layout.docs_latest("manual"), "manual/limits", "Keep the input file locally.")
    _inject(layout.docs_latest("other"), "other/reference", "CSV columns are class, number and name.")
    for article in ["manual", "other"]:
        assert render.run([article]) == 0
    assert change.run(["new", "revise-manual", "--publish", "advisory", "--why", "Synthetic revision"]) == 0
    assert change.run(["add-target", "revise-manual", "manual/action", "--action", "revise"]) == 0
    capsys.readouterr()
    assert get.run(["manual/action", "concept"]) == 0
    concept = yaml.safe_load(capsys.readouterr().out)
    concept["concept"] = "Explain the updated synthetic local operation."
    source = layout.project_root / "draft-input.yaml"
    source.write_text(yaml.safe_dump(concept, allow_unicode=True), encoding="utf-8")
    assert put.run(["manual/action", "concept", str(source), "--change", "revise-manual"]) == 0
    assert render.run(["manual", "--change", "revise-manual"]) == 0
    preview = chg.preview_dir(chg.load_change(layout, "revise-manual").dir) / "manual_latest.md"
    preview.write_text(preview.read_text(encoding="utf-8").replace("Open the local application.", "Open the updated local application."), encoding="utf-8")
    assert render.run(["manual", "--change", "revise-manual"]) == 0
    capsys.readouterr()
    return layout, preview


def _query(capsys, args):
    capsys.readouterr()
    rc = check.run([*args, "--json"])
    captured = capsys.readouterr()
    assert not captured.err
    return rc, json.loads(captured.out)


def _article(payload, name):
    return next(row for row in payload["coverage"]["prose"]["articles"] if row["article"] == name)


def _assert_unperformed_reviews(payload):
    assert payload["coverage"]["version"] == 1
    assert payload["coverage"]["prose"]["check"] == "asset-references-and-anchors"
    assert payload["coverage"]["prose"]["semantic_review"] == "not-performed"
    assert payload["coverage"]["delivery_review"] == "not-performed"


def test_current_selected_preview_has_performed_reference_scan_and_unchanged_legacy_result(coverage_case, capsys):
    layout, preview = coverage_case
    before = _bytes(layout.project_root)
    rc, payload = _query(capsys, ["--change", "revise-manual"])
    assert rc == 0 and payload["ok"] is True and not payload["errors"]
    assert payload["coverage"]["structure"] == {"scope": "project", "status": "passed"}
    assert payload["coverage"]["software"] == {"status": "passed"}
    row = _article(payload, "manual")
    assert row["references"] == {"status": "performed", "path": preview.relative_to(layout.project_root).as_posix()}
    assert row["current_prose"] == {"status": "current", "reasons": []}
    other = _article(payload, "other")
    assert other["references"]["status"] == "performed"
    assert other["current_prose"] == {"status": "not-assessed", "reasons": []}
    _assert_unperformed_reviews(payload)
    assert _bytes(layout.project_root) == before


@pytest.mark.parametrize("state", ["missing", "stale"])
def test_unready_preview_explains_original_diagnostics_without_changing_ok(coverage_case, capsys, state):
    layout, preview = coverage_case
    if state == "missing":
        preview.unlink()
    else:
        capsys.readouterr()
        assert get.run(["manual/action", "concept", "--change", "revise-manual"]) == 0
        concept = yaml.safe_load(capsys.readouterr().out)
        concept["concept"] = "Newer requirements not yet incorporated into prose."
        source = layout.project_root / "newer-input.yaml"
        source.write_text(yaml.safe_dump(concept), encoding="utf-8")
        assert put.run(["manual/action", "concept", str(source), "--change", "revise-manual"]) == 0
    before = _bytes(layout.project_root)
    rc, payload = _query(capsys, ["--change", "revise-manual"])
    assert rc == 0 and payload["ok"] is True
    row = _article(payload, "manual")
    assert row["references"]["status"] == ("not-performed" if state == "missing" else "performed")
    assert row["current_prose"]["status"] == "deferred"
    assert row["current_prose"]["reasons"] == [r for r in payload["diagnostics"] if r.get("article") == "manual"]
    assert row["current_prose"]["reasons"]
    _assert_unperformed_reviews(payload)
    assert _bytes(layout.project_root) == before


def test_missing_official_prose_does_not_masquerade_as_checked_or_current(coverage_case, capsys):
    layout, _preview = coverage_case
    layout.docs_latest("other").unlink()
    before = _bytes(layout.project_root)
    rc, payload = _query(capsys, [])
    assert rc == 0 and payload["ok"] is True
    row = _article(payload, "other")
    assert row["references"]["status"] == "not-performed"
    assert row["current_prose"]["status"] == "deferred"
    assert any(r.get("code") == "prose-missing" for r in row["current_prose"]["reasons"])
    _assert_unperformed_reviews(payload)
    assert _bytes(layout.project_root) == before


def test_article_scope_only_filters_index_and_does_not_hide_other_article_errors(coverage_case, write_leaf, capsys):
    layout, _preview = coverage_case
    write_leaf.edit(layout.planning_home, "other/reference", concept={"governed-by": ["absent-authority"]})
    before = _bytes(layout.project_root)
    rc, payload = _query(capsys, ["manual", "--change", "revise-manual"])
    assert rc == 1 and payload["ok"] is False
    assert any("absent-authority" in error for error in payload["errors"])
    assert payload["scope"] == "manual"
    assert all(section.startswith("manual/") for section in payload["index"]["sections"])
    assert payload["coverage"]["structure"] == {"scope": "project", "status": "failed"}
    assert {row["article"] for row in payload["coverage"]["prose"]["articles"]} == {"manual", "other"}
    assert _bytes(layout.project_root) == before


def test_software_issues_stay_separate_and_keep_original_nonzero_exit(coverage_case, capsys):
    layout, _preview = coverage_case
    specs.write_spec(layout, {"capability": "synthetic", "purpose": "Synthetic function", "requirements": [
        {"id": "R1", "title": "Local result", "statement": "The function SHALL return a local result.",
         "verification": ["test"], "scenarios": [{"id": "S1", "title": "Result", "when": "called", "then": "local result"}]}]})
    assert code.run(["change", "new", "incomplete-feature", "--why", "Synthetic update", "--modified", "synthetic", "--by", "gpt"]) == 0
    assert code.run(["change", "delta", "incomplete-feature", "--capability", "synthetic", "--op", "modify-scenario",
                     "--ref", "R1/S1", "--then", "updated local result"]) == 0
    baseline = run_check(load_project(layout), load_schema(), layout)
    assert baseline.ok and baseline.software_errors
    before = _bytes(layout.project_root)
    rc, payload = _query(capsys, [])
    assert rc == 1 and payload["ok"] is True and not payload["errors"]
    assert payload["software_errors"] == baseline.software_errors
    assert payload["coverage"]["structure"]["status"] == "passed"
    assert payload["coverage"]["software"]["status"] == "issues"
    _assert_unperformed_reviews(payload)
    assert _bytes(layout.project_root) == before


@pytest.mark.parametrize("selector", [[], ["--change", "revise-manual"]])
def test_text_explanation_uses_same_sources_statuses_and_deferral_reasons_as_json(coverage_case, capsys, selector):
    layout, preview = coverage_case
    if selector:
        preview.unlink()
    before = _bytes(layout.project_root)
    rc, payload = _query(capsys, selector)
    assert check.run(selector) == rc
    text = capsys.readouterr().out
    assert "coverage" in text.lower()
    assert "semantic" in text.lower() and "delivery" in text.lower()
    assert "not-performed" in text
    for row in payload["coverage"]["prose"]["articles"]:
        assert row["article"] in text and row["references"]["path"] in text
        assert row["references"]["status"] in text
        assert row["current_prose"]["status"] in text
        for reason in row["current_prose"]["reasons"]:
            assert reason["message"] in text
    assert _bytes(layout.project_root) == before


def test_coverage_query_never_renders_runs_tests_or_writes_managed_files(coverage_case, monkeypatch, capsys):
    layout, _preview = coverage_case
    before = _bytes(layout.project_root)
    def forbidden(*args, **kwargs):
        raise AssertionError("coverage queries must not execute or refresh anything")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(render, "run", forbidden)
    rc, payload = _query(capsys, ["--change", "revise-manual"])
    assert rc == 0
    _assert_unperformed_reviews(payload)
    assert _bytes(layout.project_root) == before
