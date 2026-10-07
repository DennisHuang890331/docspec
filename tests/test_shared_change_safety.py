"""Safety contracts when existing domain records share a change container."""

import io as stream_io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_software_archive import proj, _change, code
from test_unified_changes import _bytes, _document, _legacy
from test_software_import import SPEC, _write
from dspx.commands._internal import hook
from dspx.commands.change import change as change_cmd
from dspx.commands.change import archive as common_archive
from dspx.engine import handover
from dspx.engine.layout import Layout
from dspx.engine.software import archive as software_archive
from dspx.engine.software import changes, io, openspec_import, specs


def _guard(monkeypatch, project_root, payload):
    payload = {"cwd": str(project_root), **payload}
    monkeypatch.setattr("sys.stdin", stream_io.StringIO(json.dumps(payload)))
    return hook.run(["guard"])


def test_legacy_change_can_be_edited_and_archived_using_existing_evidence(proj):
    legacy = _legacy(proj)
    assert code("change", "design", "software-edit", "--context", "Legacy context retained") == 0
    assert changes.load_change(proj, "software-edit")["design"]["context"] == "Legacy context retained"
    assert io.load(legacy / "design.yaml", "design")["context"] == "Legacy context retained"
    assert not (proj.planning_home / "changes/software-edit").exists()
    assert code("evidence", "run", "software-edit", "1") == 0
    assert code("archive", "software-edit") == 0
    archived = changes.load_archived(proj, "software-edit")
    assert not legacy.exists()
    assert archived["design"]["context"] == "Legacy context retained"
    assert archived["tasks"]["tasks"][0]["status"] == "done"
    assert archived["tasks"]["tasks"][0]["evidence"] == ["E-claude-1"]


def test_migration_preserves_archived_container_and_surrounding_record_bytes(proj):
    _change("software-history")
    assert code("archive", "software-history") == 0
    source = changes.load_archived(proj, "software-history")["folder"]
    legacy = proj.planning_home / "software/changes/_archive" / source.name
    if source != legacy:
        assert source.resolve().is_relative_to(proj.planning_home.resolve())
        assert legacy.resolve().is_relative_to(proj.planning_home.resolve())
        legacy.parent.mkdir(parents=True, exist_ok=True)
        source.rename(legacy)
    expected = _bytes(legacy)
    unchanged = {str(path): path.read_bytes() for root in
                 (io.evidence_dir(proj), io.baselines_dir(proj), io.specs_dir(proj))
                 for path in root.rglob("*") if path.is_file()}
    destination = proj.planning_home / "changes/_archive" / legacy.name
    before = _bytes(proj.project_root)
    assert change_cmd.run(["migrate", "--dry-run"]) == 0
    assert _bytes(proj.project_root) == before
    assert change_cmd.run(["migrate"]) == 0
    assert destination.is_dir() and not legacy.exists()
    assert _bytes(destination) == expected
    assert changes.load_archived(proj, "software-history")["folder"] == destination
    assert {name: Path(name).read_bytes() for name in unchanged} == unchanged


def test_migration_rolls_back_completed_moves_if_a_later_move_fails(proj, monkeypatch, capsys):
    first = _legacy(proj, "a-first")
    last = _legacy(proj, "z-last")
    before = _bytes(proj.project_root)
    original = Path.rename
    moved = []

    def fail_last(source, destination):
        if source == last:
            raise OSError("synthetic move failure")
        result = original(source, destination)
        moved.append((source, Path(destination)))
        return result

    monkeypatch.setattr(Path, "rename", fail_last)
    capsys.readouterr()
    assert change_cmd.run(["migrate"]) != 0
    output = capsys.readouterr()
    assert "unknown subcommand" not in output.out + output.err
    assert any(source == first for source, _ in moved), "The test must exercise rollback after a successful move"
    assert _bytes(proj.project_root) == before
    assert first.is_dir() and last.is_dir()
    assert not (proj.planning_home / "changes/a-first").exists()
    assert not (proj.planning_home / "changes/z-last").exists()


