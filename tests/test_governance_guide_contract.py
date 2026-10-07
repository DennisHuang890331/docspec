"""Exercise the projected governance contract through real CLI calls and records."""

from __future__ import annotations

import json
import re

import pytest

from dspx.cli import main
from dspx.engine import change as chg
from dspx.engine.layout import Layout


CHANGE = "revise-synthetic-capacity"
OWNER_CHOICE = "Set the synthetic visitor capacity to six."
OWNER_FACT = "The synthetic capacity is read from settings.json."
ORIGINAL = b'{"capacity": 4}\n'


def _snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def _run(args, capsys):
    capsys.readouterr()
    result = main(args)
    output = capsys.readouterr()
    return result, output


@pytest.fixture
def governance_case(make_project, write_leaf, monkeypatch, capsys):
    home = make_project()
    monkeypatch.chdir(home.parent)
    layout = Layout(home, "per-article")
    write_leaf(home, "guide", concept={
        "id": "section-guide", "title": "Synthetic settings guide", "order": 1,
        "concept": "Describe the recorded capacity requirement.",
        "brief": {"audience": "operators", "depth": "short", "breadth": "capacity"},
        "realizes": ["gov:RL-gpt-1", "gov:I-gpt-1"],
    })
    assert main(["ruling", "add", "--quote", OWNER_CHOICE, "--by", "gpt"]) == 0
    assert main(["info", "add", "--about", "Synthetic delivery", "--quote", OWNER_FACT,
                 "--by", "gpt"]) == 0
    official = layout.project_root / "settings.json"
    official.write_bytes(ORIGINAL)
    assert main(["change", "new", CHANGE, "--publish", "advisory", "--title", "Revise capacity",
                 "--why", "Apply the recorded capacity requirement."]) == 0
    assert main(["change", "add-target", CHANGE, "settings.json", "--kind", "file",
                 "--action", "revise"]) == 0
    change = chg.load_change(layout, CHANGE)
    staged = chg.staging_target(change.dir, layout, official)
    notes = chg.notes_path(change.dir)
    assert OWNER_CHOICE not in notes.read_text(encoding="utf-8")
    assert OWNER_FACT not in notes.read_text(encoding="utf-8")
    capsys.readouterr()
    return layout, official, staged, notes


def _develop_contract(data):
    develop = next(skill for skill in data["workflow"]["skills"] if skill["id"] == "develop")
    return [str(step) for step in develop["steps"]]


def _assert_current_governance_contract(steps):
    text = " ".join(" ".join(steps).lower().split())
    # The reader must be directed to the actual source commands, not to a second
    # owner-decision store. Wording may vary; the roles and boundary must remain.
    assert "artispec ruling" in text, "guide must route owner choices to ruling records"
    assert "artispec info" in text, "guide must route owner-provided facts to info records"
    assert re.search(r"(?:exact|verbatim|own|original)\s+(?:owner['’]s\s+)?words|quote", text)
    assert "notes.md" in text
    assert re.search(r"rationale|reason(?:ing|s)?", text)
    assert re.search(r"references?|cit(?:e|ing|ations?)", text)
    assert "human-decision record" not in text
    assert not re.search(r"record the human['’]s ruling.*?into.*?notes\.md", text)
    assert "clear" in text and "unclear" in text
    assert re.search(r"(?:only|when).*?unclear|unclear.*?only", text)
    assert "confirmation" in text or "confirmed" in text
    assert "another confirmation" in text or re.search(r"clear.*?direct|direct.*?clear", text)


@pytest.mark.parametrize("query", [[], ["develop"], ["--json"]],
                         ids=["full-text", "develop-text", "json"])
def test_guide_projects_the_recorded_source_roles_consistently_and_read_only(
        governance_case, capsys, query):
    layout, _official, _staged, _notes = governance_case
    before = _snapshot(layout.project_root)

    rc, canonical = _run(["guide", "--json"], capsys)
    assert rc == 0 and not canonical.err
    data = json.loads(canonical.out)
    steps = _develop_contract(data)
    rc, output = _run(["guide", *query], capsys)
    assert rc == 0 and not output.err
    if "--json" in query:
        assert _develop_contract(json.loads(output.out)) == steps
    else:
        projected = " ".join(output.out.split())
        assert all(" ".join(step.split()) in projected for step in steps)

    rc, ruling = _run(["ruling", "show", "RL-gpt-1", "--json"], capsys)
    assert rc == 0
    recorded_choice = json.loads(ruling.out)
    assert recorded_choice["quote"] == OWNER_CHOICE
    assert "read-back" not in recorded_choice and "confirmed-reply" not in recorded_choice
    rc, info = _run(["info", "show", "I-gpt-1", "--json"], capsys)
    assert rc == 0
    recorded_fact = json.loads(info.out)
    assert recorded_fact["quote"] == OWNER_FACT
    assert "read-back" not in recorded_fact and "confirmed-reply" not in recorded_fact
    assert _snapshot(layout.project_root) == before
    _assert_current_governance_contract(steps)


def test_unclear_content_needs_the_actual_owner_confirmation_not_a_notes_copy(
        governance_case, capsys):
    layout, _official, _staged, notes = governance_case
    for kind, extras, record_id in [
        ("ruling", [], "RL-gpt-2"),
        ("info", ["--about", "Synthetic connection"], "I-gpt-2"),
    ]:
        before = _snapshot(layout.project_root)
        rc, rejected = _run([kind, "add", *extras, "--quote", "Use the previous arrangement.",
                             "--read-back", "Use the recorded local-only connection.", "--by", "gpt"],
                            capsys)
        assert rc == 1 and "--confirmed" in rejected.err
        assert _snapshot(layout.project_root) == before
        before_notes = notes.read_bytes()
        rc, _ = _run([kind, "add", *extras, "--quote", "Use the previous arrangement.",
                      "--read-back", "Use the recorded local-only connection.",
                      "--confirmed", "Yes, local-only is what I mean.", "--by", "gpt"], capsys)
        assert rc == 0
        rc, output = _run([kind, "show", record_id, "--json"], capsys)
        assert rc == 0
        recorded = json.loads(output.out)
        assert recorded["quote"] == "Use the previous arrangement."
        assert recorded["read-back"] == "Use the recorded local-only connection."
        assert recorded["confirmed-reply"] == "Yes, local-only is what I mean."
        assert notes.read_bytes() == before_notes
