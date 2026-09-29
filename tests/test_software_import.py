"""OpenSpec 匯入（P2-6）：用合成的小型 openspec/ 資料夾驗證每一種差異與任務狀態。"""

from __future__ import annotations

import pytest

from dspx.commands.code import code as code_cmd
from dspx.engine.layout import Layout
from dspx.engine.software import changes as chg
from dspx.engine.software import io
from dspx.engine.software import openspec_import as osi
from dspx.engine.software import specs as sp
from dspx.engine.software import validate_all

SPEC = """# task-entry-page Specification

## Purpose
The home page lists tasks.

## Requirements

### Requirement: The home page is the task list
The home page SHALL show the task list.

#### Scenario: Opening a task
- **WHEN** the annotator opens the home page
- **THEN** the first row is visible
- **AND** it can be opened

#### Scenario: Many AI jobs
- **WHEN** hundreds of jobs ran
- **THEN** the page is unchanged

### Requirement: Old import rows
Import rows SHALL appear at the top.

#### Scenario: Import running
- **WHEN** an import runs
- **THEN** its row shows progress

### Requirement: Delete is one step
Deleting SHALL be one step.

#### Scenario: Delete
- **WHEN** the annotator deletes
- **THEN** the task is gone
"""

NESTED = """## Purpose
Folder format.

## Requirements

### Requirement: Folder layout
Recordings MUST follow the layout.

```
### Requirement: not a header inside a code fence
```

#### Scenario: Layout
- **GIVEN** a recording
- **WHEN** it is registered
- **THEN** it follows the layout
"""

DELTA = """## MODIFIED Requirements

### Requirement: The home page is the task list
The home page SHALL show the task list and dataset information.

#### Scenario: Opening a task
- **WHEN** the annotator opens the home page
- **THEN** the first row is fully visible

#### Scenario: Dataset first
- **WHEN** the home page opens
- **THEN** dataset information is shown first

## REMOVED Requirements

### Requirement: Delete is one step
**Reason**: Replaced by recording deletion.
**Migration**: See dataset-library.

## RENAMED Requirements

- FROM: `### Requirement: Old import rows`
- TO: `### Requirement: Imports appear as task rows`

## ADDED Requirements

### Requirement: GPU status
The home page SHALL show GPU status.

#### Scenario: Reading GPU status
- **WHEN** the page loads
- **THEN** GPU memory is shown
"""

NEW_CAP = """## Purpose
Dataset library.

## ADDED Requirements

### Requirement: Explicit receipt completion
A receipt SHALL be registered only after completion is pressed.

#### Scenario: Missing split file
- **WHEN** a split file is missing
- **THEN** registration is refused
"""

TASKS = """## 1. Storage

- [x] 1.1 Build the data service
- [ ] 1.2 Implement tables
* [X] 1.3 Implement schemas
"""


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def proj(make_project, monkeypatch):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    root = home.parent / "openspec"
    _write(root, "specs/task-entry-page/spec.md", SPEC)
    _write(root, "specs/annotation/recording-folder-format/spec.md", NESTED)
    _write(root, "changes/dataset-library/proposal.md",
           "## Why\n\nNeed a dataset library.\n\n## What Changes\n\n- Add a library\n- Merge the home "
           "page\n  into one page\n\n## Impact\n\nPortal pages.\n")
    _write(root, "changes/dataset-library/design.md", "## Context\n\nD1 keep images in bags.\n")
    _write(root, "changes/dataset-library/tasks.md", TASKS)
    _write(root, "changes/dataset-library/discussion.md", "notes")
    _write(root, "changes/dataset-library/.openspec.yaml", "schema: spec-driven\ncreated: 2026-09-22\n")
    _write(root, "changes/dataset-library/specs/task-entry-page/spec.md", DELTA)
    _write(root, "changes/dataset-library/specs/dataset-library/spec.md", NEW_CAP)
    _write(root, "changes/archive/2026-09-15-annotation/proposal.md", "## Why\n\nFirst version.\n")
    _write(root, "changes/archive/2026-09-15-annotation/tasks.md", "- [x] 1.1 done\n- [x] 1.2 done\n")
    _write(root, "changes/archive/2026-09-15-annotation/specs/task-entry-page/spec.md", "## ADDED Requirements\n")
    return Layout(home)