def test_migration_validates_all_sealed_parts_before_moving_the_first_change(proj, monkeypatch, capsys):
    first = _legacy(proj, "a-first")
    last = _legacy(proj, "z-last")
    (last / "tasks.yaml").write_text("invalid: true\n", encoding="utf-8")
    before = _bytes(proj.project_root)

    def forbidden(*args, **kwargs):
        raise AssertionError("Migration must finish validating every change before the first move")

    monkeypatch.setattr(Path, "rename", forbidden)
    capsys.readouterr()
    assert change_cmd.run(["migrate"]) != 0
    output = capsys.readouterr()
    assert "tasks.yaml" in output.out + output.err
    assert _bytes(proj.project_root) == before
    assert first.is_dir() and last.is_dir()


def test_shared_overview_reports_broken_test_plan_instead_of_omitting_the_change(proj, capsys):
    _change("software-edit", run=False)
    folder = changes.load_change(proj, "software-edit")["folder"]
    (folder / "tests.yaml").write_text("invalid: true\n", encoding="utf-8")
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert change_cmd.run(["--json"]) != 0
    output = capsys.readouterr()
    assert "tests.yaml" in output.out + output.err
    assert _bytes(proj.project_root) == before


def test_archived_identity_duplicate_is_rejected_across_dates_and_locations(proj, capsys):
    _change("software-history")
    assert code("archive", "software-history") == 0
    archived = changes.load_archived(proj, "software-history")["folder"]
    legacy = proj.planning_home / "software/changes/_archive/2025-01-01-software-history"
    assert legacy.name != archived.name
    legacy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(archived, legacy)
    before = _bytes(proj.project_root)
    capsys.readouterr()
    assert change_cmd.run(["show", "software-history", "--json"]) != 0
    assert change_cmd.run(["--all", "--json"]) != 0
    output = capsys.readouterr()
    assert "duplicate" in (output.out + output.err).lower()
    assert _bytes(proj.project_root) == before


@pytest.mark.parametrize("relative", ["proposal.yaml", "design.yaml", "tests.yaml", "tasks.yaml", "specs/entry.yaml"])
@pytest.mark.parametrize("payload_kind", ["file", "patch", "shell"])
def test_shared_software_records_remain_engine_owned(proj, monkeypatch, relative, payload_kind):
    _change("software-edit", run=False)
    path = proj.planning_home / "changes/software-edit" / relative
    assert path.is_file(), "The protected file must really be in the shared container"
    token = path.as_posix()
    if payload_kind == "file":
        payload = {"tool_input": {"file_path": token}}
    elif payload_kind == "patch":
        payload = {"tool_name": "apply_patch", "tool_input": {
            "input": f"*** Begin Patch\n*** Update File: {token}\n@@\n-x\n+y\n*** End Patch\n"}}
    else:
        payload = {"tool_input": {"command": f"echo changed > '{token}'"}}
    before = path.read_bytes()
    assert _guard(monkeypatch, proj.project_root, payload) == 2
    assert path.read_bytes() == before


def test_document_staging_yaml_is_editable_even_when_software_changes_exist(proj, write_leaf, monkeypatch):
    document = _document(proj, write_leaf)
    _change("software-edit", run=False)
    # Domain-specific staging stays editable; sharing the parent must not seal all YAML.
    staged = document.dir / "staging/draft.yaml"
    staged.write_text("draft: editable\n", encoding="utf-8")
    assert _guard(monkeypatch, proj.project_root,
                  {"tool_input": {"file_path": staged.as_posix()}}) == 0


@pytest.mark.parametrize("payload_kind", ["file", "patch", "shell"])
def test_hook_resolves_relative_software_paths_using_reported_working_directory(proj, monkeypatch, payload_kind):
    _change("software-edit", run=False)
    folder = changes.load_change(proj, "software-edit")["folder"]
    before = _bytes(folder)
    if payload_kind == "file":
        payload = {"tool_input": {"file_path": "tasks.yaml"}}
    elif payload_kind == "patch":
        payload = {"tool_name": "apply_patch", "tool_input": {
            "input": "*** Begin Patch\n*** Update File: tasks.yaml\n@@\n-x\n+y\n*** End Patch\n"}}
    else:
        payload = {"tool_input": {"command": "echo changed > tasks.yaml"}}
    assert _guard(monkeypatch, folder, payload) == 2
    assert _bytes(folder) == before


