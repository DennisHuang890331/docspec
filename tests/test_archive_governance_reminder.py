"""Archive notes carry rationale/references; the owner's words remain in governance."""

import re

import pytest

from dspx.commands.change import change as change_cmd
from dspx.commands.governance import decision, info, ruling
from dspx.engine import change as chg
from dspx.engine.layout import Layout


CHANGE = "revise-settings"
ORIGINAL = b'{"capacity": 4}\n'
REVISED = b'{"capacity": 6}\n'


@pytest.fixture
def archive_case(make_project, write_leaf, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    layout = Layout(home, "per-article")
    assert ruling.run(["add", "--quote", "Set the synthetic visitor capacity to six.", "--by", "gpt"]) == 0
    assert info.run(["add", "--about", "Synthetic delivery", "--quote", "The capacity is read from settings.json.",
                     "--by", "gpt"]) == 0
    assert decision.run(["add", "--title", "Visitor capacity", "--statement", "The configured capacity SHALL be six.",
                         "--based-on", "RL-gpt-1", "--by", "gpt"]) == 0
    assert decision.run(["activate", "D-gpt-1"]) == 0
    write_leaf(home, "guide", concept={
        "id": "section-guide", "title": "Settings guide", "order": 1, "status": "stable",
        "concept": "Describe the recorded capacity rule.", "realizes": ["gov:D-gpt-1", "gov:I-gpt-1"],
        "brief": {"audience": "operators", "depth": "short", "breadth": "capacity setting", "forbidden": []},
    })
    official = layout.project_root / "settings.json"
    official.write_bytes(ORIGINAL)
    assert change_cmd.run(["new", CHANGE, "--publish", "advisory", "--title", "Revise settings",
                           "--why", "Apply the recorded capacity rule."]) == 0
    assert change_cmd.run(["add-target", CHANGE, "settings.json", "--action", "revise", "--kind", "file"]) == 0
    change = chg.load_change(layout, CHANGE)
    staged = chg.staging_target(change.dir, layout, official)
    assert staged.read_bytes() == ORIGINAL
    return layout, official, staged, chg.notes_path(change.dir)


def _governance_bytes(layout):
    root = layout.planning_home / "governance"
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _notes_bytes(path):
    return path.read_bytes() if path.is_file() else None


def _notes_state(path, state):
    if state == "missing":
        path.unlink()
    return _notes_bytes(path)


def _assert_advisory_rationale_and_source_query(stderr):
    text = " ".join(stderr.lower().split())
    assert "notes.md" in text
    assert re.search(r"non[- ]blocking|advisory|does not block", text), stderr
    assert "rationale" in text or "reason" in text, stderr
    assert re.search(r"artispec (?:ruling|decision|info) (?:list|show)\b", text), stderr
    assert not re.search(r"human[- ]decision record.*(?:is empty|is missing)", text), stderr
    assert not re.search(r"(?:should|must|need to)\s+(?:have\s+)?(?:copy|duplicate|re-record|record)\b.*(?:ruling|decision)", text), stderr


def _assert_no_premature_archive_claim(stderr):
    text = " ".join(stderr.lower().split())
    assert "archiving anyway" not in text, stderr
    assert not re.search(r"(?:will|already)\s+(?:be\s+)?archiv(?:e|ed|ing)\b", text), stderr


@pytest.mark.parametrize("notes_state", ["seed-only", "missing"])
def test_ready_target_archives_with_advisory_without_rewriting_notes_or_governance(archive_case, capsys, notes_state):
    layout, official, staged, notes = archive_case
    before_notes = _notes_state(notes, notes_state)
    before_governance = _governance_bytes(layout)
    staged.write_bytes(REVISED)
    capsys.readouterr()

    assert change_cmd.run(["archive", CHANGE]) == 0
    output = capsys.readouterr()

    assert chg.change_state(layout, CHANGE) == chg.STATE_ARCHIVED
    assert official.read_bytes() == REVISED
    archived_notes = chg.notes_path(chg.change_dir(layout, CHANGE, chg.STATE_ARCHIVED))
    assert _notes_bytes(archived_notes) == before_notes
    assert _governance_bytes(layout) == before_governance
    _assert_advisory_rationale_and_source_query(output.err)
    _assert_no_premature_archive_claim(output.err)


@pytest.mark.parametrize("extra", [
    "\n## Rationale\nChanging the setting aligns this delivery with the approved capacity.\n",
    "\n## Sources\nSee gov:RL-gpt-1, gov:D-gpt-1 and gov:I-gpt-1 for the original owner records.\n",
], ids=["additional-rationale", "governance-references"])
def test_substantive_notes_do_not_trigger_the_seed_only_reminder(archive_case, capsys, extra):
    layout, official, staged, notes = archive_case
    notes.write_text(notes.read_text(encoding="utf-8") + extra, encoding="utf-8", newline="\n")
    before_notes, before_governance = notes.read_bytes(), _governance_bytes(layout)
    staged.write_bytes(REVISED)
    capsys.readouterr()

    assert change_cmd.run(["archive", CHANGE]) == 0
    output = capsys.readouterr()

    assert chg.change_state(layout, CHANGE) == chg.STATE_ARCHIVED
    assert official.read_bytes() == REVISED
    assert "notes.md" not in output.err
    archived_notes = chg.notes_path(chg.change_dir(layout, CHANGE, chg.STATE_ARCHIVED))
    assert archived_notes.read_bytes() == before_notes
    assert _governance_bytes(layout) == before_governance


@pytest.mark.parametrize("notes_state", ["seed-only", "missing"])
def test_incomplete_target_stays_active_and_reminder_does_not_claim_archiving(archive_case, capsys, notes_state):
    layout, official, staged, notes = archive_case
    before_notes = _notes_state(notes, notes_state)
    before_governance = _governance_bytes(layout)
    capsys.readouterr()

    assert change_cmd.run(["archive", CHANGE]) == 1
    output = capsys.readouterr()

    assert chg.change_state(layout, CHANGE) == chg.STATE_ACTIVE
    assert not chg.change_dir(layout, CHANGE, chg.STATE_ARCHIVED).exists()
    assert official.read_bytes() == staged.read_bytes() == ORIGINAL
    assert _notes_bytes(notes) == before_notes
    assert _governance_bytes(layout) == before_governance
    assert "not archivable" in output.err and "settings.json" in output.err
    _assert_no_premature_archive_claim(output.err)
    _assert_advisory_rationale_and_source_query(output.err)


def test_advisory_keeps_fork_drift_guard_and_explicit_override(archive_case, capsys):
    layout, official, staged, notes = archive_case
    staged.write_bytes(REVISED)
    third_party = b'{"capacity": 8}\n'
    official.write_bytes(third_party)
    before_notes, before_governance = notes.read_bytes(), _governance_bytes(layout)
    capsys.readouterr()

    assert change_cmd.run(["archive", CHANGE]) == 1
    blocked = capsys.readouterr()
    assert chg.change_state(layout, CHANGE) == chg.STATE_ACTIVE
    assert official.read_bytes() == third_party
    assert staged.read_bytes() == REVISED
    assert notes.read_bytes() == before_notes
    assert _governance_bytes(layout) == before_governance
    assert "drift" in blocked.err and "settings.json" in blocked.err
    _assert_no_premature_archive_claim(blocked.err)
    _assert_advisory_rationale_and_source_query(blocked.err)

    assert change_cmd.run(["archive", CHANGE, "--override-drift"]) == 0
    accepted = capsys.readouterr()
    assert chg.change_state(layout, CHANGE) == chg.STATE_ARCHIVED
    assert official.read_bytes() == REVISED
    archived_notes = chg.notes_path(chg.change_dir(layout, CHANGE, chg.STATE_ARCHIVED))
    assert archived_notes.read_bytes() == before_notes
    assert _governance_bytes(layout) == before_governance
    _assert_advisory_rationale_and_source_query(accepted.err)
