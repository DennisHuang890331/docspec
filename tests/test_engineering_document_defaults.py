"""Projected defaults follow document purpose while preserving project authority.

These checks verify the generated contract and its projections. They do not
pretend to grade the readability of prose written by an agent.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest
import yaml

from dspx.commands.maintenance import init
from dspx.commands.projection import guide, instructions
from dspx.commands.code import code
from dspx.commands.query import check
from dspx.engine.layout import Layout
from dspx.engine.software import specs


def _bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _initialize(root, language, monkeypatch, capsys):
    root.mkdir(parents=True)
    monkeypatch.chdir(root)
    assert init.run(["--tool", "codex", "--agents-md", "--lang", language,
                     "--no-tex-hint", "--no-update-check"]) == 0
    capsys.readouterr()
    return root / "docspec"


def _task_contract(text):
    lowered = " ".join(text.lower().split())
    for kind in ["how-to", "reference", "tutorial", "explain"]:
        assert kind in lowered, f"writing defaults must distinguish {kind}"
    for subject in ["task", "precondition", "step", "result", "limit", "audience"]:
        assert subject in lowered, f"engineering defaults must cover useful {subject} content"
    assert "scope" in lowered and "navigation" in lowered
    assert re.search(r"(?:project|existing|explicit).*?(?:override|precedence|take priority)|"
                     r"(?:override|precedence|take priority).*?(?:project|existing|explicit)", lowered)
    assert "each conclusion the next section's premise" not in lowered
    assert "all rules / logic / state" not in lowered
    assert "never narrate this section's own `brief`" not in lowered
    assert "never by narrating the document's own layout" not in lowered


@pytest.mark.parametrize("language", ["en", "zh-TW"])
def test_real_init_generates_task_and_genre_guidance_with_language_seed(tmp_path, monkeypatch, capsys, language):
    home = _initialize(tmp_path / ("中文工程 space " + language), language, monkeypatch, capsys)
    body = (home / "writing-guide.md").read_text(encoding="utf-8")
    _task_contract(body)
    assert "[TBD]" in body
    assert "<!--@" in body and "hand-typed" in body
    assert f"artispec reference writing-{'zh' if language == 'zh-TW' else 'en'}" in body
    assert "動詞當家" in body if language == "zh-TW" else "Verb-centric" in body


@pytest.mark.parametrize("kind", ["how-to", "reference", "tutorial", "explain"])
def test_real_instructions_keep_parent_constraints_child_form_and_delivery_audience(
        tmp_path, monkeypatch, capsys, write_leaf, kind):
    root = tmp_path / "engineer team project"
    home = _initialize(root, "en", monkeypatch, capsys)
    write_leaf(home, "manual", concept={
        "id": "c-manual", "title": "Teacher manual", "order": 1,
        "concept": "Help teachers use the local seating application.",
        "brief": {"audience": "teachers", "depth": "short", "breadth": "local operation", "kind": "how-to"},
    })
    write_leaf(home, "manual/task", concept={
        "id": "c-task", "title": "Operation", "order": 1,
        "concept": "Explain one recorded task.", "brief": {"kind": kind},
    })
    before = _bytes(root)
    assert instructions.run(["apply", "manual/task", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    own = yaml.safe_load(payload["reads"]["concept"])
    assert own["brief"] == {"kind": kind}
    parent = next(row for row in payload["parentBriefs"] if row["section"] == "manual")
    assert parent["brief"]["audience"] == "teachers"
    assert parent["brief"]["kind"] == "how-to"
    assert "engineers" not in own["brief"].values()
    _task_contract(payload["writingGuide"])
    assert _bytes(root) == before


def test_child_audience_override_remains_visible_without_rewriting_parent_source(tmp_path, monkeypatch, capsys, write_leaf):
    root = tmp_path / "project"
    home = _initialize(root, "en", monkeypatch, capsys)
    write_leaf(home, "manual", concept={
        "id": "c-root", "title": "Manual", "order": 1,
        "brief": {"audience": "teachers", "depth": "short", "breadth": "operation", "kind": "how-to"},
    })
    write_leaf(home, "manual/technical", concept={
        "id": "c-technical", "title": "Technical reference", "order": 1,
        "brief": {"audience": "integrators", "kind": "reference"},
    })
    before = _bytes(root)
    assert instructions.run(["apply", "manual/technical", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert yaml.safe_load(payload["reads"]["concept"])["brief"] == {"audience": "integrators", "kind": "reference"}
    assert payload["parentBriefs"][0]["brief"]["audience"] == "teachers"
    assert _bytes(root) == before


def test_guide_and_installed_develop_do_not_impose_universal_argument_chain(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    _initialize(root, "en", monkeypatch, capsys)
    before = _bytes(root)
    assert guide.run(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    develop = next(skill for skill in payload["workflow"]["skills"] if skill["id"] == "develop")
    projected = " ".join(str(step) for step in develop["steps"]).lower()
    installed = root / ".agents" / "skills" / "dspx-develop" / "SKILL.md"
    text = installed.read_text(encoding="utf-8").lower()
    assert "each conclusion the next section's premise" not in text
    assert "how-to" in text and "reference" in text
    assert "task" in projected and "kind" in projected
    assert "artispec ruling" in text and "artispec info" in text
    assert "notes.md" in text and "owner" in text
    assert _bytes(root) == before


def test_reinit_preserves_custom_writing_guide_and_refreshes_versioned_tool_rules(tmp_path, monkeypatch, capsys):
    root = tmp_path / "project"
    home = _initialize(root, "en", monkeypatch, capsys)
    custom = b"# Project writing rules\r\n\r\nWrite terse CSV reference cards.\r\n"
    path = home / "writing-guide.md"
    path.write_bytes(custom)
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    agents.write_text("# User rule\nPreserve the input CSV.\n\n" + text + "\n# User footer\n", encoding="utf-8")
    assert init.run(["--tool", "codex", "--agents-md", "--no-tex-hint", "--no-update-check"]) == 0
    capsys.readouterr()
    assert path.read_bytes() == custom
    text = agents.read_text(encoding="utf-8")
    assert text.startswith("# User rule\nPreserve the input CSV.")
    assert text.rstrip().endswith("# User footer")
    assert text.count(init._AGENTS_MD_BEGIN) == 1
    assert init._AGENTS_MD_VERSION > 3
    prior = {"develop": (2, 5), "apply": (2, 5), "factcheck": (2, 3)}
    for skill, previous in prior.items():
        installed = root / ".agents" / "skills" / f"dspx-{skill}" / "SKILL.md"
        frontmatter = installed.read_text(encoding="utf-8").split("---", 2)[1]
        current = tuple(int(n) for n in str(yaml.safe_load(frontmatter)["metadata"]["version"]).split("."))
        assert current > previous, f"changed {skill} guidance needs an upgrade notice"


def test_real_project_projection_distinguishes_blind_prose_from_allowed_stable_anchor_navigation(
        tmp_path, monkeypatch, capsys, write_leaf):
    root = tmp_path / "navigation project"
    home = _initialize(root, "en", monkeypatch, capsys)
    write_leaf(home, "manual", concept={
        "id": "c-manual", "title": "Manual", "order": 1,
        "brief": {"audience": "teachers", "depth": "short", "breadth": "operation", "kind": "how-to"},
    })
    before = _bytes(root)
    assert instructions.run(["apply", "manual", "--json"]) == 0
    body = json.loads(capsys.readouterr().out)["writingGuide"].lower()
    assert "no cross-section references" not in body, "stable anchor navigation must not be forbidden by another rule"
    assert "blind" in body or "cannot see other sections" in body
    assert "anchor" in body and "navigation" in body
    assert "hand-typed" in body
    assert _bytes(root) == before


def test_actual_software_error_does_not_require_aggregate_green_to_write_ready_document(
        tmp_path, monkeypatch, capsys, write_leaf):
    root = tmp_path / "two domain project"
    home = _initialize(root, "en", monkeypatch, capsys)
    write_leaf(home, "manual", concept={
        "id": "c-manual", "title": "Manual", "order": 1,
        "concept": "Use the locally supplied input.",
        "brief": {"audience": "teachers", "depth": "short", "breadth": "operation", "kind": "how-to"},
    })
    layout = Layout(home)
    specs.write_spec(layout, {"capability": "synthetic", "purpose": "Local function", "requirements": [
        {"id": "R1", "title": "Result", "statement": "The function SHALL return a local result.",
         "verification": ["test"], "scenarios": [{"id": "S1", "title": "Result", "when": "called", "then": "local result"}]}]})
    assert code.run(["change", "new", "missing-tests", "--why", "Synthetic update", "--modified", "synthetic", "--by", "gpt"]) == 0
    assert code.run(["change", "delta", "missing-tests", "--capability", "synthetic", "--op", "modify-scenario",
                     "--ref", "R1/S1", "--then", "updated result"]) == 0
    capsys.readouterr()
    assert check.run(["--json"]) == 1
    checked = json.loads(capsys.readouterr().out)
    assert checked["ok"] and checked["errors"] == [] and checked["software_errors"]
    before = _bytes(root)
    assert instructions.run(["apply", "manual", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["applyMode"]["mode"] == "rewrite"
    assert guide.run(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    apply = next(skill for skill in data["workflow"]["skills"] if skill["id"] == "apply")
    projected = " ".join(str(step) for step in apply["steps"]).lower()
    skill = (root / ".agents" / "skills" / "dspx-apply" / "SKILL.md").read_text(encoding="utf-8")
    rewrite = next(line for line in skill.splitlines() if line.startswith("3. **rewrite**")).lower()
    assert "`artispec check` green" not in rewrite, "aggregate nonzero software result must not block document authoring"
    assert "document" in rewrite and "software" in rewrite
    assert "document" in projected and "software" in projected
    assert _bytes(root) == before


def test_factcheck_requires_actual_source_diagnostics_when_document_check_passes_with_missing_draft_source(
        tmp_path, monkeypatch, capsys, write_leaf):
    root = tmp_path / "missing draft source"
    home = _initialize(root, "en", monkeypatch, capsys)
    ref = "draft-req:absent-change/school/seats/R1"
    write_leaf(home, "manual", concept={
        "id": "c-manual", "title": "Manual", "order": 1,
        "concept": "Explain the claimed seat export.", "realizes": [ref],
        "brief": {"audience": "teachers", "depth": "short", "breadth": "export", "kind": "how-to"},
    })
    before = _bytes(root)
    assert check.run(["--json"]) == 1
    checked = json.loads(capsys.readouterr().out)
    assert checked["ok"] is True and checked["errors"] == []
    assert any(ref in error for error in checked["software_errors"])
    assert instructions.run(["factcheck", "manual", "--json"]) == 0
    projected = json.loads(capsys.readouterr().out)
    resolved = projected["realized"][0]["source"]
    assert resolved["state"] in {"unresolved", "unknown"} and resolved["diagnostics"]
    skill = (root / ".agents" / "skills" / "dspx-factcheck" / "SKILL.md").read_text(encoding="utf-8")
    assert "green = every id resolves" not in skill.lower(), "document check success cannot prove an invalid software reference resolves"
    assert "diagnostic" in skill.lower() and "software" in skill.lower()
    assert _bytes(root) == before