def test_hook_allows_relative_document_staging_path(proj, write_leaf, monkeypatch):
    document = _document(proj, write_leaf)
    staged = document.dir / "staging/draft.yaml"
    staged.write_text("draft: editable\n", encoding="utf-8")
    assert _guard(monkeypatch, staged.parent, {"tool_input": {"file_path": "draft.yaml"}}) == 0
    assert _guard(monkeypatch, staged.parent, {"tool_input": {"command": "echo draft > draft.yaml"}}) == 0


@pytest.mark.parametrize("boundary", ["common", "code", "plan", "archive"])
def test_archive_refuses_active_and_historical_copies_of_one_software_identity(proj, boundary):
    _change("software-edit")
    active = changes.load_change(proj, "software-edit")["folder"]
    historical = proj.planning_home / "software/changes/_archive/2025-01-01-software-edit"
    historical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(active, historical)
    before = _bytes(proj.project_root)
    if boundary == "common":
        assert common_archive.run(["software-edit"]) != 0
    elif boundary == "code":
        assert code("archive", "software-edit") != 0
    else:
        with pytest.raises(io.SoftwareError, match="duplicate"):
            if boundary == "plan":
                software_archive.plan(proj, "software-edit")
            else:
                software_archive.archive(proj, "software-edit", tool="claude")
    assert _bytes(proj.project_root) == before
    assert active.is_dir() and historical.is_dir()


@pytest.mark.parametrize("boundary", ["common", "document"])
def test_document_archive_refuses_identity_already_in_software_history(proj, write_leaf, boundary):
    _change("shared-identity")
    assert code("archive", "shared-identity") == 0
    archived = changes.load_archived(proj, "shared-identity")["folder"]
    # Build the conflicting legacy state directly, because normal creation correctly refuses it.
    _document(proj, write_leaf, "temporary-doc")
    document = proj.planning_home / "changes/temporary-doc"
    from dspx.engine import change as documents
    record = documents.load_change(proj, "temporary-doc")
    record.id = "shared-identity"
    documents.save_change(record)
    document.rename(proj.planning_home / "changes/shared-identity")
    before = _bytes(proj.project_root)
    args = ["shared-identity", "--abandon", "--reason", "Must reject conflicting identity"]
    if boundary == "common":
        assert common_archive.run(args) != 0
    else:
        assert change_cmd.run(["archive", *args]) != 0
    assert _bytes(proj.project_root) == before
    assert archived.is_dir() and (proj.planning_home / "changes/shared-identity").is_dir()


@pytest.mark.parametrize("boundary", ["common", "code", "plan", "archive"])
@pytest.mark.parametrize("identifier", ["forward-traversal", "windows-traversal", "nested", "absolute"])
def test_archive_rejects_path_identity_even_when_container_is_readable(proj, boundary, identifier):
    cid = {"forward-traversal": "../../outside", "windows-traversal": "..\\..\\outside",
           "nested": "nested/change", "absolute": str(proj.project_root / "outside")}[identifier]
    container = proj.planning_home / "changes" / cid
    assert container.resolve().is_relative_to(proj.project_root.resolve())
    io.write(container / "proposal.yaml", "proposal", {
        "id": cid, "why": "Synthetic container addressed with invalid path identity",
        "capabilities": {"new": [], "modified": []}})
    before = _bytes(proj.project_root)
    if boundary == "common":
        assert common_archive.run([cid]) != 0
    elif boundary == "code":
        assert code("archive", cid) != 0
    else:
        with pytest.raises(io.SoftwareError):
            if boundary == "plan":
                software_archive.plan(proj, cid)
            else:
                software_archive.archive(proj, cid, tool="claude")
    assert _bytes(proj.project_root) == before
    assert container.is_dir()