def test_import_specs_changes_and_history(proj, capsys):
    assert code_cmd.run(["import-openspec"]) == 0
    out = capsys.readouterr().out
    assert "imported 2 spec(s), 1 active and 1 archived change(s)" in out

    spec = sp.load_spec(proj, "task-entry-page")
    assert [r["id"] for r in spec["requirements"]] == ["R1", "R2", "R3"]
    s1 = spec["requirements"][0]["scenarios"][0]
    assert s1 == {"id": "S1", "title": "Opening a task", "when": "the annotator opens the home page",
                  "then": "the first row is visible; it can be opened"}
    nested = sp.load_spec(proj, "annotation/recording-folder-format")
    assert len(nested["requirements"]) == 1                     # code fence 裡的不是標題
    assert nested["requirements"][0]["scenarios"][0]["when"] == "given a recording; it is registered"
    assert all(sp.validate_spec(s) == [] for s in sp.load_all(proj).values())

    ch = chg.load_change(proj, "dataset-library")
    ops = [(d["op"], d.get("ref") or d.get("id")) for d in ch["deltas"]["task-entry-page"]["deltas"]]
    assert ops == [("rename-requirement", "R2"), ("modify-requirement", "R1"),
                   ("modify-scenario", "R1/S1"), ("add-scenario", "R1"),
                   ("remove-scenario", "R1/S2"), ("remove-requirement", "R3"),
                   ("add-requirement", "R4")]
    assert all("base" in d for d in ch["deltas"]["task-entry-page"]["deltas"]
               if d["op"] not in ("add-requirement", "add-scenario"))
    assert ch["deltas"]["dataset-library"]["new"] is True
    assert ch["proposal"]["capabilities"] == {"new": ["dataset-library"], "modified": ["task-entry-page"]}
    assert ch["proposal"]["what"] == ["Add a library", "Merge the home page into one page"]
    assert ch["proposal"]["created-at"] == "2026-09-22"
    assert ch["design"]["context"].startswith("## Context")
    assert [t["status"] for t in ch["tasks"]["tasks"]] == ["imported-done", "not-started", "imported-done"]

    assert chg.change_state(proj, "annotation") == "archived"
    hist = chg.load_archived(proj, "annotation")
    assert [t["status"] for t in hist["tasks"]["tasks"]] == ["imported-done", "imported-done"]

    report = (io.root(proj) / "import-openspec-report.md").read_text(encoding="utf-8")
    assert "匯入時已完成（無證據）" in report and "discussion.md" in report
    assert (proj.project_root / "openspec" / "specs").is_dir()          # 原檔不動


def test_preview_of_imported_change_applies_cleanly(proj):
    code_cmd.run(["import-openspec"])
    ch = chg.load_change(proj, "dataset-library")
    new_specs, conflicts, _ = chg.preview_specs(proj, ch)
    assert not conflicts
    tep = new_specs["task-entry-page"]
    assert [r["title"] for r in tep["requirements"]] == [
        "The home page is the task list", "Imports appear as task rows", "GPU status"]
    assert [s["title"] for s in tep["requirements"][0]["scenarios"]] == ["Opening a task", "Dataset first"]
    assert tep["retired"] == {"requirements": ["R3"], "scenarios": ["R1/S2"]}


def test_imported_gaps_are_one_warning_but_block_archive(proj, capsys):
    code_cmd.run(["import-openspec"])
    errs, warns = validate_all(proj)
    assert errs == []
    assert any("imported from OpenSpec" in w for w in warns)
    capsys.readouterr()
    assert code_cmd.run(["archive", "dataset-library"]) == 1
    assert "no task implements it" in capsys.readouterr().out


def test_task_set_fills_links_for_imported_tasks(proj, capsys):
    code_cmd.run(["import-openspec"])
    assert code_cmd.run(["task", "set", "dataset-library", "2", "--implements", "task-entry-page/R1",
                         "--verify", "inspection"]) == 0
    t = chg.load_change(proj, "dataset-library")["tasks"]["tasks"][1]
    assert t["implements"] == ["task-entry-page/R1"] and t["verify"] == {"methods": ["inspection"]}
    assert code_cmd.run(["task", "set", "dataset-library", "2", "--verify", "test"]) == 1   # 缺 --tests


def test_refuses_to_import_twice_and_dry_run_writes_nothing(proj, capsys):
    assert code_cmd.run(["import-openspec", "--dry-run"]) == 0
    assert "# OpenSpec 匯入報告" in capsys.readouterr().out
    assert sp.list_capabilities(proj) == []
    assert code_cmd.run(["import-openspec"]) == 0
    assert code_cmd.run(["import-openspec"]) == 1
    assert "only into an empty software domain" in capsys.readouterr().err


def test_unmatched_names_are_reported_not_guessed(proj):
    root = proj.project_root / "openspec"
    _write(root, "changes/dataset-library/specs/task-entry-page/spec.md",
           "## MODIFIED Requirements\n\n### Requirement: No such thing\nIt SHALL x.\n\n"
           "#### Scenario: s\n- **WHEN** a\n- **THEN** b\n")
    report = osi.run_import(proj, root, tool="claude")
    assert any("MODIFIED \"No such thing\" not found" in n for n in report["notes"])