@pytest.mark.parametrize("boundary", ["plan", "archive"])
def test_archive_refuses_change_folder_linked_outside_managed_home(proj, boundary):
    assert code("change", "new", "linked-edit", "--why", "Synthetic linked change") == 0
    source = changes.load_change(proj, "linked-edit")["folder"]
    outside = proj.project_root / "outside"
    source.rename(outside)
    try:
        source.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # Junctions exercise Windows directory links without requiring symlink privilege.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(source), str(outside)],
                       check=True, capture_output=True)
    assert source.resolve() == outside.resolve()
    before = _bytes(proj.project_root)
    with pytest.raises(io.SoftwareError):
        if boundary == "plan":
            software_archive.plan(proj, "linked-edit")
        else:
            software_archive.archive(proj, "linked-edit", tool="claude")
    assert _bytes(proj.project_root) == before
    assert source.is_dir() and outside.is_dir()


@pytest.mark.parametrize("damage", ["seal", "missing-kind", "scalar", "empty"])
@pytest.mark.parametrize("location", ["shared", "legacy"])
def test_handover_cannot_claim_current_or_stale_when_software_record_is_corrupt(proj, damage, location):
    if location == "legacy":
        folder = _legacy(proj)
    else:
        _change("software-edit", run=False)
        folder = proj.planning_home / "changes/software-edit"
    record = folder / "proposal.yaml"
    assert record.is_file()
    handover.write(proj, {"next": ["Resume this synthetic change"]}, tool="claude")
    note = handover.load(proj)
    assert handover.freshness(proj, note)["status"] == "current"
    text = record.read_text(encoding="utf-8")
    if damage == "seal":
        text = text.replace("why: x", "why: changed", 1)
        assert text != record.read_text(encoding="utf-8")
    elif damage == "missing-kind":
        text = "body: {}\n"
    elif damage == "scalar":
        text = "42\n"
    else:
        text = ""
    record.write_text(text, encoding="utf-8")
    before = _bytes(proj.planning_home)
    result = handover.freshness(proj, note)
    assert result["status"] == "unknown"
    assert result["changes-available"] is False and result["reason"]
    assert _bytes(proj.planning_home) == before


@pytest.mark.parametrize("collision_kind", ["active", "archived"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_openspec_import_preflights_all_document_identity_collisions(make_project, monkeypatch, write_leaf,
                                                                    collision_kind, dry_run):
    home = make_project()
    monkeypatch.chdir(home.parent)
    monkeypatch.setenv("DOCSPEC_AGENT", "claude")
    layout = Layout(home)
    _document(layout, write_leaf, "z-collision")
    source = layout.project_root / "openspec"
    _write(source, "specs/imported-cap/spec.md", SPEC)
    _write(source, "changes/a-first/proposal.md", "## Why\n\nA valid synthetic import.\n")
    collision = ("changes/z-collision/proposal.md" if collision_kind == "active" else
                 "changes/archive/2026-09-01-z-collision/proposal.md")
    _write(source, collision, "## Why\n\nMust not overwrite the document identity.\n")
    assert specs.list_capabilities(layout) == []
    before = _bytes(layout.project_root)
    with pytest.raises(io.SoftwareError, match="z-collision"):
        openspec_import.run_import(layout, source, tool="claude", dry_run=dry_run)
    assert _bytes(layout.project_root) == before
    assert not (home / "changes/a-first").exists()
    assert specs.list_capabilities(layout) == []


def test_software_archive_preview_derives_current_tasks_without_persisting_them(proj):
    _change("software-edit")
    change = changes.load_change(proj, "software-edit")
    change["tasks"]["tasks"][0]["status"] = "not-started"
    change["tasks"]["tasks"][0].pop("evidence", None)
    changes.write_part(proj, "software-edit", "tasks", change["tasks"])
    before = _bytes(proj.planning_home)
    assert code("archive", "software-edit", "--dry-run") == 0
    assert _bytes(proj.planning_home) == before
    assert changes.load_change(proj, "software-edit")["tasks"]["tasks"][0]["status"] == "not-started"
